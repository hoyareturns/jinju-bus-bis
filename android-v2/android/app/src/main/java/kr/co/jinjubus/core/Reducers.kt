package kr.co.jinjubus.core

fun applySelection(state: MainUiState, selection: RouteSelectionState): MainUiState {
    return state.copy(
        monitoredBusNumbers = selection.monitored,
        focusedBusNumber = selection.focused,
        vehiclesByStableVehicleKey = filterVehiclesForMonitored(
            state.vehiclesByStableVehicleKey,
            selection.monitored,
        ),
        routeMetadataByBusNumber = state.routeMetadataByBusNumber.filterKeys { it in selection.monitored },
        routeErrors = state.routeErrors.filter { it.busNo in selection.monitored },
        confirmedRouteIdsByBusNumber = state.confirmedRouteIdsByBusNumber.filterKeys { it in selection.monitored },
    )
}

fun applyRefreshStarted(state: MainUiState): MainUiState = state.copy(isRefreshing = true)

fun applyRefreshFailure(
    state: MainUiState,
    message: String = "실시간 정보를 불러오지 못했습니다. 다시 갱신해 주세요.",
): MainUiState = state.copy(
    isRefreshing = false,
    isUsingStaleData = state.vehiclesByStableVehicleKey.isNotEmpty() || state.fetchedAt != null,
    routeErrors = state.monitoredBusNumbers.map { RouteError(it, null, message) },
    vehiclesByStableVehicleKey = state.vehiclesByStableVehicleKey.mapValues { (_, vehicle) ->
        vehicle.copy(bearing = null, bearingSource = "unknown")
    },
)

fun applyLiveSnapshot(state: MainUiState, snapshot: LiveSnapshot): MainUiState {
    val previous = state.vehiclesByStableVehicleKey.mapValues { (_, vehicle) ->
        vehicle.copy(bearing = null, bearingSource = "unknown")
    }
    val activeRoutes = snapshot.routes.filter { it.busNo in state.monitoredBusNumbers }
    val nextVehicles = reconcileVehicles(previous, activeRoutes)
    val anyVariantFailed = activeRoutes.any { it.status != "ok" } || snapshot.errors.any { it.busNo in state.monitoredBusNumbers }
    val confirmed = state.confirmedRouteIdsByBusNumber.toMutableMap()
    activeRoutes.filter { it.status == "ok" }.groupBy { it.busNo }.forEach { (bus, routes) ->
        confirmed[bus] = confirmed[bus].orEmpty() + routes.map { it.routeId }
    }
    return state.copy(
        vehiclesByStableVehicleKey = filterVehiclesForMonitored(nextVehicles, state.monitoredBusNumbers),
        fetchedAt = when {
            anyVariantFailed && state.fetchedAt != null -> state.fetchedAt
            activeRoutes.any { it.status == "ok" } -> snapshot.fetchedAt
            else -> state.fetchedAt
        },
        confirmedRouteIdsByBusNumber = confirmed,
        isRefreshing = false,
        routeErrors = (snapshot.errors + snapshot.routes.filter { it.status != "ok" }.map {
            RouteError(it.busNo, it.routeId, it.message ?: "실시간 위치 조회 실패")
        }).filter { it.busNo in state.monitoredBusNumbers }.distinct(),
        isUsingStaleData = anyVariantFailed,
    )
}

fun applyRouteMetadata(state: MainUiState, variants: List<RouteVariant>): MainUiState {
    val grouped = variants.groupBy { it.busNo }
    return state.copy(
        routeMetadataByBusNumber = state.routeMetadataByBusNumber + grouped,
    )
}

fun applyLocalBootstrap(
    state: MainUiState,
    landmarks: List<Landmark>,
    variants: List<RouteVariant>,
): MainUiState = applyRouteMetadata(state.copy(landmarks = landmarks), variants)

fun applyCachedSnapshot(state: MainUiState, snapshot: LiveSnapshot): MainUiState {
    val applied = applyLiveSnapshot(state, snapshot)
    return applied.copy(isUsingStaleData = true, isRefreshing = false,
        vehiclesByStableVehicleKey = applied.vehiclesByStableVehicleKey.mapValues { (_, vehicle) ->
            vehicle.copy(bearing = null, bearingSource = "unknown")
        })
}

fun replaceRouteMetadata(
    state: MainUiState,
    requestedBusNumbers: Collection<String>,
    variants: List<RouteVariant>,
): MainUiState {
    val requested = requestedBusNumbers.toSet()
    val retained = state.routeMetadataByBusNumber.filterKeys { it !in requested }
    val replacement = variants.groupBy { it.busNo }.filterKeys { it in requested }
    return state.copy(routeMetadataByBusNumber = retained + replacement)
}

fun mergeRouteMetadataWithErrors(
    state: MainUiState,
    requestedBusNumbers: Collection<String>,
    variants: List<RouteVariant>,
    errors: List<RouteError>,
): MainUiState {
    val requested = requestedBusNumbers.toSet()
    val freshByBus = variants.filter { it.busNo in requested }.groupBy { it.busNo }
    val errorsByBus = errors.filter { it.busNo in requested }.groupBy { it.busNo }
    val next = state.routeMetadataByBusNumber.toMutableMap()

    for (busNo in requested) {
        val fresh = freshByBus[busNo].orEmpty()
        val busErrors = errorsByBus[busNo].orEmpty()
        if (busErrors.isEmpty()) {
            if (fresh.isEmpty()) next.remove(busNo) else next[busNo] = fresh
            continue
        }

        val existing = state.routeMetadataByBusNumber[busNo].orEmpty()
        val freshRouteIds = fresh.mapTo(mutableSetOf()) { it.routeId }
        val hasBusLevelError = busErrors.any { it.routeId == null }
        val failedRouteIds = busErrors.mapNotNullTo(mutableSetOf()) { it.routeId }
        val retainedFailures = existing.filter { variant ->
            variant.routeId !in freshRouteIds &&
                (hasBusLevelError || variant.routeId in failedRouteIds)
        }
        val merged = fresh + retainedFailures
        if (merged.isEmpty()) next.remove(busNo) else next[busNo] = merged
    }

    return state.copy(routeMetadataByBusNumber = next)
}

fun shouldPersistAsLastSuccessful(snapshot: LiveSnapshot): Boolean =
    snapshot.errors.isEmpty() && snapshot.routes.all { it.status == "ok" }

enum class RouteValidationDecision {
    ACCEPT,
    ACCEPT_OFFLINE_SNAPSHOT,
    REJECT_UNKNOWN,
    REJECT_UNAVAILABLE,
}

fun decideRouteValidation(
    localExists: Boolean,
    remoteSucceeded: Boolean,
    remoteHasRoutes: Boolean,
    remoteConfirmsUnknown: Boolean,
): RouteValidationDecision = when {
    remoteSucceeded && remoteHasRoutes -> RouteValidationDecision.ACCEPT
    remoteSucceeded && remoteConfirmsUnknown -> RouteValidationDecision.REJECT_UNKNOWN
    localExists -> RouteValidationDecision.ACCEPT_OFFLINE_SNAPSHOT
    else -> RouteValidationDecision.REJECT_UNAVAILABLE
}
