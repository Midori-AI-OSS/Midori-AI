package xyz.midoriai.radio.ui.screens.nowplaying

import android.content.Context
import android.graphics.Bitmap
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FastForward
import androidx.compose.material.icons.filled.FastRewind
import androidx.compose.material.icons.filled.HighQuality
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.RectangleShape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.palette.graphics.Palette
import coil.compose.AsyncImage
import coil.imageLoader
import coil.request.ImageRequest
import coil.request.SuccessResult
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers
import java.time.Duration
import java.time.LocalDateTime
import java.time.temporal.ChronoUnit
import java.util.Locale
import kotlin.math.cos
import kotlin.math.sin

private const val CHANNEL_TRANSITION_DURATION_MS = 320
private const val CHANNEL_SWIPE_LOCK_MS = 500L
private const val GRADIENT_TRANSITION_DURATION_MS = 820

@Composable
fun NowPlayingScreen(
    modifier: Modifier = Modifier,
    viewModel: NowPlayingViewModel = viewModel(),
) {
    val playbackState = viewModel.playbackState.collectAsState().value
    val currentTrack = viewModel.currentTrack.collectAsState().value
    val art = viewModel.art.collectAsState().value
    val channels = viewModel.channels.collectAsState().value
    val selectedChannel = viewModel.selectedChannel.collectAsState().value
    val selectedQuality = viewModel.selectedQuality.collectAsState().value
    val pendingQuality = viewModel.pendingQuality.collectAsState().value

    val isActivelyPlaying = playbackState is RadioPlaybackState.Playing ||
        playbackState is RadioPlaybackState.Connecting ||
        playbackState is RadioPlaybackState.Reconnecting ||
        playbackState is RadioPlaybackState.SwitchingChannel

    val normalizedSelectedChannel = normalizeChannelKey(selectedChannel)
    val artForSelectedChannel = art?.takeIf {
        it.hasArt && normalizeChannelKey(it.channel) == normalizedSelectedChannel
    }
    val currentTrackForSelectedChannel = currentTrack?.takeIf {
        normalizeChannelKey(it.channel) == normalizedSelectedChannel
    }

    val isArtForCurrentTrack = if (currentTrackForSelectedChannel != null && artForSelectedChannel != null) {
        artForSelectedChannel.trackId == currentTrackForSelectedChannel.trackId
    } else {
        true
    }

    val artUrl = if (isArtForCurrentTrack) {
        artForSelectedChannel?.artUrl
    } else {
        null
    }
    val trackId = currentTrackForSelectedChannel?.trackId ?: artForSelectedChannel?.trackId ?: "unknown"
    val trackTitle = currentTrackForSelectedChannel?.title ?: "Fetching current track..."
    val imageCacheKey = "${normalizedSelectedChannel}_${trackId}_${artUrl.orEmpty()}"

    val liveSnapshot = NowPlayingVisualState(
        channel = normalizedSelectedChannel,
        channelSubtitle = toChannelSubtitle(normalizedSelectedChannel),
        title = trackTitle,
        artUrl = artUrl,
        imageCacheKey = imageCacheKey,
    )

    var renderedSnapshot by remember { mutableStateOf<NowPlayingVisualState?>(null) }
    var activeTransition by remember { mutableStateOf<HeroTransitionState?>(null) }
    val heroSlideProgress = remember { Animatable(1f) }

    val liveSnapshotState by rememberUpdatedState(liveSnapshot)
    val context = LocalContext.current

    val neutralDarkGradient = remember {
        PaletteGradient(
            top = Color(0xFF171A20),
            middle = Color(0xFF1E232A),
            bottom = Color(0xFF14171D),
        )
    }
    var targetGradient by remember { mutableStateOf(neutralDarkGradient) }
    var hourSeedBucket by remember { mutableStateOf(currentHourSeedBucket()) }

    val backgroundSeed = remember(
        liveSnapshot.title,
        liveSnapshot.channel,
        hourSeedBucket,
    ) {
        buildBackgroundSeed(
            title = liveSnapshot.title,
            channel = liveSnapshot.channel,
            hourBucket = hourSeedBucket,
        )
    }

    val targetBackgroundPattern = remember(targetGradient, backgroundSeed) {
        buildDynamicBackgroundPattern(
            palette = targetGradient,
            seed = backgroundSeed,
        )
    }

    val animatedBackgroundBase by animateColorAsState(
        targetValue = targetBackgroundPattern.base,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundBase",
    )
    val animatedBackgroundLayerOne by animateColorAsState(
        targetValue = targetBackgroundPattern.layerOne,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundLayerOne",
    )
    val animatedBackgroundLayerTwo by animateColorAsState(
        targetValue = targetBackgroundPattern.layerTwo,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundLayerTwo",
    )
    val animatedBackgroundLayerThree by animateColorAsState(
        targetValue = targetBackgroundPattern.layerThree,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundLayerThree",
    )
    val animatedBackgroundGlowOne by animateColorAsState(
        targetValue = targetBackgroundPattern.glowOne,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundGlowOne",
    )
    val animatedBackgroundGlowTwo by animateColorAsState(
        targetValue = targetBackgroundPattern.glowTwo,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundGlowTwo",
    )
    val animatedStopOne by animateFloatAsState(
        targetValue = targetBackgroundPattern.stopOne,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundStopOne",
    )
    val animatedStopTwo by animateFloatAsState(
        targetValue = targetBackgroundPattern.stopTwo,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundStopTwo",
    )
    val animatedAngleDegrees by animateFloatAsState(
        targetValue = targetBackgroundPattern.angleDegrees,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundAngle",
    )
    val animatedGlowOneX by animateFloatAsState(
        targetValue = targetBackgroundPattern.glowOneX,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundGlowOneX",
    )
    val animatedGlowOneY by animateFloatAsState(
        targetValue = targetBackgroundPattern.glowOneY,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundGlowOneY",
    )
    val animatedGlowTwoX by animateFloatAsState(
        targetValue = targetBackgroundPattern.glowTwoX,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundGlowTwoX",
    )
    val animatedGlowTwoY by animateFloatAsState(
        targetValue = targetBackgroundPattern.glowTwoY,
        animationSpec = tween(
            durationMillis = GRADIENT_TRANSITION_DURATION_MS,
            easing = FastOutSlowInEasing,
        ),
        label = "backgroundGlowTwoY",
    )

    val swipeThresholdPx = with(LocalDensity.current) { 72.dp.toPx() }
    var horizontalDragAmount by remember { mutableFloatStateOf(0f) }
    var switchDirection by remember { mutableIntStateOf(1) }
    var isSwipeLocked by remember { mutableStateOf(false) }
    var swipeUnlockJob by remember { mutableStateOf<Job?>(null) }
    val swipeScope = rememberCoroutineScope()

    LaunchedEffect(liveSnapshot) {
        if (renderedSnapshot == null) {
            renderedSnapshot = liveSnapshot
        }

        if (activeTransition == null && renderedSnapshot?.channel == normalizedSelectedChannel) {
            renderedSnapshot = liveSnapshot
        }

    }

    LaunchedEffect(liveSnapshot.artUrl, liveSnapshot.imageCacheKey) {
        val candidateUrl = liveSnapshot.artUrl
        if (candidateUrl.isNullOrBlank()) {
            targetGradient = neutralDarkGradient
            return@LaunchedEffect
        }

        val extracted = extractPaletteGradient(
            context = context,
            artUrl = candidateUrl,
            imageCacheKey = liveSnapshot.imageCacheKey,
            fallbackGradient = neutralDarkGradient,
        )
        if (extracted != null) {
            targetGradient = extracted
        } else {
            targetGradient = neutralDarkGradient
        }
    }

    LaunchedEffect(Unit) {
        while (true) {
            delay(millisUntilNextHour())
            hourSeedBucket = currentHourSeedBucket()
        }
    }

    LaunchedEffect(normalizedSelectedChannel) {
        val fromSnapshot = renderedSnapshot ?: liveSnapshotState

        if (fromSnapshot.channel == normalizedSelectedChannel) {
            renderedSnapshot = liveSnapshotState
            return@LaunchedEffect
        }

        val toSnapshot = liveSnapshotState

        activeTransition = HeroTransitionState(
            from = fromSnapshot,
            to = toSnapshot,
            direction = switchDirection,
        )

        heroSlideProgress.snapTo(0f)
        heroSlideProgress.animateTo(
            targetValue = 1f,
            animationSpec = tween(
                durationMillis = CHANNEL_TRANSITION_DURATION_MS,
                easing = FastOutSlowInEasing,
            ),
        )

        renderedSnapshot = liveSnapshotState
        activeTransition = null
    }

    fun requestChannelChange(direction: Int) {
        if (isSwipeLocked || channels.size <= 1 || direction == 0) {
            return
        }

        switchDirection = if (direction >= 0) 1 else -1
        isSwipeLocked = true
        swipeUnlockJob?.cancel()
        swipeUnlockJob = swipeScope.launch {
            delay(CHANNEL_SWIPE_LOCK_MS)
            isSwipeLocked = false
        }
        viewModel.selectAdjacentChannel(direction)
    }

    val swipeModifier = Modifier.pointerInput(
        channels,
        selectedChannel,
        swipeThresholdPx,
        isSwipeLocked,
    ) {
        detectHorizontalDragGestures(
            onDragStart = {
                horizontalDragAmount = 0f
            },
            onHorizontalDrag = { _, dragAmount ->
                horizontalDragAmount += dragAmount
            },
            onDragEnd = {
                when {
                    horizontalDragAmount <= -swipeThresholdPx -> {
                        requestChannelChange(1)
                    }

                    horizontalDragAmount >= swipeThresholdPx -> {
                        requestChannelChange(-1)
                    }
                }
                horizontalDragAmount = 0f
            },
            onDragCancel = {
                horizontalDragAmount = 0f
            },
        )
    }

    val visibleSnapshot = renderedSnapshot ?: liveSnapshot

    Box(
        modifier = modifier
            .fillMaxSize()
            .then(swipeModifier),
    ) {
        Box(
            modifier = Modifier
                .matchParentSize()
                .drawWithCache {
                    val angleRadians = Math.toRadians(animatedAngleDegrees.toDouble())
                    val directionX = cos(angleRadians).toFloat()
                    val directionY = sin(angleRadians).toFloat()
                    val center = Offset(
                        x = size.width / 2f,
                        y = size.height / 2f,
                    )
                    val travelDistance = size.maxDimension * 0.82f
                    val start = Offset(
                        x = center.x - (directionX * travelDistance),
                        y = center.y - (directionY * travelDistance),
                    )
                    val end = Offset(
                        x = center.x + (directionX * travelDistance),
                        y = center.y + (directionY * travelDistance),
                    )
                    val layeredBlend = Brush.linearGradient(
                        colorStops = arrayOf(
                            0f to animatedBackgroundBase,
                            animatedStopOne to animatedBackgroundLayerOne,
                            animatedStopTwo to animatedBackgroundLayerTwo,
                            1f to animatedBackgroundLayerThree,
                        ),
                        start = start,
                        end = end,
                    )
                    val glowBrushOne = Brush.radialGradient(
                        colors = listOf(
                            animatedBackgroundGlowOne.copy(alpha = 0.58f),
                            Color.Transparent,
                        ),
                        center = Offset(
                            x = size.width * animatedGlowOneX,
                            y = size.height * animatedGlowOneY,
                        ),
                        radius = size.maxDimension * 0.90f,
                    )
                    val glowBrushTwo = Brush.radialGradient(
                        colors = listOf(
                            animatedBackgroundGlowTwo.copy(alpha = 0.52f),
                            Color.Transparent,
                        ),
                        center = Offset(
                            x = size.width * animatedGlowTwoX,
                            y = size.height * animatedGlowTwoY,
                        ),
                        radius = size.maxDimension * 0.96f,
                    )

                    onDrawBehind {
                        drawRect(color = animatedBackgroundBase)
                        drawRect(brush = layeredBlend)
                        drawRect(brush = glowBrushOne)
                        drawRect(brush = glowBrushTwo)
                        drawRect(color = Color.Black.copy(alpha = 0.16f))
                    }
                },
        )

        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .padding(horizontal = 18.dp, vertical = 18.dp),
                contentAlignment = Alignment.Center,
            ) {
                BoxWithConstraints(
                    modifier = Modifier.fillMaxWidth(),
                    contentAlignment = Alignment.Center,
                ) {
                    val artSize = when {
                        maxWidth <= 420.dp -> 224.dp
                        maxWidth < 600.dp -> 252.dp
                        else -> 320.dp
                    }
                    val titleFontSize = when {
                        maxWidth <= 420.dp -> 24.sp
                        maxWidth < 600.dp -> 26.sp
                        else -> 30.sp
                    }
                    val titleLineHeight = when {
                        maxWidth <= 420.dp -> 30.sp
                        maxWidth < 600.dp -> 32.sp
                        else -> 36.sp
                    }
                    val titleStyle = MaterialTheme.typography.titleLarge.copy(
                        fontSize = titleFontSize,
                        lineHeight = titleLineHeight,
                    )

                    val transition = activeTransition
                    val heroTravelWidth = maxWidth

                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clipToBounds(),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (transition != null) {
                            val progress = heroSlideProgress.value.coerceIn(0f, 1f)
                            val directionSign = if (transition.direction >= 0) 1f else -1f
                            val slideDistancePx = with(LocalDensity.current) { heroTravelWidth.toPx() }
                            val outgoingOffset = -directionSign * slideDistancePx * progress
                            val incomingOffset = directionSign * slideDistancePx * (1f - progress)

                            NowPlayingHeroCard(
                                snapshot = transition.from,
                                artSize = artSize,
                                titleStyle = titleStyle,
                                modifier = Modifier.graphicsLayer {
                                    translationX = outgoingOffset
                                    alpha = 1f - (0.10f * progress)
                                },
                            )

                            NowPlayingHeroCard(
                                snapshot = transition.to,
                                artSize = artSize,
                                titleStyle = titleStyle,
                                modifier = Modifier.graphicsLayer {
                                    translationX = incomingOffset
                                    alpha = 0.70f + (0.30f * progress)
                                },
                            )
                        } else {
                            NowPlayingHeroCard(
                                snapshot = visibleSnapshot,
                                artSize = artSize,
                                titleStyle = titleStyle,
                            )
                        }
                    }
                }
            }

            NowPlayingControlDock(
                isActivelyPlaying = isActivelyPlaying,
                frostColor = animatedBackgroundBase,
                selectedQuality = selectedQuality,
                pendingQuality = pendingQuality,
                onPreviousChannel = {
                    requestChannelChange(-1)
                },
                onPlayPause = {
                    if (isActivelyPlaying) {
                        viewModel.pause()
                    } else {
                        viewModel.play()
                    }
                },
                onNextChannel = {
                    requestChannelChange(1)
                },
                onQualitySelected = viewModel::setQuality,
            )
        }
    }
}

