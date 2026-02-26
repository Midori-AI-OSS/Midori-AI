package xyz.midoriai.radio.ui.components

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import xyz.midoriai.radio.ui.model.AlbumSummary

@Composable
fun HorizontalAlbumRow(
    albums: List<AlbumSummary>,
    modifier: Modifier = Modifier,
) {
    LazyRow(
        modifier = modifier,
        contentPadding = PaddingValues(horizontal = 16.dp),
    ) {
        items(albums) { album ->
            AlbumArtCard(
                album = album,
                modifier = Modifier.width(160.dp),
            )
            Spacer(modifier = Modifier.width(12.dp))
        }
    }
}
