package kr.co.jinjubus.data

import kotlin.math.*

internal class GpsHistory {
    private data class Sample(val lat: Double, val lon: Double, val time: Long)
    private val previous = mutableMapOf<String, Sample>()

    @Synchronized fun bearing(key: String, lat: Double?, lon: Double?, now: Long): Double? {
        previous.entries.removeAll { now - it.value.time > 120_000 }
        if (!validGps(lat, lon)) return null
        val current = Sample(lat!!, lon!!, now)
        val old = previous.put(key, current) ?: return null
        val elapsed = now - old.time
        if (elapsed !in 1..120_000) return null
        val p1 = Math.toRadians(old.lat)
        val p2 = Math.toRadians(current.lat)
        val deltaLat = p2 - p1
        val deltaLon = Math.toRadians(current.lon - old.lon)
        val h = (sin(deltaLat / 2).pow(2) + cos(p1) * cos(p2) * sin(deltaLon / 2).pow(2)).coerceIn(0.0, 1.0)
        val distance = 6_371_000 * 2 * atan2(sqrt(h), sqrt(1 - h))
        if (distance < 5 || distance / (elapsed / 1000.0) > 45) return null
        val y = sin(deltaLon) * cos(p2)
        val x = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(deltaLon)
        return (Math.toDegrees(atan2(y, x)) + 360) % 360
    }

    @Synchronized fun retainRoutes(routeIds: Set<String>) {
        previous.keys.removeAll { it.substringBefore('|') !in routeIds }
    }
}
