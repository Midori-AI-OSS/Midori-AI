package xyz.midoriai.radio.ui

import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import xyz.midoriai.radio.ui.screens.nowplaying.NowPlayingScreen

@Composable
fun MidoriAIRadioApp() {
    Surface(color = MaterialTheme.colorScheme.background) {
        Scaffold { innerPadding ->
            NowPlayingScreen(
                modifier = Modifier.padding(innerPadding),
            )
        }
    }
}
