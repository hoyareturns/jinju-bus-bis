package kr.co.jinjubus.core

import java.time.Duration
import java.time.OffsetDateTime

fun freshnessText(
    fetchedAt: String?,
    stale: Boolean,
    now: OffsetDateTime = OffsetDateTime.now(),
): String {
    val fetched = fetchedAt?.let { runCatching { OffsetDateTime.parse(it) }.getOrNull() }
        ?: return "아직 갱신 전"
    val seconds = Duration.between(fetched, now).seconds.coerceAtLeast(0)
    val age = when {
        seconds < 15 -> "방금 갱신됨"
        seconds < 60 -> "${seconds}초 전"
        seconds < 3600 -> "${seconds / 60}분 전"
        else -> "${seconds / 3600}시간 전"
    }
    return if (stale && age != "방금 갱신됨") "이전 정보 · $age" else if (stale) "이전 정보 · 방금" else age
}

fun stopWindow(stops: List<RouteStop>, currentOrd: Int, radius: Int = 3): List<RouteStop> {
    if (stops.isEmpty()) return emptyList()
    val currentIndex = stops.indexOfFirst { it.nodeOrd == currentOrd }.takeIf { it >= 0 }
        ?: stops.indexOfFirst { it.nodeOrd > currentOrd }.takeIf { it >= 0 }
        ?: stops.lastIndex
    val start = (currentIndex - radius).coerceAtLeast(0)
    val endExclusive = (currentIndex + radius + 1).coerceAtMost(stops.size)
    return stops.subList(start, endExclusive)
}

fun shouldInitializeMapCamera(cameraInitialized: Boolean, hasContent: Boolean): Boolean =
    !cameraInitialized && hasContent

fun sanitizeRouteNumberInput(value: String, maxLength: Int = 8): String =
    value.filter { it.isDigit() || it == '-' }.take(maxLength)
