package kr.co.jinjubus.data

import kotlinx.coroutines.runBlocking
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test

class BusApiTest {
    @Test fun transientUpstreamErrorRetriesWithoutTurningIntoEmptySuccess() = runBlocking {
        var registryAttempts = 0
        val api = BusApi("test-key", client { url ->
            if (url.encodedPath.endsWith("getRouteNoList")) {
                registryAttempts++
                if (registryAttempts == 1) """{"response":{"header":{"resultCode":"99","resultMsg":"APPLICATION ERROR"}}}"""
                else envelope("""{"routeno":10,"routeid":"OUT"}""")
            } else envelope("[]", 0)
        })
        val response = api.locations(listOf("10"))
        assertEquals(2, registryAttempts)
        assertTrue(response.errors.isEmpty())
        assertEquals("ok", response.routes.single().status)
    }
    @Test fun gpsVehicleIsKeptWhenOptionalStopOrderIsMissing() = runBlocking {
        val api = BusApi("test-key", client { url ->
            if (url.encodedPath.endsWith("getRouteNoList")) envelope("""{"routeno":10,"routeid":"OUT"}""")
            else envelope("""{"vehicleno":"V1","gpslati":35.18,"gpslong":128.1}""")
        })
        val vehicle = api.locations(listOf("10")).routes.single().vehicles.single()
        assertEquals(-1, vehicle.nodeOrd)
        assertEquals(35.18, vehicle.lat!!, 0.0)
    }
    private fun envelope(items: String, total: Int = 1) =
        """{"response":{"header":{"resultCode":"00","resultMsg":"NORMAL SERVICE."},"body":{"items":{"item":$items},"totalCount":$total}}}"""
    private val registry = """[{"routeno":10,"routeid":"OUT","endnodenm":"종점"},{"routeno":"10","routeid":"BACK","endnodenm":"차고지"},{"routeno":100,"routeid":"OTHER"}]"""
    private fun client(reply: (HttpUrl) -> String) = OkHttpClient.Builder().addInterceptor { chain ->
        Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
            .body(reply(chain.request().url).toResponseBody()).build()
    }.build()

    @Test fun rawAndEncodedKeysAreEncodedExactlyOnceAndAllExactVariantsAreFetched() = runBlocking {
        for (key in listOf("A+B/C==", "A%2BB%2FC%3D%3D")) {
            val calls = java.util.Collections.synchronizedList(mutableListOf<HttpUrl>())
            val api = BusApi(key, client { url ->
                calls.add(url)
                if (url.encodedPath.endsWith("getRouteNoList")) envelope(registry, 3)
                else envelope("[]", 0)
            })
            val result = api.locations(listOf("10"))
            assertEquals(setOf("OUT", "BACK"), result.routes.map { it.routeId }.toSet())
            assertEquals(setOf("OUT", "BACK"), calls.mapNotNull { it.queryParameter("routeId") }.toSet())
            assertTrue(calls.all { it.host == "apis.data.go.kr" && it.queryParameter("cityCode") == "38030" })
            assertTrue(calls.all { it.queryParameter("serviceKey") == "A+B/C==" })
            assertFalse(calls.any { it.encodedQuery.orEmpty().contains("%252B") })
        }
    }

    @Test fun missingOptionalGpsKeepsRealVehicleAndStopDetails() = runBlocking {
        val api = BusApi("test-key", client { url ->
            if (url.encodedPath.endsWith("getRouteNoList")) envelope("""{"routeno":10,"routeid":"OUT"}""")
            else envelope("""{"vehicleno":"경남71자5809","nodeid":"N1","nodeord":34,"nodenm":"진주동명중고등학교"}""")
        })
        val vehicle = api.locations(listOf("10")).routes.single().vehicles.single()
        assertEquals("OUT|경남71자5809", vehicle.key)
        assertEquals("진주동명중고등학교", vehicle.nodeName)
        assertNull(vehicle.lat)
        assertNull(vehicle.lon)
        assertNull(vehicle.bearing)
    }

