package kr.co.jinjubus.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertNull
import org.junit.Test

class ReducersTest {
    @Test fun newRouteIsUnconfirmedUntilItsOwnResponseArrivesAndPartialFailureKeepsOldAge() {
        val initial = MainUiState(monitoredBusNumbers = listOf("10", "160"))
        val old = applyLiveSnapshot(initial, LiveSnapshot("old", listOf(LiveRoute("10", "R10", null, "ok", null, emptyList()))))
        assertTrue(old.confirmedRouteIdsByBusNumber["160"].isNullOrEmpty())
        val partial = applyLiveSnapshot(old, LiveSnapshot("new", listOf(
            LiveRoute("10", "R10", null, "error", "network", emptyList()),
            LiveRoute("160", "R160", null, "ok", null, emptyList()))))
        assertEquals(setOf("R160"), partial.confirmedRouteIdsByBusNumber["160"])
        assertEquals("old", partial.fetchedAt)
        assertTrue(applySelection(partial, RouteSelectionState(emptyList(), null)).confirmedRouteIdsByBusNumber.isEmpty())
    }
    @Test fun cachedAndFailedDirectionsAreHiddenWhileCoordinatesAreRetained() {
        val route = LiveRoute("10", "R", null, "ok", null,
            listOf(ApiVehicle("R|V", "V", 35.0, 128.0, "N", 1, "Stop", 45.0, "gps")))
        val snapshot = LiveSnapshot("2020-01-01T00:00:00Z", listOf(route))
        val cached = applyCachedSnapshot(MainUiState(), snapshot)
        assertNull(cached.vehiclesByStableVehicleKey.getValue("R|V").bearing)
        assertEquals(35.0, cached.vehiclesByStableVehicleKey.getValue("R|V").lat!!, 0.0)
        val live = applyLiveSnapshot(MainUiState(), snapshot)
        assertNull(applyRefreshFailure(live).vehiclesByStableVehicleKey.getValue("R|V").bearing)
        val partial = applyLiveSnapshot(live, snapshot.copy(routes = listOf(route.copy(status = "error", vehicles = emptyList()))))
        assertNull(partial.vehiclesByStableVehicleKey.getValue("R|V").bearing)
    }
    @Test fun firstRefreshFailureIsReportedForEveryMonitoredRoute() {
        val state = MainUiState(monitoredBusNumbers = listOf("10", "160"))
        val failed = applyRefreshFailure(state)
        assertEquals(listOf("10", "160"), failed.routeErrors.map { it.busNo })
        assertTrue(failed.routeErrors.all { it.routeId == null && it.message.isNotBlank() })
        assertNull(failed.fetchedAt)
    }

    @Test fun successfulEmptyResponseClearsPreviousConnectionErrors() {
        val failed = applyRefreshFailure(MainUiState())
        val recovered = applyLiveSnapshot(failed, LiveSnapshot(
            "2026-09-11T20:00:00+09:00",
            listOf(LiveRoute("10", "R10A", null, "ok", null, emptyList())),
        ))
        assertTrue(recovered.routeErrors.isEmpty())
        assertEquals("2026-09-11T20:00:00+09:00", recovered.fetchedAt)
    }

    @Test fun failedRefreshRetainsLastKnownVehicleAndReportsError() {
        val vehicle = UiVehicle("R10A|V1", "10", "R10A", "V1", 35.0, 128.0, "N1", 1, "A", null, "unknown")
        val state = MainUiState(
            fetchedAt = "2026-09-11T20:00:00+09:00",
            vehiclesByStableVehicleKey = mapOf(vehicle.key to vehicle),
        )
        val failed = applyRefreshFailure(state)
        assertEquals(state.vehiclesByStableVehicleKey, failed.vehiclesByStableVehicleKey)
        assertEquals(state.fetchedAt, failed.fetchedAt)
        assertTrue(failed.isUsingStaleData)
        assertTrue(failed.routeErrors.isNotEmpty())
    }

    @Test fun cachedSnapshotIsMarkedStaleUntilRefreshSucceeds() {
        val snapshot = LiveSnapshot(
            fetchedAt = "2026-09-11T12:00:00+09:00",
            routes = listOf(
                LiveRoute(
                    "10", "R10A", null, "ok", null,
                    listOf(ApiVehicle("R10A|V1", "V1", 35.0, 128.0, "N1", 1, "A", null, "unknown")),
                )
            ),
        )
        val state = applyCachedSnapshot(MainUiState(), snapshot)
        assertTrue(state.isUsingStaleData)
        assertEquals(snapshot.fetchedAt, state.fetchedAt)
    }

    @Test fun remoteMetadataReplacesOnlyRequestedBusNumbers() {
        val old10 = RouteVariant("10", "OLD", "A", "B", null, emptyList())
        val old160 = RouteVariant("160", "R160", "C", "D", null, emptyList())
        val fresh10 = RouteVariant("10", "NEW", "A", "C", null, emptyList())
        val state = MainUiState(
            monitoredBusNumbers = listOf("10", "160"),
            routeMetadataByBusNumber = mapOf("10" to listOf(old10), "160" to listOf(old160)),
        )
        val next = replaceRouteMetadata(state, listOf("10"), listOf(fresh10))
        assertEquals(listOf(fresh10), next.routeMetadataByBusNumber["10"])
        assertEquals(listOf(old160), next.routeMetadataByBusNumber["160"])
    }
    @Test fun partialMetadataFailureKeepsFailedVariantWhileUpdatingSuccessfulVariant() {
        val oldA = RouteVariant("10", "R10A", "A", "B", null, emptyList())
        val oldB = RouteVariant("10", "R10B", "B", "A", null, emptyList())
        val freshA = RouteVariant("10", "R10A", "A", "C", "C 방면", emptyList())
        val state = MainUiState(
            monitoredBusNumbers = listOf("10"),
            routeMetadataByBusNumber = mapOf("10" to listOf(oldA, oldB)),
        )

        val next = mergeRouteMetadataWithErrors(
            state,
            requestedBusNumbers = listOf("10"),
            variants = listOf(freshA),
            errors = listOf(RouteError("10", "R10B", "정류장 조회 실패")),
        )

        assertEquals(listOf(freshA, oldB), next.routeMetadataByBusNumber["10"])
    }

}
