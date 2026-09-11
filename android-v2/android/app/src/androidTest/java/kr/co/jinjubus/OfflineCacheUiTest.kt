package kr.co.jinjubus

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import kotlinx.coroutines.runBlocking
import kr.co.jinjubus.data.RoutePreferences
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Run explicitly after LiveTagoUiTest, with emulator networking disabled and app force-stopped. */
@RunWith(AndroidJUnit4::class)
class OfflineCacheUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun restoresActualDiskResponseBeforeNetwork() {
        val vm = ViewModelProvider(compose.activity)[MainViewModel::class.java]
        val prefs = RoutePreferences(compose.activity.applicationContext)
        val stored = runBlocking { prefs.loadLive() }
        assertNotNull("Run the live test first to populate actual TAGO data", stored)
        compose.waitUntil(120_000) {
            vm.state.value.isUsingStaleData && vm.state.value.fetchedAt != null
        }
        assertEquals(listOf("10"), vm.state.value.monitoredBusNumbers)
        assertEquals(stored!!.fetchedAt, vm.state.value.fetchedAt)
        assertEquals(4, vm.state.value.routeMetadataByBusNumber["10"].orEmpty().size)
        compose.onNodeWithText("10 번").assertIsDisplayed()
        compose.onAllNodesWithText("이전 정보", substring = true).onFirst().assertIsDisplayed()
        compose.waitUntil(240_000) {
            compose.onAllNodesWithContentDescription("진주 지도").fetchSemanticsNodes().isNotEmpty()
        }
        Log.i("TAGO_TEST", "Offline process restart: persisted selection and actual cache restored PASS")
        val bitmap = InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
        assertNotNull(bitmap)
        File(compose.activity.getExternalFilesDir(null), "offline-cache.png").outputStream().use {
            bitmap!!.compress(Bitmap.CompressFormat.PNG, 100, it)
        }
        bitmap!!.recycle()
    }
}
