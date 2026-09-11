package kr.co.jinjubus.ui

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.content.Context
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Text
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.DefaultLifecycleObserver
import androidx.lifecycle.LifecycleOwner
import kr.co.jinjubus.BuildConfig
import kr.co.jinjubus.core.Landmark
import kr.co.jinjubus.core.UiVehicle
import kr.co.jinjubus.core.shouldInitializeMapCamera
import kr.co.jinjubus.data.validGps
import kr.co.jinjubus.data.BundledMapStore
import kotlinx.coroutines.CancellationException
import org.maplibre.android.annotations.IconFactory
import org.maplibre.android.annotations.Marker
import org.maplibre.android.annotations.MarkerOptions
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView

@Composable
fun BusMap(
    vehicles: List<UiVehicle>,
    landmarks: List<Landmark>,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    var prepareAttempt by remember { mutableStateOf(0) }
    val packageState by produceState("loading", prepareAttempt) {
        value = "loading"
        try {
            BundledMapStore.prepare(context)
            value = "ready"
        } catch (cancelled: CancellationException) { throw cancelled
        } catch (failure: Exception) {
            android.util.Log.e("BUS_MAP", "Bundled map import failed", failure)
            value = "error"
        }
    }
    if (packageState != "ready") {
        Box(modifier, contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("진주 지도")
                if (packageState == "loading") {
                    CircularProgressIndicator()
                    Text("저장된 지도를 준비하고 있어요")
                } else {
                    Text("지도를 열지 못했습니다")
                    FilledTonalButton(onClick = { prepareAttempt++ }) { Text("다시 열기") }
                }
            }
        }
        return
    }
    val lifecycleOwner = LocalLifecycleOwner.current
    val mapView = remember { MapView(context).also { it.onCreate(null) } }
    var map by remember { mutableStateOf<MapLibreMap?>(null) }
    var styleReady by remember { mutableStateOf(false) }
    var mapRendered by remember { mutableStateOf(false) }
    var cameraInitialized by remember { mutableStateOf(false) }
    val markers = remember { linkedMapOf<String, Marker>() }
    val markerSignatures = remember { mutableMapOf<String, String>() }

    DisposableEffect(lifecycleOwner, mapView) {
        val observer = object : DefaultLifecycleObserver {
            override fun onStart(owner: LifecycleOwner) = mapView.onStart()
            override fun onResume(owner: LifecycleOwner) = mapView.onResume()
            override fun onPause(owner: LifecycleOwner) = mapView.onPause()
            override fun onStop(owner: LifecycleOwner) = mapView.onStop()
            override fun onDestroy(owner: LifecycleOwner) = mapView.onDestroy()
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            markers.clear()
            markerSignatures.clear()
        }
    }

    val positionedVehicles = vehicles.filter { validGps(it.lat, it.lon) }
    val fitPoints = if (positionedVehicles.isNotEmpty()) {
        positionedVehicles.map { LatLng(it.lat!!, it.lon!!) }
    } else {
        landmarks.map { LatLng(it.lat, it.lon) }
    }

    Box(modifier = modifier) {
        AndroidView(
            modifier = Modifier.fillMaxSize().semantics {
                contentDescription = if (mapRendered) "진주 지도" else "지도 불러오는 중"
            },
            factory = {
                mapView.apply {
                    addOnDidFinishRenderingMapListener { fully ->
                        if (fully && styleReady && !mapRendered) {
                            mapRendered = true
                            android.util.Log.i("BUS_MAP", "Map tiles fully rendered")
                        }
                    }
                    getMapAsync { readyMap ->
                        map = readyMap
                        readyMap.setStyle(BuildConfig.MAP_STYLE_URL) {
                            android.util.Log.i("BUS_MAP", "Map style ready: ${it.layers.size} layers")
                            styleReady = true
                        }
                    }
                }
            },
            update = {
                val readyMap = map
                if (readyMap != null && styleReady) {
                    reconcileMarkers(
                        context = context,
                        map = readyMap,
                        vehicles = positionedVehicles,
                        landmarks = landmarks,
                        existing = markers,
                        signatures = markerSignatures,
                    )
                    if (shouldInitializeMapCamera(cameraInitialized, fitPoints.isNotEmpty())) {
                        fitInitialCamera(readyMap, fitPoints)
                        cameraInitialized = true
                    }
                }
            },
        )
        if (fitPoints.isNotEmpty()) {
            FilledTonalButton(
                onClick = { map?.let { fitInitialCamera(it, fitPoints) } },
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(10.dp),
            ) {
                Text("전체 보기")
            }
        }
    }
}

