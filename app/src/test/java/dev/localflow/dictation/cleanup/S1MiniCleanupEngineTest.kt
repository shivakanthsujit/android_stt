package dev.localflow.dictation.cleanup

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class S1MiniCleanupEngineTest {
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
