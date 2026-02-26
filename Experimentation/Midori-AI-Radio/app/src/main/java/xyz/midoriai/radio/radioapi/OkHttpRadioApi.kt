package xyz.midoriai.radio.radioapi

import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

class OkHttpRadioApi(
    baseUrl: String = RadioApiDefaults.DEFAULT_BASE_URL,
    private val client: OkHttpClient = OkHttpClient(),
    private val json: Json = Json { ignoreUnknownKeys = true },
) : RadioApi {
    private val baseHttpUrl: HttpUrl = baseUrl.trim().trimEnd('/').toHttpUrl()

    override suspend fun fetchHealth(): RadioApiResult<HealthPayload> {
        val url = baseHttpUrl.newBuilder()
            .addPathSegments("health")
            .build()

        return requestData(url, HealthPayload.serializer())
    }

    override suspend fun fetchChannels(): RadioApiResult<ChannelsPayload> {
        val url = baseHttpUrl.newBuilder()
            .addPathSegments("radio/v1/channels")
            .build()

        return requestData(url, ChannelsPayload.serializer())
    }

    override suspend fun fetchCurrent(channel: String?): RadioApiResult<CurrentPayload> {
        val url = buildChannelQueryUrl(baseHttpUrl, "/radio/v1/current", channel)
        return requestData(url, CurrentPayload.serializer())
    }

    override suspend fun fetchArt(channel: String?): RadioApiResult<ArtPayload> {
        val url = buildChannelQueryUrl(baseHttpUrl, "/radio/v1/art", channel)

        return when (val result = requestData(url, ArtPayload.serializer())) {
            is RadioApiResult.Success -> {
                val resolved = result.data.copy(
                    artUrl = toAbsoluteRadioUrl(result.data.artUrl, baseHttpUrl.toString()),
                )
                RadioApiResult.Success(resolved, result.now)
            }

            is RadioApiResult.Failure -> result
        }
    }

    private suspend fun <T> requestData(
        url: HttpUrl,
        serializer: KSerializer<T>,
    ): RadioApiResult<T> {
        val request = Request.Builder()
            .url(url)
            .get()
            .header("Accept", "application/json")
            .build()

        return when (val httpResult = executeCall(request)) {
            is HttpResult.Err -> RadioApiResult.Failure(httpResult.failure)
            is HttpResult.Ok -> parseEnvelopeResponse(httpResult.response, serializer)
        }
    }

    private fun <T> parseEnvelopeResponse(
        response: Response,
        serializer: KSerializer<T>,
    ): RadioApiResult<T> {
        response.use { resp ->
            val status = resp.code
            val bodyString = try {
                resp.body?.string()
            } catch (exc: Exception) {
                null
            }

            if (bodyString.isNullOrBlank()) {
                return RadioApiResult.Failure(RadioApiFailure.Http(status, "Empty response body"))
            }

            val envelope = try {
                json.decodeFromString(RadioEnvelope.serializer(serializer), bodyString)
            } catch (exc: Exception) {
                return RadioApiResult.Failure(
                    RadioApiFailure.InvalidEnvelope(exc.message ?: "Invalid JSON envelope"),
                )
            }

            if (envelope.version != RadioApiDefaults.API_VERSION) {
                return RadioApiResult.Failure(RadioApiFailure.UnsupportedVersion(envelope.version))
            }

            if (!resp.isSuccessful || !envelope.ok) {
                val upstreamError = envelope.error

                return RadioApiResult.Failure(
                    RadioApiFailure.Upstream(
                        status = status,
                        code = upstreamError?.code ?: "RADIO_ERROR",
                        message = upstreamError?.message ?: "Radio request failed",
                        now = envelope.now,
                    ),
                )
            }

            val data = envelope.data
                ?: return RadioApiResult.Failure(RadioApiFailure.NullData("Radio response data was null"))

            return RadioApiResult.Success(data, envelope.now)
        }
    }

    private sealed interface HttpResult {
        data class Ok(
            val response: Response,
        ) : HttpResult

        data class Err(
            val failure: RadioApiFailure,
        ) : HttpResult
    }

    private suspend fun executeCall(request: Request): HttpResult {
        return suspendCoroutine { continuation ->
            val call = client.newCall(request)
            call.enqueue(
                object : Callback {
                    override fun onFailure(call: Call, e: IOException) {
                        continuation.resume(
                            HttpResult.Err(RadioApiFailure.Network(e.message ?: "Network error")),
                        )
                    }

                    override fun onResponse(call: Call, response: Response) {
                        continuation.resume(HttpResult.Ok(response))
                    }
                },
            )
        }
    }
}
