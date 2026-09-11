package kr.co.jinjubus.data

import kotlinx.serialization.Serializable
import kr.co.jinjubus.core.ApiVehicle
import kr.co.jinjubus.core.LiveRoute
import kr.co.jinjubus.core.LiveSnapshot
import kr.co.jinjubus.core.RouteError
import kr.co.jinjubus.core.RouteStop
import kr.co.jinjubus.core.RouteVariant

internal fun mergeSuccessfulCache(previous: LiveResponseDto?, fresh: LiveResponseDto): LiveResponseDto {
    val successes = fresh.routes.filter { it.status == "ok" }
    val replaced = successes.mapTo(mutableSetOf()) { it.routeId }
    val retained = previous?.routes.orEmpty().filter { it.status == "ok" && it.routeId !in replaced }
    val hasFailures = fresh.errors.isNotEmpty() || fresh.routes.any { it.status != "ok" }
    return LiveResponseDto(
        if (hasFailures && previous != null) previous.fetchedAt else fresh.fetchedAt,
        retained + successes,
        fresh.errors,
    )
}

@Serializable
data class LiveResponseDto(
    val fetchedAt: String,
    val routes: List<LiveRouteDto> = emptyList(),
    val errors: List<RouteErrorDto> = emptyList(),
) {
    fun toCore() = LiveSnapshot(
        fetchedAt = fetchedAt,
        routes = routes.map(LiveRouteDto::toCore),
        errors = errors.map(RouteErrorDto::toCore),
    )
}

@Serializable
data class LiveRouteDto(
    val busNo: String,
    val routeId: String,
    val directionLabel: String? = null,
    val status: String,
    val message: String? = null,
    val vehicles: List<ApiVehicleDto> = emptyList(),
) {
    fun toCore() = LiveRoute(
        busNo, routeId, directionLabel, status, message, vehicles.map(ApiVehicleDto::toCore)
    )
}

@Serializable
data class ApiVehicleDto(
    val key: String,
    val vehicleNo: String,
    val lat: Double? = null,
    val lon: Double? = null,
    val nodeId: String = "",
    val nodeOrd: Int,
    val nodeName: String = "",
    val bearing: Double? = null,
    val bearingSource: String = "unknown",
) {
    fun toCore() = ApiVehicle(key, vehicleNo, lat, lon, nodeId, nodeOrd, nodeName, bearing, bearingSource)
}

@Serializable
data class RouteErrorDto(
    val busNo: String,
    val routeId: String? = null,
    val message: String,
) {
    fun toCore() = RouteError(busNo, routeId, message)
}

@Serializable
data class RoutesResponseDto(
    val routes: List<RouteVariantDto> = emptyList(),
    val errors: List<RouteErrorDto> = emptyList(),
)

@Serializable
data class RouteVariantDto(
    val busNo: String,
    val routeId: String,
    val startNodeName: String = "",
    val endNodeName: String = "",
    val directionLabel: String? = null,
    val stops: List<RouteStopDto> = emptyList(),
) {
    fun toCore() = RouteVariant(
        busNo, routeId, startNodeName, endNodeName, directionLabel, stops.map(RouteStopDto::toCore)
    )
}

@Serializable
data class RouteStopDto(
    val nodeId: String,
    val nodeOrd: Int,
    val nodeName: String,
    val lat: Double? = null,
    val lon: Double? = null,
) {
    fun toCore() = RouteStop(nodeId, nodeOrd, nodeName, lat, lon)
}
