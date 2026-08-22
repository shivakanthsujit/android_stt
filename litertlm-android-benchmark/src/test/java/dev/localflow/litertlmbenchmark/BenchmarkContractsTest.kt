package dev.localflow.litertlmbenchmark

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class BenchmarkContractsTest {
    @Test
    fun exactPromptAndCap() {
        val prompt = S1LiteRtContract.renderPrompt("um hello there")
        assertEquals(36, S1LiteRtContract.outputCap(3))
        assertTrue(
            prompt.endsWith("<|im_start|>assistant\n<think>\n\n</think>\n\n"),
        )
    }

    @Test
    fun parserAcceptsTranscriptAndTokenCountOnly() {
        val parsed = TranscriptCaseParser.parseLine(
            """{"id":"short-filler","raw":"um hello there","categories":["smoke"],"raw_tokens":3}""",
            1,
        )
        assertEquals(3, parsed.rawTokenCount)
        assertThrows(IllegalArgumentException::class.java) {
            TranscriptCaseParser.parseLine(
                """{"id":"bad","raw":"text","categories":[],"raw_tokens":1,"expected":"x"}""",
                1,
            )
        }
    }

    @Test
    fun jobsRemainSequentialAndRepeatMajor() {
        assertEquals(
            listOf(
                BenchmarkJob(0, PHASE_WARMUP, 0),
                BenchmarkJob(1, PHASE_MEASURED, 0),
                BenchmarkJob(2, PHASE_MEASURED, 0),
                BenchmarkJob(0, PHASE_MEASURED, 0),
            ),
            buildJobOrder(3, 1, 1),
        )
    }
}
