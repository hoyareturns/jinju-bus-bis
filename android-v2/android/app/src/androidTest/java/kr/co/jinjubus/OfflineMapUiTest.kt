package kr.co.jinjubus

import android.graphics.Bitmap
import android.util.Log
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Explicit test on a freshly cleared emulator app profile with Wi-Fi/data disabled. */
@RunWith(AndroidJUnit4::class)
class OfflineMapUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun firstLaunchRendersBundledMapWithoutNetwork() {
        compose.waitUntil(240_000) {
            compose.onAllNodesWithContentDescription("진주 지도").fetchSemanticsNodes().isNotEmpty()
        }
        compose.onNodeWithContentDescription("진주 지도").assertIsDisplayed()
        assertEquals(BuildConfig.OFFLINE_MAP_VERSION,
            compose.activity.getSharedPreferences("bundled_map", 0).getString("version", null))
        val bitmap = InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot()
        assertNotNull(bitmap)
        File(compose.activity.getExternalFilesDir(null), "offline-first-install-map.png").outputStream().use {
            bitmap!!.compress(Bitmap.CompressFormat.PNG, 100, it)
        }
        bitmap!!.recycle()
        Log.i("TAGO_TEST", "Fresh installation: bundled Jinju map rendered without network PASS")
    }
}
