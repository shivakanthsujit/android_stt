package dev.localflow.litertlmhost

import java.security.MessageDigest
import java.nio.file.Files
import java.nio.file.Path

internal object S1MiniContract {
    const val MODEL_BYTES = 436_596_864L
    const val MODEL_SHA256 = "8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403"
    const val CONTEXT_TOKENS = 4_096
    const val FIXED_PROMPT_TOKENS = 78

    const val SYSTEM_PROMPT =
        "You are a text normalizer for speech-to-text transcripts. The input begins with a " +
            "control line specifying the styling, structure, and context settings; clean the " +
            "transcript to match those settings and output only the cleaned text."

    const val CONTROL_LINE =
        "[Styling: semi-formal] [Structure: prose] [Context: general]"

    fun userText(raw: String): String = "$CONTROL_LINE\n$raw"

    fun expectedRenderedPrompt(raw: String): String =
        "<|im_start|>system\n$SYSTEM_PROMPT<|im_end|>\n" +
            "<|im_start|>user\n${userText(raw)}<|im_end|>\n" +
            "<|im_start|>assistant\n<think>\n\n</think>\n\n"

    fun maxOutputTokens(rawTokens: Int): Int {
        require(rawTokens > 0) { "rawTokens must be positive" }
        return (13 * rawTokens + 9) / 10 + 32
    }

    fun selectExactRenderedPrompt(
        expected: String,
        preface: String,
        renderedMessage: String,
    ): String = when {
        renderedMessage == expected -> renderedMessage
        preface + renderedMessage == expected -> preface + renderedMessage
        else -> error(
            "LiteRT-LM rendered prompt differs from the frozen S1 contract: " +
                "expectedBytes=${expected.toByteArray().size}, " +
                "expectedSha256=${sha256(expected.toByteArray())}, " +
                "prefaceBytes=${preface.toByteArray().size}, " +
                "renderedMessageBytes=${renderedMessage.toByteArray().size}, " +
                "combinedSha256=${sha256((preface + renderedMessage).toByteArray())}",
        )
    }

    fun sha256(bytes: ByteArray): String =
        MessageDigest.getInstance("SHA-256")
            .digest(bytes)
            .joinToString("") { "%02x".format(it) }

    fun sha256(path: Path): String {
        val digest = MessageDigest.getInstance("SHA-256")
        Files.newInputStream(path).buffered().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
