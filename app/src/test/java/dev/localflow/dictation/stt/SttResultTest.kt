package dev.localflow.dictation.stt

import org.junit.Assert.assertEquals
import org.junit.Test

class SttResultTest {
    @Test
    fun reportsRecordingAndTailLatencyInMilliseconds() {
        val result = SttResult(
            text = "Hello.",
            micStartedAtNs = 1_000_000_000L,
            stopPressedAtNs = 3_345_900_000L,
            finalTextAtNs = 3_582_100_000L,
        )

        assertEquals(2_345L, result.recordingDurationMs)
        assertEquals(236L, result.finalizationLatencyMs)
    }

    @Test
    fun protectsMetricsFromReversedTimestamps() {
        val result = SttResult(
            text = "",
            micStartedAtNs = 2L,
            stopPressedAtNs = 1L,
            finalTextAtNs = 0L,
        )

        assertEquals(0L, result.recordingDurationMs)
        assertEquals(0L, result.finalizationLatencyMs)
    }
}

