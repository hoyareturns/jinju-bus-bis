package kr.co.jinjubus.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kr.co.jinjubus.core.MainUiState
import kr.co.jinjubus.core.RouteStop
import kr.co.jinjubus.core.RouteVariant
import kr.co.jinjubus.core.UiVehicle
import kr.co.jinjubus.core.freshnessText
import kr.co.jinjubus.core.stopWindow

@Composable
fun RouteDetailPanel(
    state: MainUiState,
    onAddRoute: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val focused = state.focusedBusNumber
    if (focused == null) {
        Box(modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("표시할 버스가 없습니다.", style = MaterialTheme.typography.titleMedium)
                Button(onClick = onAddRoute) { Text("+ 노선 추가") }
            }
        }
        return
    }

    val variants = state.routeMetadataByBusNumber[focused].orEmpty()
    val vehicles = state.vehiclesByStableVehicleKey.values.filter { it.busNo == focused }
    val focusedErrors = state.routeErrors.filter { it.busNo == focused }
    val confirmedRoutes = state.confirmedRouteIdsByBusNumber[focused].orEmpty()
    LazyColumn(
        modifier = modifier.padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("$focused 번", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Column(modifier = Modifier.padding(start = 8.dp)) {
                    Text(
                        when {
                            confirmedRoutes.isEmpty() && focusedErrors.isEmpty() -> "운행 정보 확인 전"
                            vehicles.isEmpty() && focusedErrors.isNotEmpty() -> "운행 정보 확인 불가"
                            else -> "운행 ${vehicles.size}대"
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        freshnessText(state.fetchedAt, state.isUsingStaleData),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        if (variants.isEmpty()) {
            item { Text("노선 정보를 불러오는 중입니다.", modifier = Modifier.padding(vertical = 20.dp)) }
        } else {
            items(
                variants.sortedByDescending { variant -> vehicles.any { it.routeId == variant.routeId } },
                key = { it.routeId },
            ) { variant ->
                RouteVariantCard(
                    variant,
                    vehicles.filter { it.routeId == variant.routeId },
                    hasLiveData = variant.routeId in confirmedRoutes,
                    hasError = focusedErrors.any { it.routeId == null || it.routeId == variant.routeId },
                )
            }
        }

        state.routeErrors.filter { it.busNo == focused }.takeIf { it.isNotEmpty() }?.let { errors ->
            item {
                Text(
                    if (state.fetchedAt == null) errors.first().message
                    else "일부 실시간 정보를 갱신하지 못해 이전 위치를 유지하고 있습니다.",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(vertical = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun RouteVariantCard(
    variant: RouteVariant,
    vehicles: List<UiVehicle>,
    hasLiveData: Boolean,
    hasError: Boolean,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                variant.directionLabel ?: "${variant.endNodeName} 방면",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            if (vehicles.isEmpty()) {
                Text(
                    when {
                        hasError -> "실시간 정보를 불러오지 못했습니다."
                        !hasLiveData -> "실시간 정보 확인 전"
                        else -> "현재 조회되는 차량 없음"
                    },
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                vehicles.sortedBy { it.nodeOrd }.forEach { vehicle ->
                    VehicleProgress(vehicle, variant.stops)
                }
            }
        }
    }
}

@Composable
private fun VehicleProgress(vehicle: UiVehicle, stops: List<RouteStop>) {
    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text(
            if (vehicle.lat == null || vehicle.lon == null) "${vehicle.vehicleNo} · GPS 좌표 미제공" else vehicle.vehicleNo,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.error)
                    .padding(horizontal = 8.dp, vertical = 3.dp)
            ) {
                Text(vehicle.busNo, color = MaterialTheme.colorScheme.onError, style = MaterialTheme.typography.labelMedium)
            }
            Text(
                vehicle.nodeName.ifBlank { if (vehicle.nodeOrd >= 0) "정류장 ${vehicle.nodeOrd}" else "현재 정류장 정보 없음" },
                modifier = Modifier.padding(start = 8.dp),
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        if (vehicle.nodeOrd >= 0) StopStrip(stops, vehicle.nodeOrd)
    }
}

@Composable
private fun StopStrip(stops: List<RouteStop>, currentOrd: Int) {
    val visible = stopWindow(stops, currentOrd, radius = 3)
    val listState = rememberLazyListState()
    val currentIndex = visible.indexOfFirst { it.nodeOrd == currentOrd }.coerceAtLeast(0)
    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val density = LocalDensity.current
        val centerOffsetPx = with(density) { -((maxWidth - 94.dp) / 2).roundToPx() }
        LaunchedEffect(currentOrd, visible.size, centerOffsetPx) {
            if (visible.isNotEmpty()) listState.animateScrollToItem(currentIndex, centerOffsetPx)
        }
        LazyRow(
            state = listState,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier.fillMaxWidth(),
        ) {
            items(visible, key = { "${it.nodeId}:${it.nodeOrd}" }) { stop ->
                val isCurrent = stop.nodeOrd == currentOrd
                val isPast = stop.nodeOrd < currentOrd
                Column(
                    modifier = Modifier
                        .width(94.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(
                            when {
                                isCurrent -> MaterialTheme.colorScheme.primaryContainer
                                isPast -> MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f)
                                else -> MaterialTheme.colorScheme.surfaceVariant
                            }
                        )
                        .padding(8.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Text(
                        if (isCurrent) "●" else "○",
                        color = if (isCurrent) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        stop.nodeName,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isPast) MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.55f) else MaterialTheme.colorScheme.onSurface,
                    )
                }
            }
        }
    }
}
