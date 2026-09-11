package kr.co.jinjubus.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class VehicleReconciliationTest {
    private val old = mapOf(
        "R10A|V1" to UiVehicle("R10A|V1", "10", "R10A", "V1", 35.0, 128.0, "N1", 1, "A", null, "unknown")
    )

    @Test fun successfulVariantReplacesItsVehiclesByStableKey() {
        val route = LiveRoute("10", "R10A", null, "ok", null,
            listOf(ApiVehicle("R10A|V1", "V1", 35.1, 128.1, "N2", 2, "B", 90.0, "gps")))
        val result = reconcileVehicles(old, listOf(route))
        assertEquals(35.1, result["R10A|V1"]!!.lat!!, 0.0)
    }

    @Test fun failedVariantRetainsPreviousVehicles() {
        val failed = LiveRoute("10", "R10A", null, "error", "failed", emptyList())
        assertEquals(old, reconcileVehicles(old, listOf(failed)))
    }

    @Test fun successfulEmptyVariantClearsPreviousVehicles() {
        val empty = LiveRoute("10", "R10A", null, "ok", "현재 조회되는 차량 없음", emptyList())
        assertTrue(reconcileVehicles(old, listOf(empty)).isEmpty())
    }
}
