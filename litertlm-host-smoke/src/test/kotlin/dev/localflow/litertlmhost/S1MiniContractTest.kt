package dev.localflow.litertlmhost

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class S1MiniContractTest {
    @Test
    fun `prompt is byte exact for frozen authored smoke`() {
        val raw = "um hello there"
        val expected =
            "<|im_start|>system\nYou are a text normalizer for speech-to-text transcripts. " +
                "The input begins with a control line specifying the styling, structure, and context " +
                "settings; clean the transcript to match those settings and output only the cleaned " +
                "text.<|im_end|>\n<|im_start|>user\n[Styling: semi-formal] [Structure: prose] " +
                "[Context: general]\num hello there<|im_end|>\n<|im_start|>assistant\n" +
                "<think>\n\n</think>\n\n"
        assertEquals(expected, S1MiniContract.expectedRenderedPrompt(raw))
    }

    @Test
    fun `output cap matches ceil one point three raw tokens plus thirty two`() {
        assertEquals(36, S1MiniContract.maxOutputTokens(3))
        assertEquals(45, S1MiniContract.maxOutputTokens(10))
        assertEquals(1_332, S1MiniContract.maxOutputTokens(1_000))
    }

    @Test
    fun `renderer accepts exact full or split prompt only`() {
        val expected = "preface-message"
        assertEquals(expected, S1MiniContract.selectExactRenderedPrompt(expected, "", expected))
        assertEquals(expected, S1MiniContract.selectExactRenderedPrompt(expected, "preface-", "message"))
        assertFailsWith<IllegalStateException> {
            S1MiniContract.selectExactRenderedPrompt(expected, "preface", "different")
        }
    }
}
