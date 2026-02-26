package xyz.midoriai.radio.radioapi

sealed interface RadioApiResult<out T> {
    data class Success<T>(
        val data: T,
        val now: String,
    ) : RadioApiResult<T>

    data class Failure(
        val failure: RadioApiFailure,
    ) : RadioApiResult<Nothing>
}

sealed interface RadioApiFailure {
    data class Network(
        val message: String,
    ) : RadioApiFailure

    data class Http(
        val status: Int,
        val message: String,
    ) : RadioApiFailure

    data class InvalidEnvelope(
        val message: String,
    ) : RadioApiFailure

    data class UnsupportedVersion(
        val version: String,
    ) : RadioApiFailure

    data class Upstream(
        val status: Int,
        val code: String,
        val message: String,
        val now: String? = null,
    ) : RadioApiFailure

    data class NullData(
        val message: String,
    ) : RadioApiFailure
}