@Suppress("DEPRECATION")
private fun reconcileMarkers(
    context: Context,
    map: MapLibreMap,
    vehicles: List<UiVehicle>,
    landmarks: List<Landmark>,
    existing: MutableMap<String, Marker>,
    signatures: MutableMap<String, String>,
) {
    val desired = buildSet {
        vehicles.forEach { add("vehicle:${it.key}") }
        landmarks.forEach { add("landmark:${it.name}") }
    }
    (existing.keys - desired).forEach { key ->
        existing.remove(key)?.let(map::removeMarker)
        signatures.remove(key)
    }

    val iconFactory = IconFactory.getInstance(context)
    vehicles.forEach { vehicle ->
        val lat = vehicle.lat ?: return@forEach
        val lon = vehicle.lon ?: return@forEach
        val key = "vehicle:${vehicle.key}"
        val position = LatLng(lat, lon)
        val signature = "${vehicle.busNo}|${vehicle.nodeName}|${vehicle.nodeOrd}|${vehicle.bearing?.toInt()}"
        val marker = existing[key]
        if (marker == null) {
            existing[key] = map.addMarker(
                MarkerOptions()
                    .position(position)
                    .title("${vehicle.busNo}번")
                    .snippet(vehicle.nodeName)
                    .icon(iconFactory.fromBitmap(busMarkerBitmap(vehicle)))
            )
            signatures[key] = signature
        } else {
            marker.position = position
            marker.title = "${vehicle.busNo}번"
            marker.snippet = vehicle.nodeName
            if (signatures[key] != signature) {
                marker.icon = iconFactory.fromBitmap(busMarkerBitmap(vehicle))
                signatures[key] = signature
            }
        }
    }

    landmarks.forEach { landmark ->
        val key = "landmark:${landmark.name}"
        if (existing[key] == null) {
            existing[key] = map.addMarker(
                MarkerOptions()
                    .position(LatLng(landmark.lat, landmark.lon))
                    .title(landmark.name)
                    .icon(iconFactory.fromBitmap(landmarkMarkerBitmap(landmark.name)))
            )
            signatures[key] = landmark.name
        }
    }
}

@Suppress("DEPRECATION")
private fun fitInitialCamera(map: MapLibreMap, points: List<LatLng>) {
    if (points.isEmpty()) return
    if (points.size == 1) {
        map.cameraPosition = org.maplibre.android.camera.CameraPosition.Builder()
            .target(points.first())
            .zoom(14.5)
            .build()
        return
    }
    val bounds = LatLngBounds.fromLatLngs(points)
    map.getCameraForLatLngBounds(bounds, intArrayOf(70, 70, 70, 70))?.let {
        map.cameraPosition = it
    }
}

private fun busMarkerBitmap(vehicle: UiVehicle): Bitmap {
    val width = 220
    val height = 116
    val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    val paint = Paint(Paint.ANTI_ALIAS_FLAG)

    paint.color = Color.WHITE
    paint.setShadowLayer(5f, 0f, 2f, 0x55000000)
    canvas.drawRoundRect(RectF(18f, 58f, 202f, 112f), 16f, 16f, paint)
    paint.clearShadowLayer()

    paint.color = 0xFFD93025.toInt()
    canvas.drawCircle(110f, 38f, 30f, paint)

    paint.color = Color.WHITE
    if (vehicle.bearing != null) {
        canvas.save()
        canvas.rotate(vehicle.bearing.toFloat(), 110f, 38f)
        val arrow = Path().apply {
            moveTo(110f, 17f)
            lineTo(99f, 43f)
            lineTo(106f, 40f)
            lineTo(106f, 57f)
            lineTo(114f, 57f)
            lineTo(114f, 40f)
            lineTo(121f, 43f)
            close()
        }
        canvas.drawPath(arrow, paint)
        canvas.restore()
    } else {
        canvas.drawCircle(110f, 38f, 7f, paint)
    }

    paint.color = Color.rgb(25, 25, 25)
    paint.textAlign = Paint.Align.CENTER
    paint.textSize = 23f
    paint.isFakeBoldText = true
    canvas.drawText(vehicle.busNo, 110f, 80f, paint)
    paint.isFakeBoldText = false
    paint.textSize = 17f
    val stop = vehicle.nodeName.ifBlank { "정류장 ${vehicle.nodeOrd}" }.let {
        if (it.length > 13) it.take(12) + "…" else it
    }
    canvas.drawText(stop, 110f, 103f, paint)
    return bitmap
}

private fun landmarkMarkerBitmap(name: String): Bitmap {
    val bitmap = Bitmap.createBitmap(184, 52, Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    paint.color = Color.WHITE
    canvas.drawRoundRect(RectF(2f, 2f, 182f, 50f), 14f, 14f, paint)
    paint.color = 0xFF1D5FD1.toInt()
    canvas.drawCircle(21f, 26f, 10f, paint)
    paint.color = Color.rgb(35, 35, 35)
    paint.textSize = 15f
    paint.textAlign = Paint.Align.LEFT
    val label = if (name.length > 12) name.take(11) + "…" else name
    canvas.drawText(label, 38f, 31f, paint)
    return bitmap
}
