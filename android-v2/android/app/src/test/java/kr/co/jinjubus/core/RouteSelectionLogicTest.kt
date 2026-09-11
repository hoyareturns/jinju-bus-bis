package kr.co.jinjubus.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RouteSelectionLogicTest {
    @Test fun firstInstallDefaultsTo10() {
        val state = RouteSelectionState.fromPersisted(null, null)
        assertEquals(listOf("10"), state.monitored)
        assertEquals("10", state.focused)
    }

    @Test fun persistedEmptyListStaysEmpty() {
        val state = RouteSelectionState.fromPersisted(emptyList(), null)
        assertEquals(emptyList<String>(), state.monitored)
        assertNull(state.focused)
    }

    @Test fun deletingFocusedRouteFallsBackAndLastRouteCanBeDeleted() {
        val state = RouteSelectionState(listOf("10", "160"), "10").remove("10")
        assertEquals("160", state.focused)
        assertNull(state.remove("160").focused)
    }
}
