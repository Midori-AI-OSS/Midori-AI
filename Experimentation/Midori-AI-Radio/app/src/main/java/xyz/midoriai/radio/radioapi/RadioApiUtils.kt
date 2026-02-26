package xyz.midoriai.radio.radioapi

import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl

private val QUALITY_VALUES = setOf("low", "medium", "high")

/**
 * Normalizes the channel for Midori AI Radio requests.
 *
 * Parity target (Agent Runner): treat "all" as the empty string. When building requests we still include
 * the query parameter (i.e. `channel=`).
 */
fun normalizeChannel(value: String?): String {
    val raw = value?.trim()?.lowercase() ?: ""

    if (raw.isBlank()) {
        return ""
    }

    if (raw == "all") {
        return ""
    }

    return raw
}

/**
 * Normalizes the quality name for Midori AI Radio requests.
 *
 * Only `low|medium|high` are allowed. Unknown values snap to `medium`.
 */
fun normalizeQuality(value: String?): String {
    val raw = value?.trim()?.lowercase() ?: "medium"
    return if (QUALITY_VALUES.contains(raw)) {
        raw
    } else {
        "medium"
    }
}

/**
 * Builds the stream URL:
 *   GET /radio/v1/stream?channel=<channel>&q=<quality>
 */
fun buildStreamUrl(
    baseUrl: String = RadioApiDefaults.DEFAULT_BASE_URL,
    channel: String?,
    quality: String?,
): String {
    val base = baseUrl.toHttpUrl()

    return base.newBuilder()
        .addPathSegments("radio/v1/stream")
        .setQueryParameter("channel", normalizeChannel(channel))
        .setQueryParameter("q", normalizeQuality(quality))
        .build()
        .toString()
}

internal fun buildChannelQueryUrl(
    baseUrl: HttpUrl,
    path: String,
    channel: String?,
): HttpUrl {
    return baseUrl.newBuilder()
        .addPathSegments(path.trimStart('/'))
        .setQueryParameter("channel", normalizeChannel(channel))
        .build()
}

fun toAbsoluteRadioUrl(
    rawUrl: String,
    baseUrl: String = RadioApiDefaults.DEFAULT_BASE_URL,
): String {
    val trimmed = rawUrl.trim()

    if (
        trimmed.startsWith("http://", ignoreCase = true) ||
        trimmed.startsWith("https://", ignoreCase = true)
    ) {
        return trimmed
    }

    val base = baseUrl.trim().trimEnd('/').toHttpUrl()

    return base.resolve(trimmed)?.toString()
        ?: if (trimmed.startsWith("/")) {
            "${baseUrl.trim().trimEnd('/')}$trimmed"
        } else {
            "${baseUrl.trim().trimEnd('/')}/$trimmed"
        }
}
