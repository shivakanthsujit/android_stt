package dev.localflow.dictation.stt

/**
 * Optional file-fed inference surface used by the debug-only STT benchmark harness.
 *
 * Implementations must keep the model loaded across calls. Timing covers model inference only;
 * WAV decoding and host/device transfer are deliberately outside the measurement.
 */
interface FileSttBenchmarkEngine {
    val benchmarkEngineId: String

    fun transcribePcm(
        samples: FloatArray,
        sampleRate: Int,
        callback: (Result<FileSttBenchmarkResult>) -> Unit,
    )
}

data class FileSttBenchmarkResult(
    val text: String,
    val inferenceDurationNs: Long,
    val processCpuDurationMs: Long,
) {
    val inferenceDurationMs: Double
        get() = inferenceDurationNs.coerceAtLeast(0L) / 1_000_000.0
}
