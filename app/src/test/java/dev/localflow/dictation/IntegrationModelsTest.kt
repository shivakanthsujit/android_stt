package dev.localflow.dictation

import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertTrue
import org.junit.Test

class IntegrationModelsTest {
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
