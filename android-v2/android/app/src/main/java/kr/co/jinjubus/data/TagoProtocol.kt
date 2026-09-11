package kr.co.jinjubus.data

import kotlinx.serialization.json.*

enum class TagoErrorKind { AUTH, QUOTA, INVALID_REQUEST, NETWORK, HTTP, MALFORMED, UPSTREAM }

class BusApiException(
    val kind: TagoErrorKind,
    val code: String,
    message: String,
) : RuntimeException(message)

internal data class TagoPage(val items: List<JsonObject>, val total: Int)

internal fun tagoError(code: String): BusApiException {
    val kind = when (code) {
        "20", "30", "31", "32", "401", "403" -> TagoErrorKind.AUTH
        "22", "29", "429" -> TagoErrorKind.QUOTA
        "10", "11", "12" -> TagoErrorKind.INVALID_REQUEST
        else -> TagoErrorKind.UPSTREAM
    }
    val label = when (kind) {
        TagoErrorKind.AUTH -> "공공 API 인증키 또는 이용 권한을 확인해 주세요."
        TagoErrorKind.QUOTA -> "공공 API 요청 한도를 초과했습니다."
        TagoErrorKind.INVALID_REQUEST -> "노선 ID 또는 요청 항목을 확인해 주세요."
        else -> "공공 API가 오류를 반환했습니다."
    }
    return BusApiException(kind, code, "$label (TAGO $code)")
}

internal fun parseTagoPage(payload: String, json: Json): TagoPage {
    if (payload.trimStart().startsWith('<')) {
        val code = Regex("<(?:resultCode|returnReasonCode)>\\s*([^<]+)").find(payload)?.groupValues?.get(1)?.trim()
        if (code != null && code != "00" && code != "0") throw tagoError(code)
        throw BusApiException(TagoErrorKind.MALFORMED, "XML", "공공 API JSON 응답을 확인할 수 없습니다.")
    }
    try {
        val root = json.parseToJsonElement(payload).jsonObject["response"]?.jsonObject
            ?: error("Missing response")
        val header = root["header"]?.jsonObject ?: error("Missing header")
        val code = header.text("resultCode")
        check(code.isNotEmpty() && header.text("resultMsg").isNotBlank())
        if (code == "03") return TagoPage(emptyList(), 0)
        if (code != "00" && code != "0") throw tagoError(code)
        val body = root["body"]?.jsonObject ?: error("Missing body")
        val total = body["totalCount"]?.jsonPrimitive?.intOrNull ?: error("Missing totalCount")
        check(total >= 0 && body.containsKey("items"))
        val container = body["items"]
        val raw = when (container) {
            null, JsonNull -> null
            is JsonObject -> container["item"]
            is JsonPrimitive -> { check(container.content.isBlank()); null }
            else -> error("Invalid items")
        }
        val items = when (raw) {
            null, JsonNull -> emptyList()
            is JsonArray -> raw.map { it.jsonObject }
            is JsonObject -> listOf(raw)
            is JsonPrimitive -> { check(raw.content.isBlank()); emptyList() }
            else -> error("Invalid item")
        }
        check(items.size <= total && (total == 0 || items.isNotEmpty()))
        return TagoPage(items, total)
    } catch (error: BusApiException) {
        throw error
    } catch (_: Exception) {
        throw BusApiException(TagoErrorKind.MALFORMED, "PARSE", "공공 API 응답 형식을 확인할 수 없습니다.")
    }
}

internal fun JsonObject.text(name: String): String = (get(name) as? JsonPrimitive)?.contentOrNull.orEmpty()
internal fun JsonObject.number(name: String): Double? = text(name).toDoubleOrNull()
internal fun JsonObject.integer(name: String): Int? = text(name).toIntOrNull()

internal fun validGps(lat: Double?, lon: Double?): Boolean = lat != null && lon != null &&
    lat.isFinite() && lon.isFinite() && lat in -90.0..90.0 && lon in -180.0..180.0 && (lat != 0.0 || lon != 0.0)
