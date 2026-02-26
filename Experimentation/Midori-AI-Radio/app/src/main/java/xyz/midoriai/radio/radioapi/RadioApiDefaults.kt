package xyz.midoriai.radio.radioapi

/**
 * Android connects to the Midori AI Radio upstream API by default.
 *
 * The Website Blog also exposes proxy routes under `/api/radio/` for browser same-origin usage.
 * Android should not use those proxy paths unless it is explicitly running inside the Blog domain.
 */
object RadioApiDefaults {
    const val DEFAULT_BASE_URL = "https://radio.midori-ai.xyz"
    const val API_VERSION = "radio.v1"
}
