package xyz.midoriai.radio.settings

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import xyz.midoriai.radio.radioapi.normalizeQuality

private val Context.radioSettingsDataStore: DataStore<Preferences> by preferencesDataStore(
    name = "midoriai_radio_settings",
)

class RadioSettingsRepository(
    private val context: Context,
) {
    private object Keys {
        val channel = stringPreferencesKey("channel")
        val quality = stringPreferencesKey("quality")
    }

    val channel: Flow<String> = context.radioSettingsDataStore.data
        .map { prefs ->
            prefs[Keys.channel]
                ?.trim()
                ?.lowercase()
                ?.ifBlank { "all" }
                ?: "all"
        }

    val quality: Flow<String> = context.radioSettingsDataStore.data
        .map { prefs ->
            normalizeQuality(prefs[Keys.quality])
        }

    suspend fun setChannel(value: String) {
        val normalized = value.trim().lowercase().ifBlank { "all" }
        context.radioSettingsDataStore.edit { prefs ->
            prefs[Keys.channel] = normalized
        }
    }

    suspend fun setQuality(value: String) {
        val normalized = normalizeQuality(value)
        context.radioSettingsDataStore.edit { prefs ->
            prefs[Keys.quality] = normalized
        }
    }
}
