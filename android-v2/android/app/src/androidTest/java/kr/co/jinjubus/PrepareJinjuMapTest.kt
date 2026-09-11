package kr.co.jinjubus

import android.util.Log
import java.io.File
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.maplibre.android.MapLibre
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.offline.*
import org.maplibre.android.storage.FileSource

/** Explicit build-time tool. Never downloads an offline region during normal app use. */
@RunWith(AndroidJUnit4::class)
class PrepareJinjuMapTest {
    @Test fun prepareRegionalDatabaseForBundling() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val done = CountDownLatch(1)
        val failure = AtomicReference<String?>(null)
        instrumentation.runOnMainSync {
            MapLibre.getInstance(context)
            val manager = OfflineManager.getInstance(context)
            val definition = OfflineTilePyramidRegionDefinition(
                BuildConfig.MAP_STYLE_URL,
                LatLngBounds.from(35.47, 128.46, 35.03, 127.87),
                7.0, 14.0, 2f, true,
            )
            manager.createOfflineRegion(definition, "Jinju 2026-09-11 z7-14".toByteArray(),
                object : OfflineManager.CreateOfflineRegionCallback {
                    override fun onError(error: String) { failure.set(error); done.countDown() }
                    override fun onCreate(region: OfflineRegion) {
                        var lastLogged = -100L
                        var completed = false
                        region.setObserver(object : OfflineRegion.OfflineRegionObserver {
                            override fun onStatusChanged(status: OfflineRegionStatus) {
                                if (status.completedResourceCount - lastLogged >= 100 || status.isComplete) {
                                    Log.i("MAP_PACKAGE", "resources=${status.completedResourceCount}/${status.requiredResourceCount} tiles=${status.completedTileCount} bytes=${status.completedResourceSize} complete=${status.isComplete}")
                                    lastLogged = status.completedResourceCount
                                }
                                if (status.isComplete && !completed) {
                                    completed = true
                                    region.setDownloadState(OfflineRegion.STATE_INACTIVE)
                                    manager.packDatabase(object : OfflineManager.FileSourceCallback {
                                        override fun onSuccess() {
                                            Log.i("MAP_PACKAGE", "READY path=${FileSource.getResourcesCachePath(context)}")
                                            done.countDown()
                                        }
                                        override fun onError(message: String) { failure.set(message); done.countDown() }
                                    })
                                }
                            }
                            override fun onError(error: OfflineRegionError) {
                                Log.w("MAP_PACKAGE", "Download retry: ${error.reason} ${error.message}")
                            }
                            override fun mapboxTileCountLimitExceeded(limit: Long) {
                                failure.set("Tile limit $limit"); done.countDown()
                            }
                        })
                        region.setDownloadState(OfflineRegion.STATE_ACTIVE)
                    }
                })
        }
        assertTrue("Regional map download timed out", done.await(25, TimeUnit.MINUTES))
        assertNull(failure.get())
        // Export the completed, inactive database without requiring a rooted test device.
        val exported = File(context.getExternalFilesDir(null), "jinju-map.db")
        File(FileSource.getResourcesCachePath(context), "mbgl-offline.db").copyTo(exported, overwrite = true)
        Log.i("MAP_PACKAGE", "EXPORT ${exported.absolutePath} bytes=${exported.length()}")
    }
}
