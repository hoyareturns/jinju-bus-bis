package kr.co.jinjubus.data

import kotlinx.coroutines.runBlocking
import kr.co.jinjubus.BuildConfig
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Explicit host-side check of the exact Android API adapter; not a device/UI test. */
class LiveTagoIntegrationTest {
    @Test fun actualBuildKeyAndAndroidAdapterReceiveJinjuData() = runBlocking {
        assumeTrue(System.getenv("TAGO_LIVE_CHECK") == "true")
        assertTrue(BuildConfig.TAGO_API_KEY.isNotBlank())
        val api = BusApi(BuildConfig.TAGO_API_KEY, log = ::println)
        api.setMonitoredBusNumbers(listOf("10", "160"))
        val metadata = api.routes(listOf("10", "160"))
        assertTrue("Metadata errors: ${metadata.errors}", metadata.errors.isEmpty())
        val live = api.locations(listOf("10", "160"))
        assertTrue("Live errors: ${live.errors}", live.errors.isEmpty())
        assertEquals(setOf("JJB381101010", "JJB381101020", "JJB381001010", "JJB381001020"),
            live.routes.filter { it.busNo == "10" }.map { it.routeId }.toSet())
        assertTrue(live.routes.all { it.status == "ok" })
        for (route in live.routes) {
            for (vehicle in route.vehicles) {
                println("ACTUAL bus=${route.busNo} routeId=${route.routeId} vehicle=${vehicle.vehicleNo} gps=${vehicle.lat},${vehicle.lon} node=${vehicle.nodeName}")
            }
        }
        api.setMonitoredBusNumbers(emptyList())
        assertTrue(api.locations(listOf("10", "160")).routes.isEmpty())
    }
}
