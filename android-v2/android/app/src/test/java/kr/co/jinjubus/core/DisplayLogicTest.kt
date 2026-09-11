package kr.co.jinjubus.core

import java.time.OffsetDateTime
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DisplayLogicTest {
    @Test fun freshnessLabelsDistinguishCachedData() {
        val now = OffsetDateTime.parse("2026-09-11T12:00:20+09:00")
        assertEquals("방금 갱신됨", freshnessText("2026-09-11T12:00:15+09:00", false, now))
        assertEquals("이전 정보 · 1분 전", freshnessText("2026-09-11T11:59:20+09:00", true, now))
    }

    @Test fun stopWindowKeepsCurrentNearMiddle() {
        val stops = (1..10).map { RouteStop("N$it", it, "정류장 $it", null, null) }
        assertEquals(listOf(3, 4, 5, 6, 7), stopWindow(stops, 5, 2).map { it.nodeOrd })
    }

    @Test fun cameraOnlyAutoInitializesOnce() {
        assertTrue(shouldInitializeMapCamera(false, true))
        assertFalse(shouldInitializeMapCamera(true, true))
        assertFalse(shouldInitializeMapCamera(false, false))
    }
}
