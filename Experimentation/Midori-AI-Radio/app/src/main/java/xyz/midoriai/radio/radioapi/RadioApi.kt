package xyz.midoriai.radio.radioapi

interface RadioApi {
    suspend fun fetchHealth(): RadioApiResult<HealthPayload>

    suspend fun fetchChannels(): RadioApiResult<ChannelsPayload>

    suspend fun fetchCurrent(channel: String?): RadioApiResult<CurrentPayload>

    suspend fun fetchArt(channel: String?): RadioApiResult<ArtPayload>
}
