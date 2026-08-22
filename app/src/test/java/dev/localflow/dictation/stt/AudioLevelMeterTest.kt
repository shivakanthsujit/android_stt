package dev.localflow.dictation.stt

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AudioLevelMeterTest {
    @Test
    fun emptyAndSilentChunksReturnZero() {
        assertEquals(0f, AudioLevelMeter.displayLevel(floatArrayOf()), 0f)
        assertEquals(0f, AudioLevelMeter.displayLevel(FloatArray(64)), 0f)
    }

    @Test
    fun louderChunksProduceLargerBoundedLevels() {
        val quiet = AudioLevelMeter.displayLevel(FloatArray(64) { 0.01f })
        val loud = AudioLevelMeter.displayLevel(FloatArray(64) { 0.7f })

        assertTrue(quiet in 0f..1f)
        assertTrue(loud in 0f..1f)
        assertTrue(loud > quiet)
    }

    @Test
    fun outOfRangeSamplesRemainBounded() {
        assertEquals(1f, AudioLevelMeter.displayLevel(floatArrayOf(-4f, 4f)), 0.0001f)
    }
}
