package xyz.midoriai.radio.ui.screens.nowplaying

import android.app.Application
import android.content.pm.ApplicationInfo
import android.util.Log
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.PlaybackException
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import xyz.midoriai.radio.radioapi.ArtPayload
import xyz.midoriai.radio.radioapi.CurrentPayload
import xyz.midoriai.radio.radioapi.HealthPayload
import xyz.midoriai.radio.radioapi.OkHttpRadioApi
import xyz.midoriai.radio.radioapi.RadioApi
import xyz.midoriai.radio.radioapi.RadioApiDefaults
import xyz.midoriai.radio.radioapi.RadioApiFailure
import xyz.midoriai.radio.radioapi.RadioApiResult
import xyz.midoriai.radio.radioapi.buildStreamUrl
import xyz.midoriai.radio.radioapi.normalizeQuality
import xyz.midoriai.radio.settings.RadioSettingsRepository

class NowPlayingViewModel(
    application: Application,
) : AndroidViewModel(application) {
    private val reconnectDelaysMs: List<Long> = listOf(1000L, 2000L, 4000L, 8000L, 16000L, 30000L)
    private val playingMetadataPollIntervalMs = 5000L
    private val idleMetadataPollIntervalMs = 20000L
    private val channelRefreshIntervalMs = 60000L
    private val healthPollIntervalMs = 30000L
    private val channelSwitchFadeDurationMs = 220L
    private val adjacentArtPrefetchCooldownMs = 15000L
    private val playerVolumeNormal = 1f

    private val isDebugBuild: Boolean = (
        getApplication<Application>().applicationInfo.flags and ApplicationInfo.FLAG_DEBUGGABLE
        ) != 0

    private val settingsRepository = RadioSettingsRepository(application)
    private val api: RadioApi = OkHttpRadioApi()

    val selectedChannel: StateFlow<String> = settingsRepository.channel
        .stateIn(viewModelScope, SharingStarted.Eagerly, "all")

    val selectedQuality: StateFlow<String> = settingsRepository.quality
        .stateIn(viewModelScope, SharingStarted.Eagerly, "medium")

    private val player: ExoPlayer = ExoPlayer.Builder(application)
        .build()
        .also { exo ->
            exo.setAudioAttributes(
                AudioAttributes.Builder()
                    .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                    .setUsage(C.USAGE_MEDIA)
                    .build(),
                true,
            )
            exo.volume = playerVolumeNormal
            exo.addListener(PlayerEventListener())
        }

    private val _playbackState = MutableStateFlow<RadioPlaybackState>(RadioPlaybackState.Idle)
    val playbackState: StateFlow<RadioPlaybackState> = _playbackState.asStateFlow()

    private val _currentTrack = MutableStateFlow<CurrentPayload?>(null)
    val currentTrack: StateFlow<CurrentPayload?> = _currentTrack.asStateFlow()

    private val _art = MutableStateFlow<ArtPayload?>(null)
    val art: StateFlow<ArtPayload?> = _art.asStateFlow()

    private val _health = MutableStateFlow<HealthPayload?>(null)
    val health: StateFlow<HealthPayload?> = _health.asStateFlow()

    private val _lastError = MutableStateFlow<String?>(null)
    val lastError: StateFlow<String?> = _lastError.asStateFlow()

    private val _activeQuality = MutableStateFlow("medium")
    val activeQuality: StateFlow<String> = _activeQuality.asStateFlow()

    private val _pendingQuality = MutableStateFlow<String?>(null)
    val pendingQuality: StateFlow<String?> = _pendingQuality.asStateFlow()

    private val _channels = MutableStateFlow(listOf("all"))
    val channels: StateFlow<List<String>> = combine(_channels, selectedChannel) { fetched, selected ->
        val normalizedSelected = normalizePersistedChannel(selected)
        ensureAllChannel((fetched + listOf(normalizedSelected)).distinct())
    }.stateIn(viewModelScope, SharingStarted.Eagerly, listOf("all"))

    private val _channelsError = MutableStateFlow<String?>(null)
    val channelsError: StateFlow<String?> = _channelsError.asStateFlow()

    private val _channelsLoading = MutableStateFlow(false)
    val channelsLoading: StateFlow<Boolean> = _channelsLoading.asStateFlow()

    private val artByChannel: MutableMap<String, ArtPayload> = mutableMapOf()
    private val artFetchInFlight: MutableSet<String> = mutableSetOf()
    private val artFetchAtMsByChannel: MutableMap<String, Long> = mutableMapOf()

    private var playbackDesired: Boolean = false
    private var reconnectAttempt: Int = 0
    private var reconnectJob: Job? = null
    private var channelSwitchJob: Job? = null
    private var metadataPollJob: Job? = null
    private var channelPollJob: Job? = null
    private var healthPollJob: Job? = null
    private var connectGeneration: Long = 0
    private var lastObservedChannel: String? = null
    private var lastObservedQuality: String? = null

    init {
        startMetadataPolling()
        startChannelPolling()
        startHealthPolling()

        viewModelScope.launch {
            selectedChannel
                .collect { channel ->
                    val normalized = normalizePersistedChannel(channel)

                    if (lastObservedChannel == null) {
                        lastObservedChannel = normalized
                        publishCachedArtForSelectedChannel(normalized)
                        viewModelScope.launch {
                            refreshSelectedAndAdjacentArt(
                                selected = normalized,
                                forceSelectedRefresh = true,
                            )
                        }
                        return@collect
                    }

                    lastObservedChannel = normalized
                    publishCachedArtForSelectedChannel(normalized)

                    if (playbackDesired) {
                        switchChannelWithFade(normalized)
                    } else {
                        viewModelScope.launch {
                            refreshSelectedAndAdjacentArt(
                                selected = normalized,
                                forceSelectedRefresh = true,
                            )
                        }
                    }
                }
        }

        viewModelScope.launch {
            selectedQuality
                .collect { quality ->
                    val normalized = normalizeQuality(quality)
                    if (lastObservedQuality == null) {
                        lastObservedQuality = normalized
                        _activeQuality.value = normalized
                        return@collect
                    }

                    lastObservedQuality = normalized
                    if (playbackDesired) {
                        _pendingQuality.value = normalized
                    } else {
                        _activeQuality.value = normalized
                        _pendingQuality.value = null
                    }
                }
        }
    }

    fun play() {
        if (playbackDesired) {
            return
        }

        playbackDesired = true
        reconnectAttempt = 0
        player.volume = playerVolumeNormal
        connectToSelectedStream(RadioPlaybackState.Connecting)
    }

    fun pause() {
        playbackDesired = false
        reconnectJob?.cancel()
        reconnectJob = null
        channelSwitchJob?.cancel()
        channelSwitchJob = null

        player.playWhenReady = false
        player.pause()
        player.volume = playerVolumeNormal
        _playbackState.value = RadioPlaybackState.Stopped
    }

    fun retry() {
        playbackDesired = true
        reconnectAttempt = 0
        player.volume = playerVolumeNormal
        connectToSelectedStream(RadioPlaybackState.Connecting)
    }

    fun selectAdjacentChannel(direction: Int) {
        val available = channels.value
        if (available.isEmpty()) {
            return
        }

        val selected = normalizePersistedChannel(selectedChannel.value)
        val currentIndex = available.indexOf(selected).let { if (it >= 0) it else 0 }
        val nextIndex = floorMod(currentIndex + direction, available.size)
        setChannel(available[nextIndex])
    }

    fun setQuality(quality: String) {
        viewModelScope.launch {
            settingsRepository.setQuality(quality)
        }
    }

    private fun setChannel(channel: String) {
        viewModelScope.launch {
            settingsRepository.setChannel(channel)
        }
    }

    private fun switchChannelWithFade(channel: String) {
        channelSwitchJob?.cancel()
        channelSwitchJob = viewModelScope.launch {
            if (!playbackDesired) {
                return@launch
            }

            reconnectAttempt = 0
            _playbackState.value = RadioPlaybackState.SwitchingChannel(toChannelLabel(channel))

            fadePlayerVolume(0f, channelSwitchFadeDurationMs)
            connectToSelectedStream(
                defaultState = RadioPlaybackState.Connecting,
                channelOverride = channel,
            )
            fadePlayerVolume(playerVolumeNormal, channelSwitchFadeDurationMs)

            pollCurrentOnce()
            pollArtOnce()
        }
    }

    private fun connectToSelectedStream(
        defaultState: RadioPlaybackState,
        channelOverride: String? = null,
    ) {
        reconnectJob?.cancel()
        reconnectJob = null
        connectGeneration += 1

        val channel = normalizePersistedChannel(channelOverride ?: selectedChannel.value)
        val quality = resolveQualityForConnect()
        val streamUrl = buildStreamUrl(
            baseUrl = RadioApiDefaults.DEFAULT_BASE_URL,
            channel = channel,
            quality = quality,
        )

        if (isDebugBuild) {
            Log.d(
                "MidoriAIRadio",
                "Radio endpoints: stream=$streamUrl current=/radio/v1/current art=/radio/v1/art artImage=/radio/v1/art/image health=/health reconnectDelaysMs=$reconnectDelaysMs",
            )
        }

        _playbackState.value = defaultState
        _lastError.value = null

        player.volume = playerVolumeNormal
        player.setMediaItem(MediaItem.fromUri(streamUrl))
        player.prepare()
        player.playWhenReady = true
    }

    private fun queueReconnect(reason: String) {
        if (!playbackDesired) {
            return
        }

        reconnectJob?.cancel()
        reconnectJob = null

        reconnectAttempt += 1
        val delayIndex = (reconnectAttempt - 1).coerceAtMost(reconnectDelaysMs.lastIndex)
        val delayMs = reconnectDelaysMs[delayIndex]
        val capturedGeneration = connectGeneration

        _playbackState.value = RadioPlaybackState.Reconnecting(reconnectAttempt, delayMs)
        _lastError.value = reason

        reconnectJob = viewModelScope.launch {
            delay(delayMs)
            if (!playbackDesired || capturedGeneration != connectGeneration) {
                return@launch
            }

            connectToSelectedStream(RadioPlaybackState.Connecting)
        }
    }

    private fun resolveQualityForConnect(): String {
        val queuedQuality = _pendingQuality.value
        if (!queuedQuality.isNullOrBlank()) {
            val normalized = normalizeQuality(queuedQuality)
            _activeQuality.value = normalized
            _pendingQuality.value = null
            return normalized
        }

        val active = normalizeQuality(_activeQuality.value)
        if (active != _activeQuality.value) {
            _activeQuality.value = active
        }

        return active
    }

    private fun startMetadataPolling() {
        if (metadataPollJob?.isActive == true) {
            return
        }

        metadataPollJob = viewModelScope.launch {
            while (isActive) {
                pollCurrentOnce()
                pollArtOnce()
                val delayMs = if (playbackDesired) {
                    playingMetadataPollIntervalMs
                } else {
                    idleMetadataPollIntervalMs
                }
                delay(delayMs)
            }
        }
    }

    private fun startChannelPolling() {
        if (channelPollJob?.isActive == true) {
            return
        }

        channelPollJob = viewModelScope.launch {
            while (isActive) {
                refreshChannels()
                delay(channelRefreshIntervalMs)
            }
        }
    }

    private fun startHealthPolling() {
        if (healthPollJob?.isActive == true) {
            return
        }

        healthPollJob = viewModelScope.launch {
            while (isActive) {
                pollHealthOnce()
                delay(healthPollIntervalMs)
            }
        }
    }

    private suspend fun refreshChannels() {
        _channelsLoading.value = true
        _channelsError.value = null
        var resolvedChannels = ensureAllChannel(_channels.value)

        try {
            when (val result = api.fetchChannels()) {
                is RadioApiResult.Success -> {
                    val merged = result.data.channels
                        .map { normalizePersistedChannel(it.name) }
                        .filter { it.isNotBlank() && it != "all" }
                        .distinct()

                    resolvedChannels = ensureAllChannel(merged)
                    _channels.value = resolvedChannels
                }

                is RadioApiResult.Failure -> {
                    _channelsError.value = toFailureText(result.failure)
                    resolvedChannels = ensureAllChannel(_channels.value)
                    _channels.value = resolvedChannels
                }
            }
        } catch (exc: Exception) {
            _channelsError.value = exc.message ?: "Failed to load channels"
            resolvedChannels = ensureAllChannel(_channels.value)
            _channels.value = resolvedChannels
        }

        _channelsLoading.value = false

        pruneArtCache(resolvedChannels)
        publishCachedArtForSelectedChannel(selectedChannel.value)
        try {
            refreshSelectedAndAdjacentArt(
                selected = selectedChannel.value,
                forceSelectedRefresh = false,
            )
        } catch (exc: CancellationException) {
            throw exc
        } catch (_: Exception) {
            // Preserve existing channel data even when neighbor prefetch fails.
        }
    }

    private suspend fun pollCurrentOnce() {
        try {
            when (val result = api.fetchCurrent(channel = selectedChannel.value)) {
                is RadioApiResult.Success -> {
                    _currentTrack.value = result.data
                }

                is RadioApiResult.Failure -> {
                    _lastError.value = toFailureText(result.failure)
                }
            }
        } catch (exc: CancellationException) {
            throw exc
        } catch (exc: Exception) {
            _lastError.value = exc.message ?: "Current polling failed"
        }
    }

    private suspend fun pollArtOnce() {
        val selected = normalizePersistedChannel(selectedChannel.value)
        try {
            refreshSelectedAndAdjacentArt(
                selected = selected,
                forceSelectedRefresh = true,
            )
        } catch (exc: CancellationException) {
            throw exc
        } catch (exc: Exception) {
            _lastError.value = exc.message ?: "Art polling failed"
        }
    }

    private suspend fun refreshSelectedAndAdjacentArt(
        selected: String,
        forceSelectedRefresh: Boolean,
    ) {
        val normalizedSelected = normalizePersistedChannel(selected)
        fetchArtForChannel(
            channel = normalizedSelected,
            forceRefresh = forceSelectedRefresh,
            isPrefetch = false,
        )

        val adjacentChannels = selectedAndAdjacentChannels(normalizedSelected)
            .filter { it != normalizedSelected }

        adjacentChannels.forEach { channel ->
            fetchArtForChannel(
                channel = channel,
                forceRefresh = false,
                isPrefetch = true,
            )
        }
    }

    private suspend fun fetchArtForChannel(
        channel: String,
        forceRefresh: Boolean,
        isPrefetch: Boolean,
    ) {
        val normalizedChannel = normalizePersistedChannel(channel)
        val selected = normalizePersistedChannel(selectedChannel.value)
        val cached = artByChannel[normalizedChannel]
        val nowMs = System.currentTimeMillis()
        val lastFetchAt = artFetchAtMsByChannel[normalizedChannel] ?: 0L
        val withinPrefetchCooldown = nowMs - lastFetchAt < adjacentArtPrefetchCooldownMs

        if (normalizedChannel == selected && cached != null) {
            _art.value = cached
        }

        if (isPrefetch && cached != null && withinPrefetchCooldown) {
            return
        }

        if (!isPrefetch && !forceRefresh && cached != null) {
            return
        }

        if (!artFetchInFlight.add(normalizedChannel)) {
            return
        }

        try {
            when (val result = api.fetchArt(channel = normalizedChannel)) {
                is RadioApiResult.Success -> {
                    val payload = result.data
                    artByChannel[normalizedChannel] = payload
                    artFetchAtMsByChannel[normalizedChannel] = System.currentTimeMillis()

                    if (normalizedChannel == normalizePersistedChannel(selectedChannel.value)) {
                        _art.value = payload
                    }
                }

                is RadioApiResult.Failure -> {
                    if (!isPrefetch && normalizedChannel == normalizePersistedChannel(selectedChannel.value)) {
                        _lastError.value = toFailureText(result.failure)
                    }
                }
            }
        } catch (exc: CancellationException) {
            throw exc
        } catch (exc: Exception) {
            if (!isPrefetch && normalizedChannel == normalizePersistedChannel(selectedChannel.value)) {
                _lastError.value = exc.message ?: "Art polling failed"
            }
        } finally {
            artFetchInFlight.remove(normalizedChannel)
        }
    }

    private fun publishCachedArtForSelectedChannel(channel: String) {
        val normalized = normalizePersistedChannel(channel)
        val cached = artByChannel[normalized] ?: return
        _art.value = cached
    }

    private fun selectedAndAdjacentChannels(selected: String): List<String> {
        val available = channels.value
        if (available.isEmpty()) {
            return listOf(normalizePersistedChannel(selected))
        }

        val normalizedSelected = normalizePersistedChannel(selected)
        val selectedIndex = available.indexOf(normalizedSelected).let { if (it >= 0) it else 0 }
        val center = normalizePersistedChannel(available[selectedIndex])
        if (available.size == 1) {
            return listOf(center)
        }

        val previous = normalizePersistedChannel(
            available[floorMod(selectedIndex - 1, available.size)],
        )
        val next = normalizePersistedChannel(
            available[floorMod(selectedIndex + 1, available.size)],
        )

        return listOf(center, previous, next).distinct()
    }

    private fun pruneArtCache(validChannels: List<String>) {
        val allowedChannels = (validChannels + selectedChannel.value)
            .map { normalizePersistedChannel(it) }
            .toSet()

        artByChannel.keys.removeAll { it !in allowedChannels }
        artFetchAtMsByChannel.keys.removeAll { it !in allowedChannels }
        artFetchInFlight.removeAll { it !in allowedChannels }
    }

    private suspend fun pollHealthOnce() {
        try {
            when (val result = api.fetchHealth()) {
                is RadioApiResult.Success -> {
                    _health.value = result.data
                }

                is RadioApiResult.Failure -> {
                    _lastError.value = toFailureText(result.failure)
                }
            }
        } catch (exc: CancellationException) {
            throw exc
        } catch (exc: Exception) {
            _lastError.value = exc.message ?: "Health polling failed"
        }
    }

    private suspend fun fadePlayerVolume(target: Float, durationMs: Long) {
        val clampedTarget = target.coerceIn(0f, 1f)
        val start = player.volume.coerceIn(0f, 1f)
        if (durationMs <= 0L || start == clampedTarget) {
            player.volume = clampedTarget
            return
        }

        val steps = 8
        val stepDuration = (durationMs / steps).coerceAtLeast(1L)
        repeat(steps) { index ->
            val progress = (index + 1) / steps.toFloat()
            player.volume = start + ((clampedTarget - start) * progress)
            delay(stepDuration)
        }

        player.volume = clampedTarget
    }

    private fun ensureAllChannel(values: List<String>): List<String> {
        val normalized = values
            .map { normalizePersistedChannel(it) }
            .filter { it.isNotBlank() && it != "all" }
            .distinct()
        return listOf("all") + normalized
    }

    private fun normalizePersistedChannel(value: String): String {
        val raw = value.trim().lowercase()
        return if (raw.isBlank()) {
            "all"
        } else {
            raw
        }
    }

    private fun toChannelLabel(channel: String): String {
        return if (channel == "all") {
            "All"
        } else {
            channel
        }
    }

    private fun handlePlayerError(error: PlaybackException) {
        val message = error.message?.trim().orEmpty()
        queueReconnect(if (message.isNotEmpty()) message else "Playback error")
    }

    private fun toFailureText(failure: RadioApiFailure): String {
        return when (failure) {
            is RadioApiFailure.Http -> "HTTP ${failure.status}: ${failure.message}"
            is RadioApiFailure.InvalidEnvelope -> failure.message
            is RadioApiFailure.Network -> failure.message
            is RadioApiFailure.NullData -> failure.message
            is RadioApiFailure.UnsupportedVersion -> "Unsupported API version: ${failure.version}"
            is RadioApiFailure.Upstream -> "${failure.code}: ${failure.message}"
        }
    }

    private fun floorMod(value: Int, modulus: Int): Int {
        if (modulus <= 0) {
            return 0
        }

        val remainder = value % modulus
        return if (remainder < 0) {
            remainder + modulus
        } else {
            remainder
        }
    }

    override fun onCleared() {
        reconnectJob?.cancel()
        reconnectJob = null
        channelSwitchJob?.cancel()
        channelSwitchJob = null
        metadataPollJob?.cancel()
        metadataPollJob = null
        channelPollJob?.cancel()
        channelPollJob = null
        healthPollJob?.cancel()
        healthPollJob = null
        player.release()
        super.onCleared()
    }

    private inner class PlayerEventListener : Player.Listener {
        override fun onPlayerError(error: PlaybackException) {
            handlePlayerError(error)
        }

        override fun onIsPlayingChanged(isPlaying: Boolean) {
            if (!playbackDesired) {
                return
            }

            if (isPlaying) {
                reconnectAttempt = 0
                _playbackState.value = RadioPlaybackState.Playing
                _lastError.value = null
                player.volume = playerVolumeNormal
            }
        }

        override fun onPlaybackStateChanged(playbackState: Int) {
            if (!playbackDesired) {
                return
            }

            if (playbackState == Player.STATE_READY && player.playWhenReady && player.isPlaying) {
                reconnectAttempt = 0
                _playbackState.value = RadioPlaybackState.Playing
                _lastError.value = null
                player.volume = playerVolumeNormal
            }

            if (playbackState == Player.STATE_ENDED) {
                queueReconnect("Stream ended")
            }
        }

        override fun onPlayWhenReadyChanged(playWhenReady: Boolean, reason: Int) {
            if (!playbackDesired && !playWhenReady) {
                _playbackState.value = RadioPlaybackState.Stopped
            }
        }
    }
}
