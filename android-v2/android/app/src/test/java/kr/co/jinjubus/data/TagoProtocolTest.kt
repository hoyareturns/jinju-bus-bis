package kr.co.jinjubus.data

import org.junit.Assert.*
import org.junit.Test

class TagoProtocolTest {
    @Test fun ambiguousSuccessfulBodiesAreNotEmptySuccess() {
        for (body in listOf("{}", """{"items":"","totalCount":"bad"}""", """{"items":"","totalCount":3}""")) {
            val failure = runCatching { parseTagoPage("""{"response":{"header":{"resultCode":"00","resultMsg":"NORMAL SERVICE"},"body":$body}}""", BusApi.defaultJson()) }.exceptionOrNull()
            assertTrue(failure is BusApiException)
            assertEquals(TagoErrorKind.MALFORMED, (failure as BusApiException).kind)
        }
    }

    @Test fun explicitEmptyItemsAndZeroCountAreValid() {
        val page = parseTagoPage("""{"response":{"header":{"resultCode":"00","resultMsg":"NORMAL SERVICE"},"body":{"items":"","totalCount":0}}}""", BusApi.defaultJson())
        assertEquals(0, page.total)
        assertTrue(page.items.isEmpty())
    }
}
