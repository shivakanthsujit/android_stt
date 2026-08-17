package dev.localflow.dictation.stt

data class SttResult(
    val text: String,
    val micStartedAtNs: Long,
    val stopPressedAtNs: Long,
    val finalTextAtNs: Long,
) {
    val recordingDurationMs: Long
        get() = nanosToMillis(stopPressedAtNs - micStartedAtNs)

    val finalizationLatencyMs: Long
        get() = nanosToMillis(finalTextAtNs - stopPressedAtNs)

    private fun nanosToMillis(nanos: Long): Long = nanos.coerceAtLeast(0L) / 1_000_000L
}