@Composable
private fun NowPlayingHeroCard(
    modifier: Modifier = Modifier,
    snapshot: NowPlayingVisualState,
    artSize: Dp,
    titleStyle: TextStyle,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        if (!snapshot.artUrl.isNullOrBlank()) {
            AsyncImage(
                model = ImageRequest.Builder(LocalContext.current)
                    .data(snapshot.artUrl)
                    .memoryCacheKey(snapshot.imageCacheKey)
                    .diskCacheKey(snapshot.imageCacheKey)
                    .crossfade(false)
                    .build(),
                contentDescription = snapshot.title,
                modifier = Modifier
                    .size(artSize)
                    .aspectRatio(1f),
                contentScale = ContentScale.Crop,
            )
        } else {
            Box(
                modifier = Modifier
                    .size(artSize)
                    .aspectRatio(1f)
                    .background(
                        Brush.linearGradient(
                            colors = listOf(
                                MaterialTheme.colorScheme.surfaceVariant,
                                MaterialTheme.colorScheme.surface,
                            ),
                        ),
                    ),
            )
        }

        Spacer(modifier = Modifier.height(14.dp))

        Text(
            text = snapshot.title,
            style = titleStyle,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 2.dp),
        )

        Text(
            text = snapshot.channelSubtitle,
            style = MaterialTheme.typography.bodyMedium.copy(
                fontSize = 13.sp,
                lineHeight = 18.sp,
            ),
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.58f),
            textAlign = TextAlign.Center,
            modifier = Modifier.padding(top = 6.dp),
        )
    }
}

