package dev.localflow.dictation

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class IntegrationModelsTest {
    @Test
    fun liveSpeechIdentityIsPinnedToParakeetRealtimeEouQ4() {
        assertEquals(
            "realtime_eou_120m-v1-q4_k.gguf",
            IntegrationModels.PARAKEET_FILE_NAME,
        )
        assertEquals(
            "ac9109d0e422bd8aafa899c0f58e1938f4a2846838797a29c04f6a8729033c3c",
            IntegrationModels.PARAKEET_SHA256,
        )
    }

    @Test
    fun preferredCleanupIdentityIsPinnedToS1MiniQ4() {
        assertEquals(
            "s1-mini-q4_k_m.gguf",
            IntegrationModels.CLEANUP_FILE_NAME,
        )
        assertEquals(
            "3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634",
            IntegrationModels.CLEANUP_SHA256,
        )
    }

    @Test
    fun verifiedArtifactAcceptsExactHash() {
        val file = Files.createTempFile("local-flow-model", ".gguf").toFile()
        file.writeText("local-flow")
        try {
            IntegrationModels.requireVerified(
                file = file,
                expectedSha256 =
                    "c4384b7d0ad39bfb4e950914118e5157936fa9c64429cfbe74640e500c101d46",
                displayName = "fixture",
            )
        } finally {
            file.delete()
        }
    }

    @Test
    fun verifiedArtifactRejectsWrongHash() {
        val file = Files.createTempFile("local-flow-model", ".gguf").toFile()
        file.writeText("local-flow")
        try {
            val failure = runCatching {
                IntegrationModels.requireVerified(
                    file = file,
                    expectedSha256 = "0".repeat(64),
                    displayName = "fixture",
                )
            }.exceptionOrNull()
            assertTrue(failure is InvalidModelArtifactException)
            assertTrue(failure?.message.orEmpty().contains("SHA-256 mismatch"))
        } finally {
            file.delete()
        }
    }

    @Test
    fun verifiedArtifactRejectsMissingFileWithoutCreatingIt() {
        val file = File("build/test-models/missing.gguf")
        val failure = runCatching {
            IntegrationModels.requireVerified(
                file = file,
                expectedSha256 = "0".repeat(64),
                displayName = "fixture",
            )
        }.exceptionOrNull()
        assertTrue(failure is MissingModelArtifactException)
        assertTrue(!file.exists())
    }
}
