package xyz.midoriai.radio

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import xyz.midoriai.radio.ui.MidoriAIRadioApp
import xyz.midoriai.radio.ui.theme.MidoriAIRadioTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MidoriAIRadioTheme {
                MidoriAIRadioApp()
            }
        }
    }
}
