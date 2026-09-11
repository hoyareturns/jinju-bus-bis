package kr.co.jinjubus.data

import java.io.IOException
import java.net.URLDecoder
import java.time.OffsetDateTime
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.sync.withPermit
import kotlinx.serialization.json.*
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import kotlin.coroutines.resumeWithException

class BusApi(
    apiKey: String,
    private val client: OkHttpClient = defaultClient(),
    private val json: Json = defaultJson(),
    private val log: (String) -> Unit = {},
    private val nowMillis: () -> Long = System::currentTimeMillis,
) {
    private val key = apiKey.trim().let {
        require(it.isNotBlank()) { "TAGO_API_KEY must be configured for this build" }
        if ('%' in it) URLDecoder.decode(it.replace("+", "%2B"), "UTF-8") else it
    }
    private val root = "https://apis.data.go.kr/1613000/".toHttpUrl()
    private val permits = Semaphore(4)
    private val requestStartMutex = Mutex()
    private var nextRequestNanos = 0L
    private val inFlight = ConcurrentHashMap<Call, String>()
    private val registry = ConcurrentHashMap<String, Pair<Long, List<RouteVariantDto>>>()
    private val stopCache = ConcurrentHashMap<String, Pair<Long, List<RouteStopDto>>>()
    private val history = GpsHistory()
    private val requestLock = Any()
    @Volatile private var foreground = true
    @Volatile private var monitored: Set<String>? = null

    fun setMonitoredBusNumbers(numbers: Collection<String>) = synchronized(requestLock) {
        val previous = monitored.orEmpty()
        monitored = numbers.toSet()
        inFlight.forEach { (call, bus) -> if (bus in previous && bus !in numbers) call.cancel() }
        history.retainRoutes(registry.filterKeys { it in numbers }.values.flatMap { it.second }.map { it.routeId }.toSet())
    }

    fun setForeground(active: Boolean) = synchronized(requestLock) {
        foreground = active
        if (!active) inFlight.keys.forEach(Call::cancel)
    }

    private fun allowed(bus: String) = monitored?.contains(bus) != false
    private fun normalized(numbers: List<String>) = numbers.map(String::trim).filter(String::isNotEmpty).distinct()

    suspend fun locations(busNumbers: List<String>): LiveResponseDto = coroutineScope {
        val errors = java.util.Collections.synchronizedList(mutableListOf<RouteErrorDto>())
        val routes = normalized(busNumbers).map { bus -> async {
            if (!allowed(bus)) return@async emptyList<LiveRouteDto>()
            try {
                val variants = matchingRoutes(bus, true)
                if (variants.isEmpty()) errors.add(RouteErrorDto(bus, null, "노선 정보 없음"))
                variants.map { route -> async {
                    if (!allowed(bus)) return@async null
                    try {
                        val rows = pages("BusLcInfoInqireService/getRouteAcctoBusLcList", bus, "routeId", route.routeId, true)
                        val vehicles = rows.mapNotNull { row -> vehicle(route.routeId, row) }
                        if (!allowed(bus)) return@async null
                        log("LIVE bus=$bus routeId=${route.routeId} resultCode=00 items=${rows.size} vehicles=${vehicles.size} gps=${vehicles.count { it.lat != null }}")
                        LiveRouteDto(bus, route.routeId, route.directionLabel, "ok",
                            if (vehicles.isEmpty()) "현재 조회되는 차량 없음" else null, vehicles)
                    } catch (cancelled: CancellationException) { throw cancelled
                    } catch (failure: Exception) {
                        if (!allowed(bus)) return@async null
                        val message = report("LIVE", bus, route.routeId, failure)
                        errors.add(RouteErrorDto(bus, route.routeId, message))
                        LiveRouteDto(bus, route.routeId, route.directionLabel, "error", message)
                    }
                } }.awaitAll().filterNotNull()
            } catch (cancelled: CancellationException) { throw cancelled
            } catch (failure: Exception) {
                if (allowed(bus)) errors.add(RouteErrorDto(bus, null, report("REGISTRY", bus, null, failure)))
                emptyList()
            }
        } }.awaitAll().flatten()
        LiveResponseDto(OffsetDateTime.now().toString(), routes.filter { allowed(it.busNo) }, errors.filter { allowed(it.busNo) })
    }

    suspend fun routes(busNumbers: List<String>): RoutesResponseDto = coroutineScope {
        val errors = java.util.Collections.synchronizedList(mutableListOf<RouteErrorDto>())
        val routes = normalized(busNumbers).map { bus -> async {
            try {
                val matches = matchingRoutes(bus, false)
                if (matches.isEmpty()) errors.add(RouteErrorDto(bus, null, "노선 정보 없음"))
                matches.map { route -> async {
                    try {
                        val cached = stopCache[route.routeId]?.takeIf { nowMillis() - it.first < 86_400_000 }
                        val stops = cached?.second ?: pages("BusRouteInfoInqireService/getRouteAcctoThrghSttnList", bus, "routeId", route.routeId, false)
                            .mapNotNull { row ->
                                val order = row.integer("nodeord") ?: return@mapNotNull null
                                val lat = row.number("gpslati"); val lon = row.number("gpslong")
                                RouteStopDto(row.text("nodeid"), order, row.text("nodenm"),
                                    lat.takeIf { validGps(lat, lon) }, lon.takeIf { validGps(lat, lon) })
                            }.sortedBy { it.nodeOrd }.also { stopCache[route.routeId] = nowMillis() to it }
                        route.copy(stops = stops)
                    } catch (cancelled: CancellationException) { throw cancelled
                    } catch (failure: Exception) {
                        errors.add(RouteErrorDto(bus, route.routeId, report("STOPS", bus, route.routeId, failure)))
                        null
                    }
                } }.awaitAll().filterNotNull()
            } catch (cancelled: CancellationException) { throw cancelled
            } catch (failure: Exception) {
                errors.add(RouteErrorDto(bus, null, report("REGISTRY", bus, null, failure)))
                emptyList()
            }
        } }.awaitAll().flatten()
        RoutesResponseDto(routes, errors.toList())
    }

    private suspend fun matchingRoutes(bus: String, live: Boolean): List<RouteVariantDto> {
        registry[bus]?.takeIf { nowMillis() - it.first < 86_400_000 }?.let { return it.second }
        val matches = pages("BusRouteInfoInqireService/getRouteNoList", bus, "routeNo", bus, live)
            .filter { it.text("routeno").trim() == bus && it.text("routeid").isNotBlank() }
            .distinctBy { it.text("routeid") }.map { row ->
                RouteVariantDto(bus, row.text("routeid"), row.text("startnodenm"), row.text("endnodenm"),
                    row.text("endnodenm").takeIf(String::isNotBlank)?.let { "$it 방면" })
            }
        registry[bus] = nowMillis() to matches
        log("REGISTRY bus=$bus routeIds=${matches.joinToString { it.routeId }} resultCode=00")
        return matches
    }

    private fun vehicle(routeId: String, row: JsonObject): ApiVehicleDto? {
        val number = row.text("vehicleno").trim().takeIf(String::isNotBlank) ?: return null
        val order = row.integer("nodeord") ?: -1
        val rawLat = row.number("gpslati"); val rawLon = row.number("gpslong")
        val lat = rawLat.takeIf { validGps(rawLat, rawLon) }; val lon = rawLon.takeIf { validGps(rawLat, rawLon) }
        val stableKey = "$routeId|$number"
        val bearing = history.bearing(stableKey, lat, lon, nowMillis())
        return ApiVehicleDto(stableKey, number, lat, lon, row.text("nodeid"), order, row.text("nodenm"),
            bearing, if (bearing == null) "unknown" else "gps")
    }

    private suspend fun pages(path: String, bus: String, parameter: String, value: String, live: Boolean): List<JsonObject> {
        val all = mutableListOf<JsonObject>()
        for (page in 1..100) {
            currentCoroutineContext().ensureActive()
            if (!foreground) throw CancellationException("App is backgrounded")
            if (live && !allowed(bus)) throw BusApiException(TagoErrorKind.NETWORK, "CANCELLED", "삭제한 노선의 조회를 중지했습니다.")
            val url = root.newBuilder().addPathSegments(path).addQueryParameter("serviceKey", key)
                .addQueryParameter("cityCode", "38030").addQueryParameter(parameter, value)
                .addQueryParameter("_type", "json").addQueryParameter("pageNo", page.toString())
                .addQueryParameter("numOfRows", "1000").build()
            val result = retryTransient { permits.withPermit {
                // Registry + stops + multiple direction IDs must not burst into TAGO's rate limit.
                requestStartMutex.withLock {
                    val waitMillis = ((nextRequestNanos - System.nanoTime()) / 1_000_000).coerceAtLeast(0)
                    if (waitMillis > 0) delay(waitMillis)
                    nextRequestNanos = System.nanoTime() + 250_000_000L
                }
                withContext(Dispatchers.IO) {
                if (live && !allowed(bus)) throw BusApiException(TagoErrorKind.NETWORK, "CANCELLED", "삭제한 노선의 조회를 중지했습니다.")
                val call = client.newCall(Request.Builder().url(url).get().build())
                synchronized(requestLock) {
                    if (!foreground || (live && !allowed(bus))) throw CancellationException("Request no longer active")
                    inFlight[call] = bus
                }
                try {
                    call.await().use { response ->
                        if (!response.isSuccessful) {
                            if (response.code in listOf(401, 403, 429)) throw tagoError(response.code.toString())
                            throw BusApiException(TagoErrorKind.HTTP, response.code.toString(), "공공 API HTTP 오류 (${response.code})")
                        }
                        parseTagoPage(response.body.string(), json)
                    }
                } finally { inFlight.remove(call) }
            } } }
            all.addAll(result.items)
            if (all.size >= result.total) return all
            if (result.items.isEmpty()) throw BusApiException(TagoErrorKind.MALFORMED, "PAGING", "공공 API 응답 일부가 누락되었습니다.")
        }
        throw BusApiException(TagoErrorKind.MALFORMED, "PAGING", "공공 API 응답 페이지가 너무 많습니다.")
    }

    private fun report(operation: String, bus: String, route: String?, failure: Exception): String {
        val error = failure as? BusApiException
        log("$operation bus=$bus routeId=$route error=${error?.kind ?: TagoErrorKind.NETWORK} code=${error?.code ?: "IO"}")
        return error?.message ?: "네트워크 연결을 확인하고 다시 갱신해 주세요."
    }

    private suspend fun <T> retryTransient(block: suspend () -> T): T {
        repeat(3) { attempt ->
            try { return block() }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (failure: Exception) {
                val temporary = failure is IOException ||
                    (failure is BusApiException && (
                        failure.kind == TagoErrorKind.UPSTREAM && failure.code in setOf("01", "02", "04", "05", "99") ||
                        failure.kind == TagoErrorKind.HTTP && failure.code in setOf("500", "502", "503", "504")))
                if (!temporary || attempt == 2) throw failure
                log("Transient API response; retry ${attempt + 1}")
                delay(1_000L * (attempt + 1))
            }
        }
        error("Unreachable retry state")
    }

    private suspend fun Call.await(): Response = suspendCancellableCoroutine { continuation ->
        continuation.invokeOnCancellation { cancel() }
        enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) { if (continuation.isActive) continuation.resumeWithException(e) }
            override fun onResponse(call: Call, response: Response) {
                continuation.resume(response) { _, value, _ -> value.close() }
            }
        })
    }

    companion object {
        fun defaultJson() = Json {
            ignoreUnknownKeys = true
            explicitNulls = false
            encodeDefaults = true
        }

        fun defaultClient() = OkHttpClient.Builder()
            .connectTimeout(5, TimeUnit.SECONDS)
            .readTimeout(8, TimeUnit.SECONDS)
            .callTimeout(12, TimeUnit.SECONDS)
            .build()
    }
}
