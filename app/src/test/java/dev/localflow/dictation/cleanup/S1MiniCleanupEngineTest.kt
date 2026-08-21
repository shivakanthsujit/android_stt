package dev.localflow.dictation.cleanup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class S1MiniCleanupEngineTest {
    @Test
    fun productionLoadingOptionsUseTheSelectedLeapConfiguration() {
        val options = S1MiniCleanupEngine.productionModelLoadingOptions()

        assertEquals(2, S1MiniCleanupEngine.MODEL_CPU_THREADS)
        assertEquals(2_560, S1MiniCleanupEngine.MODEL_CONTEXT_TOKENS)
        assertEquals(S1MiniCleanupEngine.MODEL_CPU_THREADS, options.cpuThreads)
        assertEquals(S1MiniCleanupEngine.MODEL_CONTEXT_TOKENS, options.contextSize)
        assertEquals(true, options.useMmap)
        assertNull(options.cacheOptions)
        assertNull(options.chatTemplate)
    }

    @Test
    fun selectedContextFitsTheLargestSupportedCleanupPass() {
        val maxOutputTokens = S1MiniCleanupEngine.outputCapForRawTokenCount(
            S1MiniCleanupEngine.RECOMMENDED_MAX_RAW_TOKENS,
        )

        assertEquals(1_332, maxOutputTokens)
        assertEquals(78, S1MiniCleanupEngine.EXPECTED_FIXED_PROMPT_TOKENS)
        assertEquals(
            2_410,
            S1MiniCleanupEngine.EXPECTED_FIXED_PROMPT_TOKENS +
                S1MiniCleanupEngine.RECOMMENDED_MAX_RAW_TOKENS +
                maxOutputTokens,
        )
        assertTrue(2_410 <= S1MiniCleanupEngine.MODEL_CONTEXT_TOKENS)
    }

    @Test
    fun publisherOutputCapRoundsUpAfterScalingRawTokens() {
        assertEquals(34, S1MiniCleanupEngine.outputCapForRawTokenCount(1))
        assertEquals(52, S1MiniCleanupEngine.outputCapForRawTokenCount(15))
        assertEquals(57, S1MiniCleanupEngine.outputCapForRawTokenCount(19))
    }

    @Test
    fun publisherOutputCapRejectsEmptyInput() {
        assertThrows(IllegalArgumentException::class.java) {
            S1MiniCleanupEngine.outputCapForRawTokenCount(0)
        }
    }
}
