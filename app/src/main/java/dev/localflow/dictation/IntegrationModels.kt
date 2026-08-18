package dev.localflow.dictation

import android.content.Context
import java.io.File
import java.security.MessageDigest

/** Immutable model identities used by the joined integration-test build. */
object IntegrationModels {
    const val PARAKEET_FILE_NAME = "tdt_ctc-110m-q4_k.gguf"
    const val PARAKEET_SHA256 =
        "2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf"

    const val SOTTO_FILE_NAME = "sotto-cleanup-lfm25-350m-q4_k_m.gguf"

    const val SOTTO_SHA256 =
        "05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570"

    fun modelDirectory(context: Context): File {
        val appStorage = context.getExternalFilesDir(null) ?: context.filesDir
        return appStorage.resolve("models")
    }

    fun parakeetFile(context: Context): File = modelDirectory(context).resolve(PARAKEET_FILE_NAME)

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
