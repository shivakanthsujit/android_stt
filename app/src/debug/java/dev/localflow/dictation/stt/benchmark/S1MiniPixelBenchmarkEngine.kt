package dev.localflow.dictation.stt.benchmark

import ai.liquid.leap.GenerationOptions
import ai.liquid.leap.ModelLoadingOptions
import ai.liquid.leap.ModelRunner
import ai.liquid.leap.downloader.LeapModelDownloader
import ai.liquid.leap.inferenceengine.EngineOptions
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
import java.nio.file.Files
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
    val requestedConfig: Config = Config(),
) {
    /** Requested LEAP settings. Null means the SDK-selected CPU-thread control or cache off. */
    data class Config(
        val contextTokens: Int = MODEL_CONTEXT_TOKENS,
        val cpuThreads: Int? = null,
        val cacheMemoryMb: Int? = null,
    ) {
        init {
            require(contextTokens in ALLOWED_CONTEXT_TOKENS) {
                "Unsupported S1-mini context: $contextTokens"
            }
            require(cpuThreads == null || cpuThreads in ALLOWED_CPU_THREADS) {
                "Unsupported S1-mini CPU thread count: $cpuThreads"
            }
            require(cacheMemoryMb == null || cacheMemoryMb in ALLOWED_CACHE_MEMORY_MB) {
                "Unsupported S1-mini cache memory: $cacheMemoryMb MiB"
            }
        }

        val cpuThreadsMode: String
            get() = if (cpuThreads == null) CPU_THREADS_MODE_IMPLICIT else CPU_THREADS_MODE_EXPLICIT

        val cacheEnabled: Boolean
            get() = cacheMemoryMb != null

        val cacheMaxMemoryBytes: Long
            get() = cacheMemoryMb?.toLong()?.times(BYTES_PER_MIB) ?: 0L

        val cacheMaxEntries: Int
            get() = if (cacheEnabled) CACHE_MAX_MEMORY_ENTRIES else 0

        val cacheDiskDisabled: Boolean
            get() = true

        val cacheMaxDiskEntries: Int
            get() = 0

        internal fun toModelLoadingOptions(cacheRoot: File): ModelLoadingOptions =
            ModelLoadingOptions(
                // Null preserves the GGUF-embedded Qwen3 template. GenerationOptions below
                // supplies enableThinking=false, producing the trained empty-thinking prefix.
                chatTemplate = null,
                contextSize = contextTokens,
                useMmap = true,
                cacheOptions = cacheMemoryMb?.let {
                    EngineOptions.CacheOptions(
                        // The API requires a path even when disk caching is explicitly disabled.
                        path = requireMemoryCacheDirectory(cacheRoot).absolutePath,
                        maxEntries = 0,
                        enabled = true,
                        maxEntriesDisk = cacheMaxDiskEntries,
                        maxEntriesMemory = cacheMaxEntries,
                        maxBytesMemory = cacheMaxMemoryBytes,
                        diskDisabled = cacheDiskDisabled,
                    )
                },
            ).apply {
                // Leaving this unset preserves CpuThreadAdvisor's SDK-selected control value.
                this@Config.cpuThreads?.let { cpuThreads = it }
            }
    }

    data class Result(
        val cleanupResult: CleanupResult,
        val cachedPromptTokens: Long?,
        val fixedPromptTokens: Int,
        val resolvedCpuThreads: Int,
        val requestedConfig: Config,
    )

    private val downloader = LeapModelDownloader(context.applicationContext)
    private val cacheRoot = context.applicationContext.cacheDir
    private val lifecycleMutex = Mutex()
    private val generationMutex = Mutex()
    private var modelRunner: ModelRunner? = null
    private var loadedCpuThreads: Int? = null

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
        val loadingOptions = withContext(Dispatchers.IO) {
            requestedConfig.toModelLoadingOptions(cacheRoot)
        }
        val loadedRunner = downloader.loadSimpleModel(
            model = ModelSource(
                modelPath = modelFile.absolutePath,
                modelName = MODEL_NAME,
                quantizationId = QUANTIZATION,
            ),
            options = loadingOptions,
        )
        modelRunner = loadedRunner
        loadedCpuThreads = loadingOptions.cpuThreads
        CleanupLoadResult(
            startedAtNs = startedAtNs,
            completedAtNs = SystemClock.elapsedRealtimeNanos(),
            reusedLoadedRunner = false,
        )
    }

    suspend fun clean(text: String, maxOutputTokens: Int): Result =
        generationMutex.withLock {
            require(text.isNotBlank()) { "S1-mini benchmark input must not be blank" }
            require(maxOutputTokens in 1..MAX_ALLOWED_OUTPUT_TOKENS) {
                "S1-mini max output tokens are out of range: $maxOutputTokens"
            }
            val runner = checkNotNull(modelRunner) { "S1-mini model is not loaded" }
            val resolvedCpuThreads = checkNotNull(loadedCpuThreads) {
                "S1-mini loaded CPU thread count is unavailable"
            }
            val prepared = prepareGeneration(runner, text)
            require(prepared.maxOutputTokens == maxOutputTokens) {
                "S1-mini output-cap mismatch: prepared=${prepared.maxOutputTokens}, " +
                    "requested=$maxOutputTokens"
            }
            requireContextCapacity(
                promptTokens = prepared.promptTokens,
                maxOutputTokens = maxOutputTokens,
                contextTokens = requestedConfig.contextTokens,
            )
            require(prepared.fixedPromptTokens < prepared.promptTokens) {
                "S1-mini prompt does not contain transcript tokens"
            }
            require(prepared.fixedPromptTokens == EXPECTED_FIXED_PROMPT_TOKENS) {
                "S1-mini fixed prompt-token drift: expected=$EXPECTED_FIXED_PROMPT_TOKENS, " +
                    "runtime=${prepared.fixedPromptTokens}"
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
            Result(
                cleanupResult = CleanupResult(
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
                ),
                cachedPromptTokens = stats?.cachedPromptTokens,
                fixedPromptTokens = prepared.fixedPromptTokens,
                resolvedCpuThreads = resolvedCpuThreads,
                requestedConfig = requestedConfig,
            )
        }

    private suspend fun prepareGeneration(
        runner: ModelRunner,
        rawText: String,
    ): PreparedGeneration {
        fun messages(transcript: String) = listOf(
            ChatMessage(ChatMessage.Role.SYSTEM, SYSTEM_PROMPT),
            ChatMessage(ChatMessage.Role.USER, "$CONTROL_LINE\n$transcript"),
        )
        val promptTokens = runner.getPromptTokensSize(messages(rawText), true)
        val fixedPromptTokens = runner.getPromptTokensSize(messages(""), true)
        val rawTokens = promptTokens - fixedPromptTokens
        require(rawTokens > 0) { "S1-mini tokenizer returned no raw transcript tokens" }
        return PreparedGeneration(
            promptTokens = promptTokens,
            fixedPromptTokens = fixedPromptTokens,
            maxOutputTokens =
                ((13 * rawTokens + 9) / 10 + 32).coerceAtMost(MAX_ALLOWED_OUTPUT_TOKENS),
        )
    }

    private data class PreparedGeneration(
        val promptTokens: Int,
        val fixedPromptTokens: Int,
        val maxOutputTokens: Int,
    )

    suspend fun unload() {
        generationMutex.withLock {
            lifecycleMutex.withLock {
                val runner = modelRunner ?: return@withLock
                modelRunner = null
                loadedCpuThreads = null
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
        const val EXPECTED_FIXED_PROMPT_TOKENS = 78
        const val CPU_THREADS_MODE_IMPLICIT = "implicit"
        const val CPU_THREADS_MODE_EXPLICIT = "explicit"
        const val CACHE_MAX_MEMORY_ENTRIES = 4
        const val CACHE_DIRECTORY = "s1-mini-benchmark-cache"
        const val BYTES_PER_MIB = 1_048_576L
        val ALLOWED_CONTEXT_TOKENS = setOf(4_096, 3_072, 2_560)
        val ALLOWED_CPU_THREADS = setOf(2, 3, 4)
        val ALLOWED_CACHE_MEMORY_MB = setOf(32, 64)

        internal fun requireMemoryCacheDirectory(cacheRoot: File): File {
            require(cacheRoot.isDirectory) {
                "S1-mini app cache root is missing or is not a directory"
            }
            val canonicalRoot = cacheRoot.canonicalFile
            val directory = cacheRoot.resolve(CACHE_DIRECTORY)
            require(!Files.isSymbolicLink(directory.toPath())) {
                "S1-mini benchmark cache path must not be a symbolic link"
            }
            require(directory.isDirectory || directory.mkdir()) {
                "Could not create S1-mini benchmark cache directory"
            }
            val canonicalDirectory = directory.canonicalFile
            require(canonicalDirectory.parentFile == canonicalRoot) {
                "S1-mini benchmark cache path escapes the app cache root"
            }
            return canonicalDirectory
        }

        internal fun requireContextCapacity(
            promptTokens: Int,
            maxOutputTokens: Int,
            contextTokens: Int,
        ) {
            require(promptTokens > 0) { "S1-mini prompt tokens must be positive" }
            require(maxOutputTokens > 0) { "S1-mini max output tokens must be positive" }
            require(promptTokens + maxOutputTokens <= contextTokens) {
                "S1-mini request exceeds context: prompt=$promptTokens, " +
                    "max_output=$maxOutputTokens, context=$contextTokens"
            }
        }
    }
}