@Composable
private fun NowPlayingControlDock(
    modifier: Modifier = Modifier,
    isActivelyPlaying: Boolean,
    frostColor: Color,
    selectedQuality: String,
    pendingQuality: String?,
    onPreviousChannel: () -> Unit,
    onPlayPause: () -> Unit,
    onNextChannel: () -> Unit,
    onQualitySelected: (String) -> Unit,
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .wrapContentHeight()
            .heightIn(min = 118.dp),
        color = Color.Transparent,
        shape = RectangleShape,
        tonalElevation = 0.dp,
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clipToBounds(),
        ) {
            Box(
                modifier = Modifier
                    .matchParentSize()
                    .background(frostColor.copy(alpha = 0.34f))
                    .blur(24.dp),
            )

            Box(
                modifier = Modifier
                    .matchParentSize()
                    .background(Color.White.copy(alpha = 0.26f)),
            )

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 18.dp)
                    .navigationBarsPadding(),
            ) {
            Row(
                modifier = Modifier.align(Alignment.Center),
                horizontalArrangement = Arrangement.Center,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                ControlIconButton(
                    icon = Icons.Filled.FastRewind,
                    contentDescription = "Previous channel",
                    buttonSize = 56.dp,
                    iconSize = 30.dp,
                    onClick = onPreviousChannel,
                    iconTint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.88f),
                )

                androidx.compose.foundation.layout.Spacer(modifier = Modifier.size(18.dp))

                ControlIconButton(
                    icon = if (isActivelyPlaying) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                    contentDescription = if (isActivelyPlaying) "Pause playback" else "Play playback",
                    buttonSize = 68.dp,
                    iconSize = 38.dp,
                    onClick = onPlayPause,
                    iconTint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.92f),
                )

                androidx.compose.foundation.layout.Spacer(modifier = Modifier.size(18.dp))

                ControlIconButton(
                    icon = Icons.Filled.FastForward,
                    contentDescription = "Next channel",
                    buttonSize = 56.dp,
                    iconSize = 30.dp,
                    onClick = onNextChannel,
                    iconTint = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.88f),
                )
            }

            val desiredQuality = (pendingQuality ?: selectedQuality).trim().lowercase()
            val isHighQuality = desiredQuality == "high"

            ControlIconButton(
                modifier = Modifier.align(Alignment.CenterEnd),
                icon = Icons.Filled.HighQuality,
                contentDescription = if (isHighQuality) "Use medium quality" else "Use high quality",
                buttonSize = 48.dp,
                iconSize = 24.dp,
                onClick = {
                    onQualitySelected(if (isHighQuality) "medium" else "high")
                },
                iconTint = if (isHighQuality) {
                    Color.White
                } else {
                    MaterialTheme.colorScheme.onSurface.copy(alpha = 0.70f)
                },
            )
            }
        }
    }
}

