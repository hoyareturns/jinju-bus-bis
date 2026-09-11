package kr.co.jinjubus.data

import android.content.Context
import android.util.Log
import java.io.File
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.maplibre.android.offline.OfflineManager
import org.maplibre.android.offline.OfflineRegion
import org.maplibre.android.MapLibre
import kr.co.jinjubus.BuildConfig

/** Imports the APK's regional database once; it never downloads a map package. */
object BundledMapStore {
    private val mutex = Mutex()
    private var prepared = false

    suspend fun prepare(context: Context) = mutex.withLock {
        if (prepared) return@withLock
        val app = context.applicationContext
        val prefs = app.getSharedPreferences("bundled_map", Context.MODE_PRIVATE)
        // Before OfflineManager/MapView opens SQLite, seed a fresh install atomically.
        // Existing databases use the public merge API below so upgrades retain other map data.
        // MapLibre 13.6.1's default resource database path (no custom cache path is configured).
        val database = File(app.filesDir, "mbgl-offline.db")
        val seeded = withContext(Dispatchers.IO) {
            if (database.exists()) false else {
                val temporary = File(database.parentFile, "jinju-map-seed.tmp")
                try {
                    app.assets.open("jinju-map.db").use { input -> temporary.outputStream().use(input::copyTo) }
                    check(temporary.renameTo(database)) { "Cannot install bundled map database" }
                    true
                } finally { temporary.delete() }
            }
        }
        val manager = withContext(Dispatchers.Main) {
            MapLibre.getInstance(app)
            // Only the map engine is offline; the separate TAGO OkHttp client stays online.
            MapLibre.setConnected(false)
            OfflineManager.getInstance(app)
        }
        val existing = CompletableDeferred<Boolean>()
        withContext(Dispatchers.Main) {
            manager.listOfflineRegions(object : OfflineManager.ListOfflineRegionsCallback {
                override fun onList(offlineRegions: Array<OfflineRegion>?) { existing.complete(!offlineRegions.isNullOrEmpty()) }
                override fun onError(error: String) { existing.completeExceptionally(IllegalStateException(error)) }
            })
        }
        val hasRegions = existing.await()
        if ((seeded || prefs.getString("version", null) == BuildConfig.OFFLINE_MAP_VERSION) && hasRegions) {
            if (seeded) {
                withContext(Dispatchers.IO) { check(prefs.edit().putString("version", BuildConfig.OFFLINE_MAP_VERSION).commit()) }
                Log.i("BUS_MAP", "Bundled Jinju map installed directly ${BuildConfig.OFFLINE_MAP_VERSION}")
            }
            prepared = true
            return@withLock
        }
        val staged = withContext(Dispatchers.IO) {
            File(app.filesDir, "jinju-map-import.db").also { file ->
                app.assets.open("jinju-map.db").use { input -> file.outputStream().use(input::copyTo) }
            }
        }
        try {
            val imported = CompletableDeferred<Unit>()
            withContext(Dispatchers.Main) {
                manager.mergeOfflineRegions(staged.absolutePath, object : OfflineManager.MergeOfflineRegionsCallback {
                    override fun onMerge(offlineRegions: Array<OfflineRegion>?) {
                        if (offlineRegions.isNullOrEmpty()) imported.completeExceptionally(IllegalStateException("No regional map in package"))
                        else imported.complete(Unit)
                    }
                    override fun onError(error: String) { imported.completeExceptionally(IllegalStateException(error)) }
                })
            }
            imported.await()
            withContext(Dispatchers.IO) { check(prefs.edit().putString("version", BuildConfig.OFFLINE_MAP_VERSION).commit()) }
            prepared = true
            Log.i("BUS_MAP", "Bundled Jinju map installed ${BuildConfig.OFFLINE_MAP_VERSION}")
        } finally {
            withContext(Dispatchers.IO) { staged.delete() }
        }
    }
}
