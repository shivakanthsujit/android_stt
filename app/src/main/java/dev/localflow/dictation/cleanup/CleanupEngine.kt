package dev.localflow.dictation.cleanup

interface CleanupEngine {
    val state: CleanupState

    /**
     * Loads the cleanup model. Calling this while the same engine is already ready is a no-op.
     *
     * The progress callback can be invoked from a background thread.
     */
    suspend fun load(
        onProgress: (CleanupLoadProgress) -> Unit = {},
    ): CleanupLoadResult

    /** Runs one independent cleanup generation with no history from earlier calls. */
    suspend fun clean(
        text: String,
        promptVariant: CleanupPromptVariant = CleanupPromptVariant.COMMAND_ENVELOPE,
    ): CleanupResult

    /** Stops using the engine and releases the model's native memory. */
    suspend fun unload()
}

enum class CleanupState {
    UNLOADED,
    LOADING,
    READY,
    GENERATING,
    UNLOADING,
    FAILED,
}

enum class CleanupPromptVariant(val id: String) {
    BASELINE_RULES("baseline_rules"),
    ISOLATED_RULES("isolated_rules"),
    COMMAND_ENVELOPE("command_envelope"),
    STRICT_MINIMAL_EDIT("strict_minimal_edit"),
    FEW_SHOT_CORRECTIONS("few_shot_corrections"),
    SOTTO_NATIVE("sotto_native"),
}

enum class CleanupModel(
    val modelName: String,
    val quantization: String,
) {
    LFM_230M("LFM2.5-230M", "Q4_K_M"),
    LFM_350M("LFM2.5-350M", "Q4_K_M"),
    LFM_1_2B_INSTRUCT("LFM2.5-1.2B-Instruct", "Q4_K_M"),
    SOTTO_LFM_350M("Sotto LFM2.5-350M", "Q4_K_M"),
}

data class CleanupLoadProgress(
    val downloadedBytes: Long,
    val totalBytes: Long,
) {
    val fraction: Float
        get() =
            if (totalBytes > 0L) {
                (downloadedBytes.toFloat() / totalBytes).coerceIn(0f, 1f)
            } else {
                0f
            }
}

data class CleanupLoadResult(
    val startedAtNs: Long,
    val completedAtNs: Long,
    val reusedLoadedRunner: Boolean,
) {
    val durationMs: Long
        get() = nanosToMillis(completedAtNs - startedAtNs)
}

data class CleanupResult(
    val modelName: String,
    val quantization: String,
    val rawText: String,
    val promptVariantId: String,
    val modelText: String,
    val cleanedText: String,
    val startedAtNs: Long,
    val firstTokenAtNs: Long?,
    val completedAtNs: Long,
    val usedFallback: Boolean,
    val fallbackReason: String?,
    val promptTokens: Long?,
    val completionTokens: Long?,
    val tokensPerSecond: Float?,
    val finishReason: String?,
    val maxOutputTokens: Int,
) {
    val timeToFirstTokenMs: Long?
        get() = firstTokenAtNs?.let { nanosToMillis(it - startedAtNs) }

    val totalLatencyMs: Long
        get() = nanosToMillis(completedAtNs - startedAtNs)

    val hitOutputTokenLimit: Boolean
        get() = completionTokens != null && completionTokens >= maxOutputTokens
}

private fun nanosToMillis(nanos: Long): Long = nanos.coerceAtLeast(0L) / 1_000_000L
