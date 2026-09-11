import kr.co.jinjubus.core.*

private fun routeSelectionTests() {
    val first = RouteSelectionState.fromPersisted(null, null)
    check(first.monitored == listOf("10"))
    check(first.focused == "10")

    val intentionallyEmpty = RouteSelectionState.fromPersisted(emptyList(), null)
    check(intentionallyEmpty.monitored.isEmpty())
    check(intentionallyEmpty.focused == null)

    val expanded = first.add("160").add("160")
    check(expanded.monitored == listOf("10", "160"))
    check(expanded.remove("10").focused == "160")
    check(expanded.remove("10").remove("160").focused == null)
}

private fun reconciliationTests() {
    val old = mapOf(
        "R10A|V1" to UiVehicle("R10A|V1", "10", "R10A", "V1", 35.0, 128.0, "N1", 1, "A", null, "unknown")
    )
    val fresh = LiveRoute(
        busNo = "10", routeId = "R10A", directionLabel = "B 방면", status = "ok", message = null,
        vehicles = listOf(ApiVehicle("R10A|V1", "V1", 35.1, 128.1, "N2", 2, "B", 90.0, "gps"))
    )
    val updated = reconcileVehicles(old, listOf(fresh))
    check(updated.size == 1)
    check(updated["R10A|V1"]?.lat == 35.1)

    val failed = fresh.copy(status = "error", vehicles = emptyList())
    val retained = reconcileVehicles(old, listOf(failed))
    check(retained == old)

    val emptySuccess = fresh.copy(status = "ok", vehicles = emptyList())
    val cleared = reconcileVehicles(old, listOf(emptySuccess))
    check(cleared.isEmpty())
}

private fun stateReducerTests() {
    val existing = UiVehicle("R10A|V1", "10", "R10A", "V1", 35.0, 128.0, "N1", 1, "A", null, "unknown")
    var state = MainUiState(vehiclesByStableVehicleKey = mapOf(existing.key to existing))
    state = applySelection(state, RouteSelectionState(emptyList(), null))
    check(state.monitoredBusNumbers.isEmpty())
    check(state.vehiclesByStableVehicleKey.isEmpty())

    val selected = applySelection(MainUiState(vehiclesByStableVehicleKey = mapOf(existing.key to existing)), RouteSelectionState(listOf("10"), "10"))
    val failed = applyRefreshFailure(selected)
    check(failed.isUsingStaleData)
    check(!failed.isRefreshing)

    val snapshot = LiveSnapshot(
        fetchedAt = "2026-09-11T12:00:00+09:00",
        routes = listOf(LiveRoute("10", "R10A", null, "ok", null, emptyList())),
        errors = emptyList(),
    )
    val applied = applyLiveSnapshot(selected.copy(isRefreshing = true), snapshot)
    check(applied.fetchedAt == snapshot.fetchedAt)
    check(!applied.isUsingStaleData)
    check(!applied.isRefreshing)
}

fun main() {
    routeSelectionTests()
    reconciliationTests()
    stateReducerTests()
    localBootstrapTests()
    cachedSnapshotTests()
    displayLogicTests()
    metadataReplacementTests()
    cachePolicyTests()
    routeValidationPolicyTests()
    println("logic tests passed")
}

private fun localBootstrapTests() {
    val initial = MainUiState()
    val landmark = Landmark("중앙시장(주차장)", 35.19, 128.08)
    val variant = RouteVariant(
        busNo = "10",
        routeId = "R10A",
        startNodeName = "A",
        endNodeName = "B",
        directionLabel = "B 방면",
        stops = emptyList(),
    )

    val bootstrapped = applyLocalBootstrap(initial, listOf(landmark), listOf(variant))

    check(bootstrapped.landmarks == listOf(landmark))
    check(bootstrapped.routeMetadataByBusNumber["10"] == listOf(variant))
}

private fun cachedSnapshotTests() {
    val snapshot = LiveSnapshot(
        fetchedAt = "2026-09-11T12:00:00+09:00",
        routes = listOf(
            LiveRoute(
                busNo = "10",
                routeId = "R10A",
                directionLabel = "B 방면",
                status = "ok",
                message = null,
                vehicles = listOf(
                    ApiVehicle("R10A|V1", "V1", 35.0, 128.0, "N1", 1, "A", null, "unknown")
                ),
            )
        ),
    )
    val state = applyCachedSnapshot(MainUiState(), snapshot)
    check(state.vehiclesByStableVehicleKey.containsKey("R10A|V1"))
    check(state.fetchedAt == snapshot.fetchedAt)
    check(state.isUsingStaleData)
    check(!state.isRefreshing)
}

