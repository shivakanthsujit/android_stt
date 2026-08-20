package dev.localflow.dictation.stt.benchmark

import java.security.MessageDigest
import org.junit.Assert.assertEquals
import org.junit.Test

class S1MiniPixelBenchmarkEngineTest {
    @Test
    fun publisherPromptAndControlLineArePinned() {
        assertEquals(
            "6ecb6800f96b00cf612631552eff606a829feb2be8449fa95f9f150713b89327",
            sha256(S1MiniPixelBenchmarkEngine.SYSTEM_PROMPT),
        )
        assertEquals(
            "[Styling: semi-formal] [Structure: prose] [Context: general]",
            S1MiniPixelBenchmarkEngine.CONTROL_LINE,
        )
        assertEquals(
            "s1-mini-v1-publisher",
            S1MiniPixelBenchmarkEngine.PROMPT_PROFILE,
        )
    }

    private fun sha256(value: String): String =
        MessageDigest.getInstance("SHA-256")
            .digest(value.toByteArray(Charsets.UTF_8))
            .joinToString("") { byte -> "%02x".format(byte) }
}
