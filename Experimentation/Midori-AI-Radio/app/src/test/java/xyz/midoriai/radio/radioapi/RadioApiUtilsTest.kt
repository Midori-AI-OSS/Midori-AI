package xyz.midoriai.radio.radioapi

import okhttp3.HttpUrl.Companion.toHttpUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class RadioApiUtilsTest {
    @Test
    fun normalizeChannel_allBecomesEmptyString() {
        assertEquals("", normalizeChannel("all"))
        assertEquals("", normalizeChannel(" ALL "))
    }

    @Test
    fun normalizeChannel_trimsAndLowercases() {
        assertEquals("chill", normalizeChannel(" Chill "))
        assertEquals("", normalizeChannel(""))
        assertEquals("", normalizeChannel(null))
    }

    @Test
    fun normalizeQuality_snapsUnknownToMedium() {
        assertEquals("medium", normalizeQuality(null))
        assertEquals("low", normalizeQuality("LOW"))
        assertEquals("medium", normalizeQuality("not-a-quality"))
    }

    @Test
    fun buildStreamUrl_includesChannelAndQualityParams() {
        val url = buildStreamUrl(
            baseUrl = "https://radio.midori-ai.xyz",
            channel = "all",
            quality = "high",
        )
        val parsed = url.toHttpUrl()

        assertTrue(parsed.queryParameterNames.contains("channel"))
        assertTrue(parsed.queryParameterNames.contains("q"))
        assertEquals("", parsed.queryParameter("channel"))
        assertEquals("high", parsed.queryParameter("q"))
    }
}
