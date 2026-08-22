package dev.localflow.dictation.stt

import kotlin.math.PI
import kotlin.math.sin
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioLevelMeterTest {
    @Test
    fun emptyAndSilentChunksReturnZero() {
        val meter = AudioLevelMeter()

        assertEquals(0f, meter.process(floatArrayOf()), 0f)
        assertEquals(0f, meter.process(FloatArray(1_024)), 0f)
    }

    @Test
    fun quietRoomLevelIsSuppressedByNoiseGate() {
        val meter = AudioLevelMeter()

        repeat(5) {
            assertEquals(0f, meter.process(sineWave(amplitude = 0.01f)), 0f)
        }
    }

    @Test
    fun voiceLevelProducesSmoothedBoundedActivity() {
        val meter = AudioLevelMeter()
        val first = meter.process(sineWave(amplitude = 0.25f))
        val second = meter.process(sineWave(amplitude = 0.25f))

        assertTrue(first in 0f..1f)
        assertTrue(second in 0f..1f)
        assertTrue(first > 0f)
        assertTrue(second > first)
    }

    @Test
    fun highPassRejectsSteadyDcInput() {
        val meter = AudioLevelMeter()
        var level = 1f

        repeat(8) { level = meter.process(FloatArray(1_024) { 0.2f }) }

        assertEquals(0f, level, 0f)
    }

    @Test
    fun resetClearsFilterAndEnvelopeState() {
        val meter = AudioLevelMeter()
        meter.process(sineWave(amplitude = 0.8f))

        meter.reset()

        assertEquals(0f, meter.process(FloatArray(1_024)), 0f)
    }

    private fun sineWave(
        amplitude: Float,
        frequencyHz: Float = 440f,
        size: Int = 1_024,
    ): FloatArray = FloatArray(size) { index ->
        (amplitude * sin(2.0 * PI * frequencyHz * index / 16_000.0)).toFloat()
    }
}
