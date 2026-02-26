package xyz.midoriai.radio.ui.screens.home

import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.tooling.preview.Preview
import xyz.midoriai.radio.ui.components.HorizontalAlbumRow
import xyz.midoriai.radio.ui.components.SectionHeader
import xyz.midoriai.radio.ui.components.TrackRowItem
import xyz.midoriai.radio.ui.mock.MockData
import xyz.midoriai.radio.ui.theme.MidoriAIRadioTheme

@Composable
fun HomeScreen(
    modifier: Modifier = Modifier,
) {
    LazyColumn(modifier = modifier) {
        item {
            Spacer(modifier = Modifier.height(12.dp))
            Text(
                text = "Midori AI Radio",
                style = MaterialTheme.typography.headlineLarge,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = "Your mixes and picks",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 16.dp),
            )
            Spacer(modifier = Modifier.height(18.dp))
        }

        item {
            SectionHeader(title = "Featured")
            Spacer(modifier = Modifier.height(10.dp))
            HorizontalAlbumRow(albums = MockData.featuredAlbums)
            Spacer(modifier = Modifier.height(22.dp))
        }

        item {
            SectionHeader(title = "Trending")
            Spacer(modifier = Modifier.height(6.dp))
        }

        items(MockData.trendingTracks) { track ->
            TrackRowItem(track = track)
        }

        item {
            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}

@Preview
@Composable
private fun HomeScreenPreview() {
    MidoriAIRadioTheme {
        HomeScreen()
    }
}
