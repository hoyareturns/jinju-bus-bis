package kr.co.jinjubus.data

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kr.co.jinjubus.core.Landmark
import kr.co.jinjubus.core.RouteStop
import kr.co.jinjubus.core.RouteVariant

class RouteSnapshotStore(
    private val context: Context,
    private val json: Json = BusApi.defaultJson(),
) {
    @Volatile private var root: JsonObject? = null

    private suspend fun root(): JsonObject = root ?: withContext(Dispatchers.IO) {
        root ?: context.assets.open("routes_snapshot.json").bufferedReader().use { reader ->
            json.parseToJsonElement(reader.readText()).jsonObject.also { root = it }
        }
    }

    suspend fun containsBusNumber(busNo: String): Boolean =
        root()["routes"]?.jsonObject?.containsKey(busNo) == true

    suspend fun routeVariants(busNumbers: Collection<String>): List<RouteVariant> {
        val routes = root()["routes"]?.jsonObject ?: return emptyList()
        return busNumbers.flatMap { busNo ->
            val variants = routes[busNo]?.jsonObject ?: return@flatMap emptyList()
            variants.map { (routeId, rawStops) ->
                val stops = rawStops.jsonArray.map(::decodeStop)
                RouteVariant(
                    busNo = busNo,
                    routeId = routeId,
                    startNodeName = stops.firstOrNull()?.nodeName.orEmpty(),
                    endNodeName = stops.lastOrNull()?.nodeName.orEmpty(),
                    directionLabel = stops.lastOrNull()?.nodeName?.let { "$it 방면" },
                    stops = stops,
                )
            }
        }
    }

    suspend fun landmarks(): List<Landmark> {
        val array = root()["landmarks"]?.jsonArray ?: return emptyList()
        return array.mapNotNull { element ->
            val obj = element.jsonObject
            val name = obj["name"]?.jsonPrimitive?.content ?: return@mapNotNull null
            val lat = obj["lat"]?.jsonPrimitive?.doubleOrNull ?: return@mapNotNull null
            val lon = obj["lon"]?.jsonPrimitive?.doubleOrNull ?: return@mapNotNull null
            Landmark(name, lat, lon)
        }
    }

    private fun decodeStop(element: kotlinx.serialization.json.JsonElement): RouteStop {
        val obj = element.jsonObject
        return RouteStop(
            nodeId = obj["id"]?.jsonPrimitive?.content.orEmpty(),
            nodeOrd = obj["ord"]!!.jsonPrimitive.int,
            nodeName = obj["name"]?.jsonPrimitive?.content.orEmpty(),
            lat = obj["lat"]?.jsonPrimitive?.doubleOrNull,
            lon = obj["lon"]?.jsonPrimitive?.doubleOrNull,
        )
    }
}
