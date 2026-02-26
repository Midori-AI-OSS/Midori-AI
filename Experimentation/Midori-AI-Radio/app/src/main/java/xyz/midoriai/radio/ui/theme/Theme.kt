package xyz.midoriai.radio.ui.theme

import android.os.Build
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val LightColorScheme = lightColorScheme(
    primary = MidoriAIFrostWhite,
    secondary = MidoriAISoftSilver,
    tertiary = MidoriAIIceBlue,
    background = Color(0xFFF3F1ED),
    onBackground = Color(0xFF1A1D21),
    surface = Color(0xFFE7E4DE),
    onSurface = Color(0xFF1F2328),
    surfaceVariant = Color(0xFFD7D2CB),
    onSurfaceVariant = Color(0xFF4D5660),
    outline = Color(0xFF7B828D),
    error = MidoriAIErrorTint,
    onError = Color(0xFF1A1D21),
)

private val DarkColorScheme = darkColorScheme(
    primary = MidoriAIFrostWhite,
    secondary = MidoriAISoftSilver,
    tertiary = MidoriAIIceBlue,
    onPrimary = MidoriAIBackground,
    onSecondary = MidoriAIOnBackground,
    onTertiary = MidoriAIBackground,
    background = MidoriAIBackground,
    onBackground = MidoriAIOnBackground,
    surface = MidoriAISurface,
    surfaceVariant = MidoriAISurfaceVariant,
    onSurface = MidoriAIOnSurface,
    onSurfaceVariant = MidoriAIOnSurfaceVariant,
    error = MidoriAIErrorTint,
    onError = MidoriAIBackground,
    outline = MidoriAIOutline,
)

@Composable
fun MidoriAIRadioTheme(
    useDarkTheme: Boolean = true,
    useDynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        useDynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (useDarkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }

        useDarkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = MidoriAITypography,
        shapes = MidoriAIShapes,
        content = content,
    )
}
