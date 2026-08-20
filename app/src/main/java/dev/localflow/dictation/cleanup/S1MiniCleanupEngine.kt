package dev.localflow.dictation.cleanup

import ai.liquid.leap.GenerationOptions
import ai.liquid.leap.ModelLoadingOptions
import ai.liquid.leap.ModelRunner
import ai.liquid.leap.downloader.LeapModelDownloader
import ai.liquid.leap.manifest.ModelSource
import ai.liquid.leap.message.ChatMessage
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

/** Exact publisher-contract runtime for the preferred S1-mini cleanup model. */
class S1MiniCleanupEngine(
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
    private var fixedPromptTokens: Int? = null

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
                IntegrationModels.requireVerified(modelFile, expectedModelSha256, MODEL_NAME)
            }
            onProgress(CleanupLoadProgress(modelFile.length(), modelFile.length()))
            val runner = downloader.loadSimpleModel(
                model = ModelSource(
                    modelPath = modelFile.absolutePath,
                    modelName = MODEL_NAME,
                    quantizationId = QUANTIZATION,
                ),
                options = ModelLoadingOptions(
                    // Preserve the GGUF-embedded Qwen3 template. enableThinking=false below is
                    // what creates the empty thinking prefix used for S1-mini training.
                    chatTemplate = null,
                    contextSize = MODEL_CONTEXT_TOKENS,
                    useMmap = true,
                    cacheOptions = null,
                ),
            )
            fixedPromptTokens = runner.getPromptTokensSize(messages(""), true)
            modelRunner = runner
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
    ): CleanupResult = cleanTranscript(text, promptVariant, emptyList())

    override suspend fun cleanTranscript(
        text: String,
        promptVariant: CleanupPromptVariant,
        preferredBoundaryOffsets: List<Int>,
    ): CleanupResult = generationMutex.withLock {
        require(promptVariant == CleanupPromptVariant.S1_MINI_NATIVE) {
            "$MODEL_NAME only supports its pinned publisher prompt"
        }
        val runner = checkNotNull(modelRunner) { "$MODEL_NAME is not loaded" }
        check(state == CleanupState.READY) { "Cleanup engine is not ready: $state" }

        val rawText = text.trim()
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        if (rawText.isEmpty()) {
            return@withLock fallbackResult(rawText, startedAtNs, "Input was empty")
        }
        state = CleanupState.GENERATING
        try {
            val chunks = S1MiniTranscriptChunker.split(
                text = rawText,
                preferredBoundaryOffsets = preferredBoundaryOffsets,
                maxTokens = RECOMMENDED_MAX_RAW_TOKENS,
                tokenCount = { chunk -> rawTokenCount(runner, chunk) },
            )
            val passResults = chunks.map { chunk -> runSinglePass(runner, chunk.text) }
            combinePasses(rawText, chunks, passResults, startedAtNs)
        } catch (error: Throwable) {
            LocalFlowLog.error("$MODEL_NAME cleanup generation failed", error)
            throw error
        } finally {
            if (modelRunner != null) state = CleanupState.READY
        }
    }

    private suspend fun runSinglePass(runner: ModelRunner, rawText: String): CleanupResult {
        val promptTokens = runner.getPromptTokensSize(messages(rawText), true)
        val rawTokens = promptTokens - checkNotNull(fixedPromptTokens)
        require(rawTokens <= RECOMMENDED_MAX_RAW_TOKENS) {
            "S1-mini cleanup pass exceeded the recommended input-token ceiling"
        }
        val maxOutputTokens = outputCapForRawTokenCount(rawTokens)
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        var firstTokenAtNs: Long? = null
        var stats: GenerationStats? = null
        var finishReason: GenerationFinishReason? = null
        val generatedText = StringBuilder()

        runner.createConversation(systemPrompt = SYSTEM_PROMPT)
            .generateResponse(
                userTextMessage = "$CONTROL_LINE\n$rawText",
                generationOptions = GenerationOptions(
                    temperature = 0f,
                    maxTokens = maxOutputTokens,
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

        val rawModelOutput = generatedText.toString()
        val candidate = CleanupGuardrails.sanitize(rawModelOutput)
        val hitOutputTokenLimit = stats?.completionTokens?.let { it >= maxOutputTokens } == true
        val fallbackReason = CleanupGuardrails.fallbackReason(
            rawText = rawText,
            candidate = candidate,
            hitOutputTokenLimit = hitOutputTokenLimit,
        )
        return CleanupResult(
            modelName = MODEL_NAME,
            quantization = QUANTIZATION,
            rawText = rawText,
            promptVariantId = CleanupPromptVariant.S1_MINI_NATIVE.id,
            modelText = rawModelOutput,
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
            maxOutputTokens = maxOutputTokens,
            modelInputText = rawText,
        )
    }

    private fun combinePasses(
        rawText: String,
        chunks: List<S1MiniTranscriptChunk>,
        passes: List<CleanupResult>,
        startedAtNs: Long,
    ): CleanupResult {
        require(chunks.size == passes.size && passes.isNotEmpty())
        if (passes.size == 1) return passes.single()

        fun joinPassText(value: (CleanupResult) -> String): String = buildString {
            passes.forEachIndexed { index, pass ->
                append(value(pass))
                append(chunks[index].separatorAfter)
            }
        }.trim()

        val fallbackReasons = passes.mapIndexedNotNull { index, pass ->
            pass.fallbackReason?.let { "pass ${index + 1}: $it" }
        }
        val weightedRate = passes.mapNotNull { pass ->
            val tokens = pass.completionTokens ?: return@mapNotNull null
            val rate = pass.tokensPerSecond ?: return@mapNotNull null
            if (rate <= 0f) return@mapNotNull null
            tokens to rate
        }.takeIf { it.size == passes.size }?.let { values ->
            val totalTokens = values.sumOf { it.first }
            if (totalTokens > 0L) {
                val totalDecodeSeconds = values.sumOf { (tokens, rate) ->
                    tokens.toDouble() / rate
                }
                if (totalDecodeSeconds > 0.0) totalTokens / totalDecodeSeconds else null
            } else {
                null
            }
        }?.toFloat()

        return CleanupResult(
            modelName = MODEL_NAME,
            quantization = QUANTIZATION,
            rawText = rawText,
            promptVariantId = CleanupPromptVariant.S1_MINI_NATIVE.id,
            modelText = joinPassText(CleanupResult::modelText),
            cleanedText = joinPassText(CleanupResult::cleanedText),
            startedAtNs = startedAtNs,
            firstTokenAtNs = passes.mapNotNull(CleanupResult::firstTokenAtNs).minOrNull(),
            completedAtNs = passes.last().completedAtNs,
            usedFallback = fallbackReasons.isNotEmpty(),
            fallbackReason = fallbackReasons.takeIf(List<String>::isNotEmpty)?.joinToString("; "),
            promptTokens = passes.mapNotNull(CleanupResult::promptTokens)
                .takeIf { it.size == passes.size }
                ?.sum(),
            completionTokens = passes.mapNotNull(CleanupResult::completionTokens)
                .takeIf { it.size == passes.size }
                ?.sum(),
            tokensPerSecond = weightedRate,
            finishReason = passes.mapNotNull(CleanupResult::finishReason)
                .distinct()
                .joinToString("+")
                .ifEmpty { null },
            maxOutputTokens = passes.sumOf(CleanupResult::maxOutputTokens),
            modelInputText = rawText,
            modelWasRun = passes.any(CleanupResult::modelWasRun),
            cleanupPassCount = passes.size,
        )
    }

    private suspend fun rawTokenCount(runner: ModelRunner, rawText: String): Int =
        runner.getPromptTokensSize(messages(rawText), true) - checkNotNull(fixedPromptTokens)

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
                fixedPromptTokens = null
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

    private fun messages(transcript: String): List<ChatMessage> = listOf(
        ChatMessage(ChatMessage.Role.SYSTEM, SYSTEM_PROMPT),
        ChatMessage(ChatMessage.Role.USER, "$CONTROL_LINE\n$transcript"),
    )

    private fun fallbackResult(
        rawText: String,
        startedAtNs: Long,
        reason: String,
    ): CleanupResult = CleanupResult(
        modelName = MODEL_NAME,
        quantization = QUANTIZATION,
        rawText = rawText,
        promptVariantId = CleanupPromptVariant.S1_MINI_NATIVE.id,
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
        maxOutputTokens = MIN_OUTPUT_TOKENS,
        modelInputText = rawText,
        modelWasRun = false,
    )

    companion object {
        const val MODEL_NAME = "S1-mini by Superwhisper"
        const val QUANTIZATION = "Q4_K_M"
        const val SYSTEM_PROMPT =
            "You are a text normalizer for speech-to-text transcripts. The input begins with a control line specifying the styling, structure, and context settings; clean the transcript to match those settings and output only the cleaned text."
        const val CONTROL_LINE =
            "[Styling: semi-formal] [Structure: prose] [Context: general]"
        const val MODEL_CONTEXT_TOKENS = 4_096
        const val MAX_ALLOWED_OUTPUT_TOKENS = 2_048
        const val MIN_OUTPUT_TOKENS = 32
        const val RECOMMENDED_MAX_RAW_TOKENS = 1_000

        internal fun outputCapForRawTokenCount(rawTokenCount: Int): Int {
            require(rawTokenCount > 0) { "Raw transcript token count must be positive" }
            val outputCap = (13 * rawTokenCount + 9) / 10 + 32
            require(outputCap <= MAX_ALLOWED_OUTPUT_TOKENS) {
                "Transcript is too long for one S1-mini cleanup pass"
            }
            return outputCap
        }
    }
}
