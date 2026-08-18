package dev.localflow.dictation

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class IntegrationModelsTest {
    @Test
    fun integrationCleanupIdentityIsPinnedToSottoBEpoch2() {
        assertEquals(
            "sotto-b-epoch2-lfm25-350m-q4_k_m.gguf",
            IntegrationModels.SOTTO_FILE_NAME,
        )
        assertEquals(
            "02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0",
            IntegrationModels.SOTTO_SHA256,
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
            assertTrue(failure is IllegalArgumentException)
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
        assertTrue(failure is IllegalArgumentException)
        assertTrue(!file.exists())
    }
}
