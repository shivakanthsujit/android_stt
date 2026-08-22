package dev.localflow.dictation.stt

import kotlin.math.log10
import kotlin.math.sqrt

/**
 * Produces a deliberately low-detail voice-activity envelope from live PCM.
 *
 * A first-order high-pass removes DC/rumble, a firm noise gate suppresses idle room sound, and a
 * slow attack/release envelope removes speech-detail from the UI. No PCM is retained outside the
 * current calculation.
 */
class AudioLevelMeter {
    private var previousInput = 0f
    private var previousHighPassed = 0f
    private var envelope = 0f

    fun process(samples: FloatArray): Float {
        if (samples.isEmpty()) return envelope

        var sumSquares = 0.0
        var peak = 0f
        samples.forEach { rawSample ->
            val sample = rawSample.coerceIn(-1f, 1f)
            val highPassed = HIGH_PASS_ALPHA *
                (previousHighPassed + sample - previousInput)
            previousInput = sample
            previousHighPassed = highPassed
            val magnitude = kotlin.math.abs(highPassed)
            sumSquares += magnitude * magnitude
            if (magnitude > peak) peak = magnitude
        }

        val rms = sqrt(sumSquares / samples.size).toFloat()
        val target = voiceActivity(rms, peak)
        val smoothing = if (target > envelope) ATTACK else RELEASE
        envelope += smoothing * (target - envelope)
        if (target == 0f && envelope < ENVELOPE_FLOOR) envelope = 0f
        return envelope.coerceIn(0f, 1f)
    }

    fun reset() {
        previousInput = 0f
        previousHighPassed = 0f
        envelope = 0f
    }

    private fun voiceActivity(rms: Float, peak: Float): Float {
        if (rms <= ABSOLUTE_FLOOR) return 0f
        val rmsDb = 20f * log10(rms.coerceAtLeast(ABSOLUTE_FLOOR))
        if (rmsDb <= NOISE_GATE_DB) return 0f

        val peakDb = 20f * log10(peak.coerceAtLeast(ABSOLUTE_FLOOR))
        val normalizedRms = normalizeDb(rmsDb)
        val normalizedPeak = normalizeDb(peakDb)
        val mixed = (normalizedRms * 0.9f + normalizedPeak * 0.1f).coerceIn(0f, 1f)
        return mixed * mixed * (3f - 2f * mixed)
    }

    private fun normalizeDb(db: Float): Float =
        ((db - NOISE_GATE_DB) / (VOICE_CEILING_DB - NOISE_GATE_DB)).coerceIn(0f, 1f)

    private companion object {
        // 80 Hz first-order high-pass at 16 kHz: removes rumble without affecting STT audio.
        const val HIGH_PASS_ALPHA = 0.9695f
        const val NOISE_GATE_DB = -32f
        const val VOICE_CEILING_DB = -8f
        const val ATTACK = 0.32f
        const val RELEASE = 0.14f
        const val ENVELOPE_FLOOR = 0.025f
        const val ABSOLUTE_FLOOR = 0.00001f
    }
}
