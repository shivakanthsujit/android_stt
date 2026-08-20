package dev.localflow.dictation.cleanup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CleanupGuardrailsTest {
    @Test
    fun rejectsBlankOutput() {
        assertEquals(
            "Model returned empty text",
            CleanupGuardrails.fallbackReason(
                rawText = "Keep this transcript.",
                candidate = "   ",
                hitOutputTokenLimit = false,
            ),
        )
    }

    @Test
    fun rejectsOutputThatReachedTokenCap() {
        assertEquals(
            "Model reached the output token limit",
            CleanupGuardrails.fallbackReason(
                rawText = "Keep this transcript.",
                candidate = "Any non-empty partial output",
                hitOutputTokenLimit = true,
            ),
        )
    }

    @Test
    fun acceptsEveryOtherModelOutput() {
        val candidates = listOf(
            "Maria at 10am.",
            "Send it now.",
            "A much shorter summary.",
            "Entirely new lexical content is accepted.",
        )
        candidates.forEach { candidate ->
            assertNull(
                candidate,
                CleanupGuardrails.fallbackReason(
                    rawText = "Don't send the message to Maya at ten PM because I might revise it.",
                    candidate = candidate,
                    hitOutputTokenLimit = false,
                ),
            )
        }
    }

    @Test
    fun stripsKnownWrappers() {
        assertEquals(
            "Use the model output.",
            CleanupGuardrails.sanitize(
                "Cleaned transcript: \"Use the model output.\"<|im_end|>",
            ),
        )
    }
}
