package kr.co.jinjubus.data

import org.junit.Assert.*
import org.junit.Test

class GpsHistoryTest {
    @Test fun firstFixTinyMovementAndOldSamplesDoNotCreateArrow() {
        val history = GpsHistory()
        assertNull(history.bearing("R|V", 35.0, 128.0, 1000))
        assertNull(history.bearing("R|V", 35.000001, 128.0, 16000))
        assertNull(history.bearing("R|V", 35.01, 128.0, 200000))
    }
    @Test fun recentMovementCanProduceGenuineNorthOrEastBearing() {
        val history = GpsHistory()
        history.bearing("R|N", 35.0, 128.0, 1000)
        history.bearing("R|E", 35.0, 128.0, 1000)
        assertEquals(0.0, history.bearing("R|N", 35.001, 128.0, 16000)!!, 0.1)
        assertEquals(90.0, history.bearing("R|E", 35.0, 128.001, 16000)!!, 0.1)
    }
    @Test fun InvalidGpsAndImpossibleJumpsHaveNoArrow() {
        val history = GpsHistory()
        history.bearing("R|V", 35.0, 128.0, 1000)
        assertNull(history.bearing("R|V", null, null, 16000))
        assertNull(history.bearing("R|V", 0.0, 0.0, 17000))
        assertNull(history.bearing("R|V", 36.0, 129.0, 18000))
    }
}