@Composable
private fun ControlIconButton(
    modifier: Modifier = Modifier,
    icon: ImageVector,
    contentDescription: String,
    buttonSize: Dp,
    iconSize: Dp,
    onClick: () -> Unit,
    iconTint: Color,
) {
    IconButton(
        modifier = modifier.size(buttonSize),
        onClick = onClick,
    ) {
        Icon(
            modifier = Modifier.size(iconSize),
            imageVector = icon,
            contentDescription = contentDescription,
            tint = iconTint,
        )
    }
}

private fun normalizeChannelKey(value: String): String {
    return value.trim().lowercase()
}

private fun toChannelSubtitle(channel: String): String {
    val normalized = normalizeChannelKey(channel)
    val displayChannel = if (normalized.isBlank() || normalized == "all") {
        "All"
    } else {
        normalized.replaceFirstChar { first ->
            if (first.isLowerCase()) {
                first.titlecase(Locale.US)
            } else {
                first.toString()
            }
        }
    }

    return "Midori AI Radio: $displayChannel"
}

private suspend fun extractPaletteGradient(
    context: Context,
    artUrl: String,
    imageCacheKey: String,
    fallbackGradient: PaletteGradient,
): PaletteGradient? {
    val request = ImageRequest.Builder(context)
        .data(artUrl)
        .memoryCacheKey(imageCacheKey)
        .diskCacheKey(imageCacheKey)
        .allowHardware(false)
        .build()

    val drawable = when (val result = context.imageLoader.execute(request)) {
        is SuccessResult -> result.drawable
        else -> null
    } ?: return null

    val bitmap = drawable.toBitmap(
        width = 196,
        height = 196,
        config = Bitmap.Config.ARGB_8888,
    )

    return withContext(Dispatchers.Default) {
        val palette = Palette.from(bitmap)
            .maximumColorCount(16)
            .generate()

        val primary = palette.vibrantSwatch?.rgb
            ?: palette.lightVibrantSwatch?.rgb
            ?: palette.mutedSwatch?.rgb
            ?: palette.dominantSwatch?.rgb
            ?: return@withContext null
        val secondary = palette.lightMutedSwatch?.rgb
            ?: palette.mutedSwatch?.rgb
            ?: palette.lightVibrantSwatch?.rgb
            ?: palette.vibrantSwatch?.rgb
            ?: primary
        val tertiary = palette.darkVibrantSwatch?.rgb
            ?: palette.darkMutedSwatch?.rgb
            ?: palette.mutedSwatch?.rgb
            ?: secondary

        PaletteGradient(
            top = blendColor(
                base = fallbackGradient.top,
                overlay = Color(primary),
                ratio = 0.70f,
            ),
            middle = blendColor(
                base = fallbackGradient.middle,
                overlay = Color(secondary),
                ratio = 0.64f,
            ),
            bottom = blendColor(
                base = fallbackGradient.bottom,
                overlay = Color(tertiary),
                ratio = 0.68f,
            ),
        )
    }
}

