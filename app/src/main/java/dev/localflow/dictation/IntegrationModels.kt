package dev.localflow.dictation

import android.content.Context
import java.io.File
import java.security.MessageDigest

/** Immutable model identities used by the ordinary app and joined integration-test build. */
object IntegrationModels {
    const val PARAKEET_FILE_NAME = "realtime_eou_120m-v1-q4_k.gguf"
    const val PARAKEET_SHA256 =
        "ac9109d0e422bd8aafa899c0f58e1938f4a2846838797a29c04f6a8729033c3c"

    const val CLEANUP_FILE_NAME = "s1-mini-q4_k_m.gguf"
    const val CLEANUP_SHA256 =
        "3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634"

    // Retained only so the older direct-text benchmark profile remains reproducible.
    const val SOTTO_FILE_NAME = "sotto-b-epoch2-lfm25-350m-q4_k_m.gguf"
    const val SOTTO_SHA256 =
        "02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0"

    fun modelDirectory(context: Context): File = context.filesDir.resolve("models")

    fun parakeetFile(context: Context): File = modelDirectory(context).resolve(PARAKEET_FILE_NAME)

    fun cleanupFile(context: Context): File = modelDirectory(context).resolve(CLEANUP_FILE_NAME)

    fun sottoFile(context: Context): File = modelDirectory(context).resolve(SOTTO_FILE_NAME)

    fun requireVerified(file: File, expectedSha256: String, displayName: String) {
        require(file.isFile) {
            "$displayName is not staged at ${file.absolutePath}. Run the integration model " +
                "staging script first."
        }
        require(expectedSha256.length == 64) {
            "$displayName has no finalized deployment hash"
        }
        val actual = file.inputStream().buffered().use { input ->
            val digest = MessageDigest.getInstance("SHA-256")
            val buffer = ByteArray(HASH_BUFFER_BYTES)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
            digest.digest().joinToString("") { byte -> "%02x".format(byte) }
        }
        require(actual == expectedSha256) {
            "$displayName SHA-256 mismatch: expected $expectedSha256, found $actual"
        }
    }

    private const val HASH_BUFFER_BYTES = 1024 * 1024
}
