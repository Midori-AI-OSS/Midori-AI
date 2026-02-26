package xyz.midoriai.radio.ui.mock

import xyz.midoriai.radio.ui.model.AlbumSummary
import xyz.midoriai.radio.ui.model.TrackSummary

object MockData {
    val featuredAlbums: List<AlbumSummary> = listOf(
        AlbumSummary(title = "Midori AI Focus", subtitle = "Daily focus mix"),
        AlbumSummary(title = "Night Drive", subtitle = "Synth & chill"),
        AlbumSummary(title = "Coding Beats", subtitle = "Lo-fi for building"),
        AlbumSummary(title = "Deep Space", subtitle = "Ambient textures"),
        AlbumSummary(title = "Acoustic Morning", subtitle = "Soft starts"),
        AlbumSummary(title = "Hi-Energy", subtitle = "Upbeat picks"),
    )

    val trendingTracks: List<TrackSummary> = listOf(
        TrackSummary(title = "Midori AI Theme", artist = "Midori AI Radio", durationText = "3:21"),
        TrackSummary(title = "Neon Skyline", artist = "Signal Bloom", durationText = "2:58"),
        TrackSummary(title = "After Hours", artist = "Quiet Circuit", durationText = "4:05"),
        TrackSummary(title = "Paper Planets", artist = "Orbit Letters", durationText = "3:42"),
        TrackSummary(title = "Copper Sunrise", artist = "Warm Voltage", durationText = "3:12"),
    )
}