private fun blendColor(
    base: Color,
    overlay: Color,
    ratio: Float,
): Color {
    val clamped = ratio.coerceIn(0f, 1f)
    return Color(
        red = (base.red * (1f - clamped)) + (overlay.red * clamped),
        green = (base.green * (1f - clamped)) + (overlay.green * clamped),
        blue = (base.blue * (1f - clamped)) + (overlay.blue * clamped),
        alpha = 1f,
    )
}

private fun currentHourSeedBucket(): String {
    val now = LocalDateTime.now()
    return String.format(
        Locale.US,
        "%04d-%02d-%02d-%02d",
        now.year,
        now.monthValue,
        now.dayOfMonth,
        now.hour,
    )
}

private fun millisUntilNextHour(): Long {
    val now = LocalDateTime.now()
    val nextHour = now.truncatedTo(ChronoUnit.HOURS).plusHours(1)
    val millis = Duration.between(now, nextHour).toMillis()
    return millis.coerceAtLeast(1_000L)
}

private fun buildBackgroundSeed(
    title: String,
    channel: String,
    hourBucket: String,
): String {
    val normalizedTitle = title.trim().lowercase()
    val normalizedChannel = normalizeChannelKey(channel)
    return "$normalizedTitle|$normalizedChannel|$hourBucket"
}

