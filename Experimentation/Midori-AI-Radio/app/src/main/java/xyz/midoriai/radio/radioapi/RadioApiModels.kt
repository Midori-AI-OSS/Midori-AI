package xyz.midoriai.radio.radioapi

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class RadioError(
    val code: String,
    val message: String,
)

@Serializable
data class RadioEnvelope<T>(
    val version: String,
    val ok: Boolean,
    val now: String,
    val data: T? = null,
    val error: RadioError? = null,
)

@Serializable
data class HealthPayload(
    val status: String,
    @SerialName("warmup_active")
    val warmupActive: Boolean,
    @SerialName("track_count")
    val trackCount: Int,
    @SerialName("cached_tracks")
    val cachedTracks: Int,
    @SerialName("cached_bytes")
    val cachedBytes: Long,
)

@Serializable
data class ChannelEntry(
    val name: String,
    @SerialName("track_count")
    val trackCount: Int,
)

@Serializable
data class ChannelsPayload(
    val channels: List<ChannelEntry>,
)

@Serializable
data class QualityLevel(
    val name: String,
    @SerialName("bitrate_kbps")
    val bitrateKbps: Int,
)

@Serializable
data class CurrentPayload(
    @SerialName("station_label")
    val stationLabel: String,
    val channel: String,
    @SerialName("track_id")
    val trackId: String,
    val title: String,
    @SerialName("duration_ms")
    val durationMs: Long,
    @SerialName("position_ms")
    val positionMs: Long,
    @SerialName("started_at")
    val startedAt: String,
    @SerialName("warmup_active")
    val warmupActive: Boolean,
    @SerialName("quality_levels")
    val qualityLevels: List<QualityLevel>,
)

@Serializable
data class ArtPayload(
    val channel: String,
    @SerialName("track_id")
    val trackId: String,
    @SerialName("has_art")
    val hasArt: Boolean,
    val mime: String? = null,
    @SerialName("art_url")
    val artUrl: String,
)
