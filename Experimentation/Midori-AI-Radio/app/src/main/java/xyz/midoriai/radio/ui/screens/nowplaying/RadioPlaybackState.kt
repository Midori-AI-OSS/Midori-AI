package xyz.midoriai.radio.ui.screens.nowplaying

sealed interface RadioPlaybackState {
    data object Idle : RadioPlaybackState

    data object Connecting : RadioPlaybackState

    data class SwitchingChannel(
        val channel: String,
    ) : RadioPlaybackState

    data object Playing : RadioPlaybackState

    data class Reconnecting(
        val attempt: Int,
        val nextDelayMs: Long,
    ) : RadioPlaybackState

    data class Unavailable(
        val error: String,
    ) : RadioPlaybackState

    data object Stopped : RadioPlaybackState
}
