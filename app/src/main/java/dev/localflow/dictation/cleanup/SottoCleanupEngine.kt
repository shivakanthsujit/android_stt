package dev.localflow.dictation.cleanup

import ai.liquid.leap.GenerationOptions
import ai.liquid.leap.ModelLoadingOptions
import ai.liquid.leap.ModelRunner
import ai.liquid.leap.downloader.LeapModelDownloader
import ai.liquid.leap.manifest.ModelSource
import ai.liquid.leap.message.GenerationFinishReason
import ai.liquid.leap.message.GenerationStats
import ai.liquid.leap.message.MessageResponse
import android.content.Context
import android.os.SystemClock
import dev.localflow.dictation.IntegrationModels
import dev.localflow.dictation.LocalFlowLog
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** LEAP-backed sideloaded runtime for the pinned public Sotto LFM2.5-350M fine-tune. */
class SottoCleanupEngine(
    context: Context,
    private val modelFile: File,
    private val expectedModelSha256: String,
) : CleanupEngine {
    private val downloader = LeapModelDownloader(context.applicationContext)
    private val lifecycleMutex = Mutex()
    private val generationMutex = Mutex()

    @Volatile
    override var state: CleanupState = CleanupState.UNLOADED
        private set

    private var modelRunner: ModelRunner? = null

    override suspend fun load(
        onProgress: (CleanupLoadProgress) -> Unit,
    ): CleanupLoadResult = lifecycleMutex.withLock {
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        if (modelRunner != null) {
            return@withLock CleanupLoadResult(
                startedAtNs = startedAtNs,
                completedAtNs = SystemClock.elapsedRealtimeNanos(),
                reusedLoadedRunner = true,
            )
        }

        state = CleanupState.LOADING
        try {
            withContext(Dispatchers.IO) {
                IntegrationModels.requireVerified(
                    file = modelFile,
                    expectedSha256 = expectedModelSha256,
                    displayName = MODEL_NAME,
                )
            }
            onProgress(CleanupLoadProgress(modelFile.length(), modelFile.length()))
            modelRunner = downloader.loadSimpleModel(
                model = ModelSource(
                    modelPath = modelFile.absolutePath,
                    modelName = MODEL_NAME,
                    quantizationId = QUANTIZATION,
                ),
                options = ModelLoadingOptions(
                    randomSeed = DETERMINISTIC_SEED,
                    chatTemplate = RAW_COMPLETION_CHAT_TEMPLATE,
                    contextSize = MODEL_CONTEXT_TOKENS,
                    useMmap = true,
                    cacheOptions = null,
                ),
            )
            state = CleanupState.READY
            val completedAtNs = SystemClock.elapsedRealtimeNanos()
            LocalFlowLog.info(
                "Loaded $MODEL_NAME $QUANTIZATION in " +
                    "${(completedAtNs - startedAtNs).coerceAtLeast(0L) / 1_000_000L} ms",
            )
            CleanupLoadResult(startedAtNs, completedAtNs, reusedLoadedRunner = false)
        } catch (error: Throwable) {
            state = CleanupState.FAILED
            LocalFlowLog.error("Failed to load $MODEL_NAME $QUANTIZATION", error)
            throw error
        }
    }

    override suspend fun clean(
        text: String,
        promptVariant: CleanupPromptVariant,
    ): CleanupResult = generationMutex.withLock {
        require(promptVariant == CleanupPromptVariant.SOTTO_NATIVE) {
            "$MODEL_NAME only supports its pinned native prompt"
        }
        val runner = checkNotNull(modelRunner) { "Cleanup model is not loaded" }
        check(state == CleanupState.READY) { "Cleanup engine is not ready: $state" }

        val rawText = text.trim()
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        if (rawText.isEmpty()) {
            return@withLock fallbackResult(rawText, startedAtNs, "Input was empty")
        }

        state = CleanupState.GENERATING
        var firstTokenAtNs: Long? = null
        var stats: GenerationStats? = null
        var finishReason: GenerationFinishReason? = null
        val generatedText = StringBuilder()

        try {
            val conversation = runner.createConversation(systemPrompt = null)
            conversation.generateResponse(
                userTextMessage = nativePrompt(rawText),
                generationOptions = GenerationOptions(
                    temperature = 0f,
                    repetitionPenalty = REPETITION_PENALTY,
                    rngSeed = DETERMINISTIC_SEED,
                    maxTokens = MAX_OUTPUT_TOKENS,
                    inlineThinkingTags = false,
                    enableThinking = false,
                ),
            ).collect { response ->
                when (response) {
                    is MessageResponse.Chunk -> {
                        if (response.text.isNotEmpty() && firstTokenAtNs == null) {
                            firstTokenAtNs = SystemClock.elapsedRealtimeNanos()
                        }
                        generatedText.append(response.text)
                    }
                    is MessageResponse.Complete -> {
                        stats = response.stats
                        finishReason = response.finishReason
                    }
                    is MessageResponse.Error -> throw response.throwable
                    is MessageResponse.AudioSample,
                    is MessageResponse.FunctionCalls,
                    is MessageResponse.ReasoningChunk,
                    -> Unit
                }
            }

            // The publisher's inference contract takes only text before the next section marker.
            // Preserve the complete unguarded generation in modelText for integration diagnosis.
            val unfilteredModelText = generatedText.toString().trim()
            val parsedCandidate = unfilteredModelText.substringBefore(OUTPUT_DELIMITER).trim()
            val candidate = CleanupGuardrails.sanitize(parsedCandidate)
            val hitOutputTokenLimit = stats?.completionTokens?.let {
                it >= MAX_OUTPUT_TOKENS
            } == true
            val fallbackReason = CleanupGuardrails.fallbackReason(
                rawText = rawText,
                candidate = candidate,
                hitOutputTokenLimit = hitOutputTokenLimit,
            )
            val result = CleanupResult(
                modelName = MODEL_NAME,
                quantization = QUANTIZATION,
                rawText = rawText,
                promptVariantId = CleanupPromptVariant.SOTTO_NATIVE.id,
                modelText = unfilteredModelText,
                cleanedText = if (fallbackReason == null) candidate else rawText,
                startedAtNs = startedAtNs,
                firstTokenAtNs = firstTokenAtNs,
                completedAtNs = SystemClock.elapsedRealtimeNanos(),
                usedFallback = fallbackReason != null,
                fallbackReason = fallbackReason,
                promptTokens = stats?.promptTokens,
                completionTokens = stats?.completionTokens,
                tokensPerSecond = stats?.tokenPerSecond,
                finishReason = finishReason?.name,
                maxOutputTokens = MAX_OUTPUT_TOKENS,
            )
            LocalFlowLog.info(
                "Sotto cleanup completed: ttftMs=${result.timeToFirstTokenMs}, " +
                    "totalMs=${result.totalLatencyMs}, fallback=${result.usedFallback}",
            )
            result
        } catch (error: Throwable) {
            LocalFlowLog.error("Sotto cleanup generation failed", error)
            throw error
        } finally {
            if (modelRunner != null) state = CleanupState.READY
        }
    }

    override suspend fun unload() {
        generationMutex.withLock {
            lifecycleMutex.withLock {
                val runner = modelRunner
                if (runner == null) {
                    state = CleanupState.UNLOADED
                    return@withLock
                }
                state = CleanupState.UNLOADING
                modelRunner = null
                try {
                    withContext(Dispatchers.Default) { runner.unload() }
                    state = CleanupState.UNLOADED
                    LocalFlowLog.info("Unloaded $MODEL_NAME $QUANTIZATION")
                } catch (error: Throwable) {
                    state = CleanupState.FAILED
                    LocalFlowLog.error("Failed to unload $MODEL_NAME $QUANTIZATION", error)
                    throw error
                }
            }
        }
    }

    private fun nativePrompt(rawText: String): String =
        "### Input:\n$rawText\n\n### Output:\n"

    private fun fallbackResult(
        rawText: String,
        startedAtNs: Long,
        reason: String,
    ): CleanupResult = CleanupResult(
        modelName = MODEL_NAME,
        quantization = QUANTIZATION,
        rawText = rawText,
        promptVariantId = CleanupPromptVariant.SOTTO_NATIVE.id,
        modelText = "",
        cleanedText = rawText,
        startedAtNs = startedAtNs,
        firstTokenAtNs = null,
        completedAtNs = SystemClock.elapsedRealtimeNanos(),
        usedFallback = true,
        fallbackReason = reason,
        promptTokens = null,
        completionTokens = null,
        tokensPerSecond = null,
        finishReason = null,
        maxOutputTokens = MAX_OUTPUT_TOKENS,
    )

    private companion object {
        const val MODEL_NAME = "Sotto LFM2.5-350M"
        const val QUANTIZATION = "Q4_K_M"
        const val MODEL_CONTEXT_TOKENS = 4_096
        const val MAX_OUTPUT_TOKENS = 900
        const val DETERMINISTIC_SEED = 23L
        const val REPETITION_PENALTY = 1.05f
        const val OUTPUT_DELIMITER = "###"

        // LEAP's conversation API normally applies a chat template. Sotto was trained and screened
        // as a raw completion model, so this template emits BOS plus the user content verbatim.
        const val RAW_COMPLETION_CHAT_TEMPLATE =
            "{{ bos_token }}{% for message in messages %}{{ message['content'] }}{% endfor %}"
    }
}