    @Test fun realGpsIsPreservedAndInvalidCoordinatesDoNotBecomeMapPositions() = runBlocking {
        val api = BusApi("test-key", client { url ->
            if (url.encodedPath.endsWith("getRouteNoList")) envelope("""{"routeno":10,"routeid":"OUT"}""")
            else envelope("""[{"vehicleno":"V1","nodeord":1,"gpslati":35.18,"gpslong":128.1},{"vehicleno":"V2","nodeord":2,"gpslati":0,"gpslong":0},{"vehicleno":"V3","nodeord":3,"gpslati":91,"gpslong":128},{"vehicleno":"V4","nodeord":4,"gpslati":"bad","gpslong":128}]""", 4)
        })
        val vehicles = api.locations(listOf("10")).routes.single().vehicles
        assertEquals(4, vehicles.size)
        assertEquals(35.18, vehicles.first().lat!!, 0.0)
        assertEquals(128.1, vehicles.first().lon!!, 0.0)
        assertTrue(vehicles.drop(1).all { it.lat == null && it.lon == null && it.bearing == null })
    }

    @Test fun http200WithApiErrorIsNotSuccessfulEmptyData() = runBlocking {
        val api = BusApi("test-key", client { url ->
            if (url.encodedPath.endsWith("getRouteNoList")) envelope(registry, 3)
            else if (url.queryParameter("routeId") == "BACK") """{"response":{"header":{"resultCode":"22","resultMsg":"LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR"}}}"""
            else envelope("""{"vehicleno":"V1","nodeord":1,"gpslati":35.18,"gpslong":128.1}""")
        })
        val result = api.locations(listOf("10"))
        assertEquals(1, result.routes.first { it.routeId == "OUT" }.vehicles.size)
        assertEquals("error", result.routes.first { it.routeId == "BACK" }.status)
        assertTrue(result.errors.any { it.routeId == "BACK" && it.message.contains("22") })
    }

    @Test fun xmlAuthenticationErrorIsReportedWithoutLeakingKey() = runBlocking {
        val api = BusApi("private-test-key", client {
            "<OpenAPI_ServiceResponse><cmmMsgHeader><returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg><returnReasonCode>30</returnReasonCode></cmmMsgHeader></OpenAPI_ServiceResponse>"
        })
        val result = api.locations(listOf("10"))
        assertTrue(result.routes.isEmpty())
        assertTrue(result.errors.single().message.contains("30"))
        assertFalse(result.errors.single().message.contains("private-test-key"))
    }

    @Test fun singletonStopResponseIsParsedAndEmptySelectionMakesNoRequest() = runBlocking {
        var requests = 0
        val api = BusApi("test-key", client { url ->
            requests++
            if (url.encodedPath.endsWith("getRouteNoList")) envelope("""{"routeno":10,"routeid":"OUT"}""")
            else envelope("""{"nodeid":"N1","nodeord":1,"nodenm":"진주역","gpslati":35.15,"gpslong":128.12}""")
        })
        assertTrue(api.locations(emptyList()).routes.isEmpty())
        assertEquals(0, requests)
        val routes = api.routes(listOf("10"))
        assertEquals("진주역", routes.routes.single().stops.single().nodeName)
    }

    @Test fun registryPaginationDoesNotLoseReturnDirection() = runBlocking {
        val api = BusApi("test-key", client { url ->
            if (!url.encodedPath.endsWith("getRouteNoList")) envelope("[]", 0)
            else if (url.queryParameter("pageNo") == "1") envelope("""{"routeno":10,"routeid":"OUT"}""", 2)
            else envelope("""{"routeno":10,"routeid":"BACK"}""", 2)
        })
        assertEquals(setOf("OUT", "BACK"), api.locations(listOf("10")).routes.map { it.routeId }.toSet())
    }
}