private fun displayLogicTests() {
    val now = java.time.OffsetDateTime.parse("2026-09-11T12:00:20+09:00")
    check(freshnessText(null, false, now) == "아직 갱신 전")
    check(freshnessText("2026-09-11T12:00:15+09:00", false, now) == "방금 갱신됨")
    check(freshnessText("2026-09-11T11:59:20+09:00", true, now) == "이전 정보 · 1분 전")

    val stops = (1..10).map { RouteStop("N$it", it, "정류장 $it", null, null) }
    val window = stopWindow(stops, currentOrd = 5, radius = 2)
    check(window.map { it.nodeOrd } == listOf(3, 4, 5, 6, 7))

    check(shouldInitializeMapCamera(cameraInitialized = false, hasContent = true))
    check(!shouldInitializeMapCamera(cameraInitialized = true, hasContent = true))
    check(!shouldInitializeMapCamera(cameraInitialized = false, hasContent = false))
    check(sanitizeRouteNumberInput("140-1") == "140-1")
    check(sanitizeRouteNumberInput(" 200-1a ") == "200-1")
}

private fun metadataReplacementTests() {
    val old10 = RouteVariant("10", "OLD", "A", "B", null, emptyList())
    val old160 = RouteVariant("160", "R160", "C", "D", null, emptyList())
    val fresh10 = RouteVariant("10", "NEW", "A", "C", null, emptyList())
    val state = MainUiState(
        monitoredBusNumbers = listOf("10", "160"),
        focusedBusNumber = "10",
        routeMetadataByBusNumber = mapOf("10" to listOf(old10), "160" to listOf(old160)),
    )

    val replaced = replaceRouteMetadata(state, requestedBusNumbers = listOf("10"), variants = listOf(fresh10))

    check(replaced.routeMetadataByBusNumber["10"] == listOf(fresh10))
    check(replaced.routeMetadataByBusNumber["160"] == listOf(old160))

    val oldA = RouteVariant("10", "R10A", "A", "B", null, emptyList())
    val oldB = RouteVariant("10", "R10B", "B", "A", null, emptyList())
    val freshA = RouteVariant("10", "R10A", "A", "C", "C 방면", emptyList())
    val partialState = state.copy(routeMetadataByBusNumber = mapOf("10" to listOf(oldA, oldB)))
    val merged = mergeRouteMetadataWithErrors(
        partialState,
        requestedBusNumbers = listOf("10"),
        variants = listOf(freshA),
        errors = listOf(RouteError("10", "R10B", "정류장 조회 실패")),
    )
    check(merged.routeMetadataByBusNumber["10"] == listOf(freshA, oldB))
}

private fun cachePolicyTests() {
    val ok = LiveSnapshot(
        fetchedAt = "now",
        routes = listOf(LiveRoute("10", "R10", null, "ok", null, emptyList())),
    )
    check(shouldPersistAsLastSuccessful(ok))
    check(!shouldPersistAsLastSuccessful(ok.copy(errors = listOf(RouteError("10", "R10", "fail")))))
    check(!shouldPersistAsLastSuccessful(ok.copy(routes = listOf(LiveRoute("10", "R10", null, "error", "fail", emptyList())))))
}

private fun routeValidationPolicyTests() {
    check(decideRouteValidation(localExists = true, remoteSucceeded = true, remoteHasRoutes = true, remoteConfirmsUnknown = false) == RouteValidationDecision.ACCEPT)
    check(decideRouteValidation(localExists = true, remoteSucceeded = true, remoteHasRoutes = false, remoteConfirmsUnknown = true) == RouteValidationDecision.REJECT_UNKNOWN)
    check(decideRouteValidation(localExists = true, remoteSucceeded = true, remoteHasRoutes = false, remoteConfirmsUnknown = false) == RouteValidationDecision.ACCEPT_OFFLINE_SNAPSHOT)
    check(decideRouteValidation(localExists = true, remoteSucceeded = false, remoteHasRoutes = false, remoteConfirmsUnknown = false) == RouteValidationDecision.ACCEPT_OFFLINE_SNAPSHOT)
    check(decideRouteValidation(localExists = false, remoteSucceeded = false, remoteHasRoutes = false, remoteConfirmsUnknown = false) == RouteValidationDecision.REJECT_UNAVAILABLE)
}
