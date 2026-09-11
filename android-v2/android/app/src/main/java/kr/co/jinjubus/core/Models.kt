package kr.co.jinjubus.core

data class RouteSelectionState(
    val monitored: List<String>,
    val focused: String?,
) {
    companion object {
        fun fromPersisted(monitored: List<String>?, focused: String?): RouteSelectionState {
            val normalized = if (monitored == null) listOf("10") else normalize(monitored)
            val validFocus = focused?.takeIf { it in normalized } ?: normalized.firstOrNull()
            return RouteSelectionState(normalized, validFocus)
        }

        private fun normalize(values: List<String>): List<String> =
            values.asSequence().map(String::trim).filter(String::isNotEmpty).distinct().toList()
    }

    fun add(busNo: String): RouteSelectionState {
        val value = busNo.trim()
        if (value.isEmpty() || value in monitored) return this
        val next = monitored + value
        return copy(monitored = next, focused = focused ?: value)
    }

    fun remove(busNo: String): RouteSelectionState {
        val next = monitored.filterNot { it == busNo }
        val nextFocus = when {
            focused != busNo && focused in next -> focused
            else -> next.firstOrNull()
        }
        return RouteSelectionState(next, nextFocus)
    }

    fun focus(busNo: String): RouteSelectionState =
        if (busNo in monitored) copy(focused = busNo) else this
}

data class ApiVehicle(
    val key: String,
    val vehicleNo: String,
    val lat: Double?,
    val lon: Double?,
    val nodeId: String,
    val nodeOrd: Int,
    val nodeName: String,
    val bearing: Double?,
    val bearingSource: String,
)

data class LiveRoute(
    val busNo: String,
    val routeId: String,
    val directionLabel: String?,
    val status: String,
    val message: String?,
    val vehicles: List<ApiVehicle>,
)

data class LiveSnapshot(
    val fetchedAt: String,
    val routes: List<LiveRoute>,
    val errors: List<RouteError> = emptyList(),
)

data class RouteError(
    val busNo: String,
    val routeId: String?,
    val message: String,
)

data class UiVehicle(
    val key: String,
    val busNo: String,
    val routeId: String,
    val vehicleNo: String,
    val lat: Double?,
    val lon: Double?,
    val nodeId: String,
    val nodeOrd: Int,
    val nodeName: String,
    val bearing: Double?,
    val bearingSource: String,
)

data class RouteStop(
    val nodeId: String,
    val nodeOrd: Int,
    val nodeName: String,
    val lat: Double?,
    val lon: Double?,
)

data class RouteVariant(
    val busNo: String,
    val routeId: String,
    val startNodeName: String,
    val endNodeName: String,
    val directionLabel: String?,
    val stops: List<RouteStop>,
)

data class Landmark(
    val name: String,
    val lat: Double,
    val lon: Double,
)

data class MainUiState(
    val monitoredBusNumbers: List<String> = listOf("10"),
    val focusedBusNumber: String? = "10",
    val routeMetadataByBusNumber: Map<String, List<RouteVariant>> = emptyMap(),
    val landmarks: List<Landmark> = emptyList(),
    val vehiclesByStableVehicleKey: Map<String, UiVehicle> = emptyMap(),
    val fetchedAt: String? = null,
    val isRefreshing: Boolean = false,
    val routeErrors: List<RouteError> = emptyList(),
    val isUsingStaleData: Boolean = false,
    val cameraInitialized: Boolean = false,
    val confirmedRouteIdsByBusNumber: Map<String, Set<String>> = emptyMap(),
)

fun reconcileVehicles(
    previous: Map<String, UiVehicle>,
    liveRoutes: List<LiveRoute>,
): Map<String, UiVehicle> {
    val next = previous.toMutableMap()
    for (route in liveRoutes) {
        if (route.status != "ok") continue
        next.entries.removeAll { it.value.routeId == route.routeId }
        for (vehicle in route.vehicles) {
            next[vehicle.key] = UiVehicle(
                key = vehicle.key,
                busNo = route.busNo,
                routeId = route.routeId,
                vehicleNo = vehicle.vehicleNo,
                lat = vehicle.lat,
                lon = vehicle.lon,
                nodeId = vehicle.nodeId,
                nodeOrd = vehicle.nodeOrd,
                nodeName = vehicle.nodeName,
                bearing = vehicle.bearing,
                bearingSource = vehicle.bearingSource,
            )
        }
    }
    return next
}

fun filterVehiclesForMonitored(
    vehicles: Map<String, UiVehicle>,
    monitored: Collection<String>,
): Map<String, UiVehicle> {
    val wanted = monitored.toSet()
    return vehicles.filterValues { it.busNo in wanted }
}