private fun buildDynamicBackgroundPattern(
    palette: PaletteGradient,
    seed: String,
): DynamicBackgroundPattern {
    val seeded = SeededGenerator(seed.hashCode())

    val baseColor = blendColor(
        base = blendColor(
            base = palette.top,
            overlay = palette.bottom,
            ratio = 0.50f,
        ),
        overlay = Color(0xFF141920),
        ratio = 0.52f,
    )
    val layerOne = blendColor(
        base = palette.top,
        overlay = palette.middle,
        ratio = seeded.nextFloat(0.32f, 0.62f),
    )
    val layerTwo = blendColor(
        base = palette.middle,
        overlay = palette.bottom,
        ratio = seeded.nextFloat(0.34f, 0.70f),
    )
    val layerThree = blendColor(
        base = palette.bottom,
        overlay = palette.top,
        ratio = seeded.nextFloat(0.28f, 0.56f),
    )

    return DynamicBackgroundPattern(
        base = baseColor,
        layerOne = blendColor(
            base = baseColor,
            overlay = layerOne,
            ratio = 0.74f,
        ),
        layerTwo = blendColor(
            base = baseColor,
            overlay = layerTwo,
            ratio = 0.78f,
        ),
        layerThree = blendColor(
            base = baseColor,
            overlay = layerThree,
            ratio = 0.76f,
        ),
        glowOne = blendColor(
            base = layerOne,
            overlay = Color.White,
            ratio = seeded.nextFloat(0.08f, 0.18f),
        ),
        glowTwo = blendColor(
            base = layerTwo,
            overlay = Color.White,
            ratio = seeded.nextFloat(0.06f, 0.16f),
        ),
        stopOne = seeded.nextFloat(0.22f, 0.42f),
        stopTwo = seeded.nextFloat(0.58f, 0.84f),
        angleDegrees = seeded.nextFloat(24f, 156f),
        glowOneX = seeded.nextFloat(0.16f, 0.84f),
        glowOneY = seeded.nextFloat(0.16f, 0.70f),
        glowTwoX = seeded.nextFloat(0.16f, 0.84f),
        glowTwoY = seeded.nextFloat(0.34f, 0.94f),
    )
}

private class SeededGenerator(seed: Int) {
    private var state = if (seed == 0) 0x9E3779B9.toInt() else seed

    fun nextFloat(min: Float, max: Float): Float {
        state = (state * 1664525) + 1013904223
        val normalized = ((state ushr 1).toFloat() / Int.MAX_VALUE.toFloat()).coerceIn(0f, 1f)
        return min + ((max - min) * normalized)
    }
}

private data class HeroTransitionState(
    val from: NowPlayingVisualState,
    val to: NowPlayingVisualState,
    val direction: Int,
)

private data class DynamicBackgroundPattern(
    val base: Color,
    val layerOne: Color,
    val layerTwo: Color,
    val layerThree: Color,
    val glowOne: Color,
    val glowTwo: Color,
    val stopOne: Float,
    val stopTwo: Float,
    val angleDegrees: Float,
    val glowOneX: Float,
    val glowOneY: Float,
    val glowTwoX: Float,
    val glowTwoY: Float,
)

private data class PaletteGradient(
    val top: Color,
    val middle: Color,
    val bottom: Color,
)

private data class NowPlayingVisualState(
    val channel: String,
    val channelSubtitle: String,
    val title: String,
    val artUrl: String?,
    val imageCacheKey: String,
)
