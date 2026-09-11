package kr.co.jinjubus.data

import org.junit.Assert.*
import org.junit.Test

class SuccessfulCacheTest {
    @Test fun partialSuccessUpdatesGoodRouteAndKeepsFailedRoutesLastVehicle() {
        val vehicle = ApiVehicleDto("B|V", "V", 35.0, 128.0, nodeOrd = 1)
        val old = LiveResponseDto("old", listOf(
            LiveRouteDto("10", "A", status = "ok"),
            LiveRouteDto("10", "B", status = "ok", vehicles = listOf(vehicle))))
        val freshVehicle = vehicle.copy(key = "A|NEW", vehicleNo = "NEW")
        val fresh = LiveResponseDto("new", listOf(
            LiveRouteDto("10", "A", status = "ok", vehicles = listOf(freshVehicle)),
            LiveRouteDto("10", "B", status = "error")))
        val merged = mergeSuccessfulCache(old, fresh)
        assertEquals(listOf(vehicle), merged.routes.single { it.routeId == "B" }.vehicles)
        assertEquals(listOf(freshVehicle), merged.routes.single { it.routeId == "A" }.vehicles)
        assertEquals("old", merged.fetchedAt)
        val emptySuccess = mergeSuccessfulCache(merged, fresh.copy(routes = listOf(LiveRouteDto("10", "B", status = "ok"))))
        assertTrue(emptySuccess.routes.single { it.routeId == "B" }.vehicles.isEmpty())
    }
}
