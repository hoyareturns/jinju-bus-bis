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

/** Opt-in device test: calls the official TAGO service with the actual build key. */
@RunWith(AndroidJUnit4::class)
class LiveTagoUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val vm get() = ViewModelProvider(compose.activity)[MainViewModel::class.java]

    @Test fun realDataSelectionPersistenceAndCache() {
        assertTrue(BuildConfig.TAGO_API_KEY.isNotBlank())
        val expectedTen = setOf("JJB381101010", "JJB381101020", "JJB381001010", "JJB381001020")
        compose.waitUntil(240_000) {
            val state = vm.state.value
            state.fetchedAt != null && !state.isUsingStaleData && !state.isRefreshing && state.routeErrors.isEmpty() &&
                state.routeMetadataByBusNumber["10"].orEmpty().map { it.routeId }.toSet() == expectedTen &&
                state.confirmedRouteIdsByBusNumber["10"].orEmpty().containsAll(expectedTen)
        }
        assertEquals(listOf("10"), vm.state.value.monitoredBusNumbers)
        val ids = vm.state.value.routeMetadataByBusNumber["10"].orEmpty().map { it.routeId }.toSet()
        assertEquals(expectedTen, ids)
        compose.onNodeWithText("10 번").assertIsDisplayed()
        waitForMap()
        assertEquals(false, org.maplibre.android.MapLibre.isConnected())
        Log.i("TAGO_TEST", "10 API/UI PASS ids=$ids vehicles=${vm.state.value.vehiclesByStableVehicleKey.size}")
        screenshot("10-live")

        addThroughUi("160")
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("160 번").assertIsDisplayed()
        waitForMap()
        val vehicles = vm.state.value.vehiclesByStableVehicleKey.values.filter { it.busNo == "160" }
        Log.i("TAGO_TEST", "160 API/UI PASS vehicles=${vehicles.size} gps=${vehicles.count { it.lat != null }} nodes=${vehicles.map { it.nodeName }}")
        screenshot("160-live")
        val prefs = RoutePreferences(compose.activity.applicationContext)
        runBlocking {
            assertEquals(listOf("10", "160"), prefs.currentSelection().monitored)
            assertNotNull(prefs.loadLive())
            Log.i("TAGO_TEST", "Selection and real response disk cache PASS")
        }

        deleteThroughUi("160")
        deleteThroughUi("10")
        compose.onNodeWithText("표시할 버스가 없습니다.").assertIsDisplayed()
        compose.waitUntil(30_000) { runBlocking { prefs.currentSelection().monitored.isEmpty() } }
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("표시할 버스가 없습니다.").assertIsDisplayed()
        Log.i("TAGO_TEST", "Delete 160, delete default 10, persist empty selection PASS")
        screenshot("empty-selection")

        addThroughUi("10")
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText("10 번").assertIsDisplayed()
        compose.waitUntil(30_000) { runBlocking { prefs.currentSelection().monitored == listOf("10") } }
        Log.i("TAGO_TEST", "Restore 10 selection PASS")
    }

    private fun addThroughUi(number: String) {
        compose.onNodeWithText("+").performClick()
        compose.onNode(hasSetTextAction()).performTextInput(number)
        // The empty-state action remains behind the sheet; the sheet action is the last node.
        compose.onAllNodesWithText("+ 노선 추가").onLast().performClick()
        compose.waitUntil(240_000) {
            val state = vm.state.value
            val expectedIds = state.routeMetadataByBusNumber[number].orEmpty().map { it.routeId }
            number in state.monitoredBusNumbers && state.focusedBusNumber == number &&
                expectedIds.isNotEmpty() && state.confirmedRouteIdsByBusNumber[number].orEmpty().containsAll(expectedIds) &&
                !state.isRefreshing && state.routeErrors.isEmpty()
        }
    }

    private fun deleteThroughUi(number: String) {
        compose.onNode(hasText(number) and hasClickAction()).performTouchInput { longClick() }
        compose.onNodeWithText("삭제").performClick()
        compose.waitUntil(30_000) { number !in vm.state.value.monitoredBusNumbers }
    }

    private fun waitForMap() {
        compose.waitUntil(240_000) {
            compose.onAllNodesWithContentDescription("진주 지도").fetchSemanticsNodes().isNotEmpty()
        }
    }

    private fun screenshot(name: String) {
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val image = instrumentation.uiAutomation.takeScreenshot() ?: return
        val file = File(compose.activity.getExternalFilesDir(null), "$name.png")
        file.outputStream().use { image.compress(Bitmap.CompressFormat.PNG, 100, it) }
        image.recycle()
    }
}
