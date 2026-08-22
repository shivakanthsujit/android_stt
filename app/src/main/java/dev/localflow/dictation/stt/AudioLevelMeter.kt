package dev.localflow.dictation.stt

import kotlin.math.log10
import kotlin.math.sqrt

/** Converts a live PCM chunk to a bounded display level without retaining the audio. */
object AudioLevelMeter {
    fun displayLevel(samples: FloatArray): Float {
        if (samples.isEmpty()) return 0f

        var sumSquares = 0.0
        var peak = 0f
        samples.forEach { sample ->
            val magnitude = kotlin.math.abs(sample.coerceIn(-1f, 1f))
            sumSquares += magnitude * magnitude
            if (magnitude > peak) peak = magnitude
        }
        val rms = sqrt(sumSquares / samples.size).toFloat()
        if (rms <= SILENCE_FLOOR) return 0f

        // Map roughly -54 dBFS..0 dBFS to 0..1 and retain peaks for responsive quiet speech.
        val rmsDb = 20f * log10(rms.coerceAtLeast(SILENCE_FLOOR))
        val normalizedRms = ((rmsDb - MIN_DB) / -MIN_DB).coerceIn(0f, 1f)
        val normalizedPeak = sqrt(peak).coerceIn(0f, 1f)
        return (normalizedRms * 0.72f + normalizedPeak * 0.28f).coerceIn(0f, 1f)
    }

    private const val MIN_DB = -54f
    private const val SILENCE_FLOOR = 0.00001f
}
