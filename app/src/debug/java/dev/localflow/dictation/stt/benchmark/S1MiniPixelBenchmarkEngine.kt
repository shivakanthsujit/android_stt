package dev.localflow.dictation.stt.benchmark

import ai.liquid.leap.GenerationOptions
import ai.liquid.leap.ModelLoadingOptions
import ai.liquid.leap.ModelRunner
import ai.liquid.leap.downloader.LeapModelDownloader
import ai.liquid.leap.manifest.ModelSource
import ai.liquid.leap.message.GenerationFinishReason
import ai.liquid.leap.message.GenerationStats
import ai.liquid.leap.message.ChatMessage
import ai.liquid.leap.message.MessageResponse
import android.content.Context
import android.os.SystemClock
import dev.localflow.dictation.IntegrationModels
import dev.localflow.dictation.cleanup.CleanupLoadProgress
import dev.localflow.dictation.cleanup.CleanupLoadResult
import dev.localflow.dictation.cleanup.CleanupResult
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext

/** Debug-only S1-mini v1 runner that preserves the publisher's inference contract. */
class S1MiniPixelBenchmarkEngine(
    context: Context,
    private val modelFile: File,
    private val expectedModelSha256: String,
) {
    private val downloader = LeapModelDownloader(context.applicationContext)
    private val lifecycleMutex = Mutex()
    private val generationMutex = Mutex()
    private var modelRunner: ModelRunner? = null

    suspend fun load(
        onProgress: (CleanupLoadProgress) -> Unit = {},
    ): CleanupLoadResult = lifecycleMutex.withLock {
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        if (modelRunner != null) {
            return@withLock CleanupLoadResult(
                startedAtNs = startedAtNs,
                completedAtNs = SystemClock.elapsedRealtimeNanos(),
                reusedLoadedRunner = true,
            )
        }
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
                // Null preserves the GGUF-embedded Qwen3 template. GenerationOptions below
                // supplies enableThinking=false, producing the trained empty-thinking prefix.
                chatTemplate = null,
                contextSize = MODEL_CONTEXT_TOKENS,
                useMmap = true,
                cacheOptions = null,
            ),
        )
        CleanupLoadResult(
            startedAtNs = startedAtNs,
            completedAtNs = SystemClock.elapsedRealtimeNanos(),
            reusedLoadedRunner = false,
        )
    }

    suspend fun clean(text: String, maxOutputTokens: Int): CleanupResult =
        generationMutex.withLock {
            require(text.isNotBlank()) { "S1-mini benchmark input must not be blank" }
            require(maxOutputTokens in 1..MAX_ALLOWED_OUTPUT_TOKENS) {
                "S1-mini max output tokens are out of range: $maxOutputTokens"
            }
            val runner = checkNotNull(modelRunner) { "S1-mini model is not loaded" }
            val runtimeMaxOutputTokens = publisherOutputCap(runner, text)
            require(runtimeMaxOutputTokens == maxOutputTokens) {
                "S1-mini output-cap mismatch: prepared=$maxOutputTokens, " +
                    "runtime=$runtimeMaxOutputTokens"
            }
            val startedAtNs = SystemClock.elapsedRealtimeNanos()
            var firstTokenAtNs: Long? = null
            var stats: GenerationStats? = null
            var finishReason: GenerationFinishReason? = null
            val generatedText = StringBuilder()
            val conversation = runner.createConversation(systemPrompt = SYSTEM_PROMPT)
            conversation.generateResponse(
                userTextMessage = "$CONTROL_LINE\n$text",
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
            val rawOutput = generatedText.toString()
            CleanupResult(
                modelName = MODEL_NAME,
                quantization = QUANTIZATION,
                rawText = text,
                promptVariantId = PROMPT_PROFILE,
                modelText = rawOutput,
                cleanedText = rawOutput,
                startedAtNs = startedAtNs,
                firstTokenAtNs = firstTokenAtNs,
                completedAtNs = SystemClock.elapsedRealtimeNanos(),
                usedFallback = false,
                fallbackReason = null,
                promptTokens = stats?.promptTokens,
                completionTokens = stats?.completionTokens,
                tokensPerSecond = stats?.tokenPerSecond,
                finishReason = finishReason?.name,
                maxOutputTokens = maxOutputTokens,
                modelInputText = text,
            )
        }

    private suspend fun publisherOutputCap(runner: ModelRunner, rawText: String): Int {
        fun messages(transcript: String) = listOf(
            ChatMessage(ChatMessage.Role.SYSTEM, SYSTEM_PROMPT),
            ChatMessage(ChatMessage.Role.USER, "$CONTROL_LINE\n$transcript"),
        )
        val promptTokens = runner.getPromptTokensSize(messages(rawText), true)
        val fixedPromptTokens = runner.getPromptTokensSize(messages(""), true)
        val rawTokens = promptTokens - fixedPromptTokens
        require(rawTokens > 0) { "S1-mini tokenizer returned no raw transcript tokens" }
        return ((13 * rawTokens + 9) / 10 + 32).coerceAtMost(MAX_ALLOWED_OUTPUT_TOKENS)
    }

    suspend fun unload() {
        generationMutex.withLock {
            lifecycleMutex.withLock {
                val runner = modelRunner ?: return@withLock
                modelRunner = null
                withContext(Dispatchers.Default) { runner.unload() }
            }
        }
    }

    companion object {
        const val MODEL_NAME = "S1-mini v1"
        const val QUANTIZATION = "Q4_K_M"
        const val PROMPT_PROFILE = "s1-mini-v1-publisher"
        const val SYSTEM_PROMPT =
            "You are a text normalizer for speech-to-text transcripts. The input begins with a control line specifying the styling, structure, and context settings; clean the transcript to match those settings and output only the cleaned text."
        const val CONTROL_LINE =
            "[Styling: semi-formal] [Structure: prose] [Context: general]"
        const val MODEL_CONTEXT_TOKENS = 4_096
        const val MAX_ALLOWED_OUTPUT_TOKENS = 2_048
    }
}
