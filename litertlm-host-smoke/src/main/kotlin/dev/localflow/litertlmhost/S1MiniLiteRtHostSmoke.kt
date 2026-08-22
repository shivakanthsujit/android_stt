package dev.localflow.litertlmhost

import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.ThinkingConfig
import com.google.gson.GsonBuilder
import java.nio.file.Files
import java.nio.file.Path
import kotlin.io.path.createDirectories
import kotlin.io.path.fileSize

private data class Arguments(
    val model: Path,
    val raw: String,
    val rawTokens: Int,
    val report: Path,
    val cacheDir: Path,
    val backendName: String,
    val threads: Int,
)

private data class SmokeReport(
    val schema_version: Int = 1,
    val result: String,
    val runtime: String,
    val runtime_version: String,
    val backend: String,
    val cpu_threads: Int?,
    val model_bytes: Long,
    val model_sha256: String,
    val context_tokens: Int,
    val fixed_prompt_tokens: Int,
    val raw: String,
    val raw_tokens: Int,
    val expected_prompt_tokens: Int,
    val max_output_tokens: Int,
    val rendered_prompt_bytes: Int,
    val rendered_prompt_sha256: String,
    val response: String,
    val wall_init_seconds: Double,
    val wall_generation_seconds: Double,
    val benchmark_available: Boolean,
    val benchmark_error: String?,
    val runtime_init_seconds: Double?,
    val time_to_first_token_seconds: Double?,
    val prefill_tokens: Int?,
    val decode_tokens: Int?,
    val prefill_tokens_per_second: Double?,
    val decode_tokens_per_second: Double?,
    val conversation_token_count: Int,
    val hit_output_cap: Boolean?,
)

@OptIn(ExperimentalApi::class)
fun main(args: Array<String>) {
    val parsed = parseArguments(args)
    require(Files.isRegularFile(parsed.model)) { "model is not a regular file: ${parsed.model}" }
    require(parsed.model.fileSize() == S1MiniContract.MODEL_BYTES) {
        "model byte size mismatch: ${parsed.model.fileSize()} != ${S1MiniContract.MODEL_BYTES}"
    }
    val modelSha256 = S1MiniContract.sha256(parsed.model)
    require(modelSha256 == S1MiniContract.MODEL_SHA256) {
        "model SHA-256 mismatch: $modelSha256"
    }
    parsed.cacheDir.createDirectories()
    parsed.report.parent?.createDirectories()

    val backend = when (parsed.backendName) {
        "cpu" -> Backend.CPU(threadCount = parsed.threads)
        "gpu" -> Backend.GPU()
        else -> error("unsupported backend: ${parsed.backendName}")
    }
    val maxOutputTokens = S1MiniContract.maxOutputTokens(parsed.rawTokens)
    val extraContext = mapOf<String, Any>("enable_thinking" to false)
    val thinkingConfig = ThinkingConfig(enableThinking = false)
    val conversationConfig = ConversationConfig(
        systemInstruction = Contents.of(S1MiniContract.SYSTEM_PROMPT),
        samplerConfig = SamplerConfig(topK = 1, topP = 1.0, temperature = 0.0, seed = 0),
        extraContext = extraContext,
        prefillPrefaceOnInit = false,
        maxOutputToken = maxOutputTokens,
        thinkingConfig = thinkingConfig,
    )

    Engine(
        EngineConfig(
            modelPath = parsed.model.toAbsolutePath().toString(),
            backend = backend,
            maxNumTokens = S1MiniContract.CONTEXT_TOKENS,
            cacheDir = parsed.cacheDir.toAbsolutePath().toString(),
        ),
    ).use { engine ->
        val initStart = System.nanoTime()
        engine.initialize()
        val initSeconds = (System.nanoTime() - initStart) / 1_000_000_000.0
        engine.createConversation(conversationConfig).use { conversation ->
            val message = Message.user(S1MiniContract.userText(parsed.raw))
            val expectedPrompt = S1MiniContract.expectedRenderedPrompt(parsed.raw)
            val renderedPrompt = S1MiniContract.selectExactRenderedPrompt(
                expected = expectedPrompt,
                preface = conversation.renderPrefaceIntoString(),
                renderedMessage = conversation.renderMessageIntoString(message, extraContext),
            )
            val generationStart = System.nanoTime()
            val response = conversation.sendMessage(
                message = message,
                extraContext = extraContext,
                maxOutputToken = maxOutputTokens,
                thinkingConfig = thinkingConfig,
            ).toString()
            val generationSeconds = (System.nanoTime() - generationStart) / 1_000_000_000.0
            var benchmarkError: String? = null
            val benchmark = try {
                conversation.getBenchmarkInfo()
            } catch (failure: RuntimeException) {
                benchmarkError = "${failure::class.qualifiedName}: ${failure.message}"
                null
            }
            val report = SmokeReport(
                result = "pass",
                runtime = "LiteRT-LM JVM",
                runtime_version = "0.16.1",
                backend = parsed.backendName,
                cpu_threads = parsed.threads.takeIf { parsed.backendName == "cpu" },
                model_bytes = parsed.model.fileSize(),
                model_sha256 = modelSha256,
                context_tokens = S1MiniContract.CONTEXT_TOKENS,
                fixed_prompt_tokens = S1MiniContract.FIXED_PROMPT_TOKENS,
                raw = parsed.raw,
                raw_tokens = parsed.rawTokens,
                expected_prompt_tokens = S1MiniContract.FIXED_PROMPT_TOKENS + parsed.rawTokens,
                max_output_tokens = maxOutputTokens,
                rendered_prompt_bytes = renderedPrompt.toByteArray().size,
                rendered_prompt_sha256 = S1MiniContract.sha256(renderedPrompt.toByteArray()),
                response = response,
                wall_init_seconds = initSeconds,
                wall_generation_seconds = generationSeconds,
                benchmark_available = benchmark != null,
                benchmark_error = benchmarkError,
                runtime_init_seconds = benchmark?.initTimeInSecond,
                time_to_first_token_seconds = benchmark?.timeToFirstTokenInSecond,
                prefill_tokens = benchmark?.lastPrefillTokenCount,
                decode_tokens = benchmark?.lastDecodeTokenCount,
                prefill_tokens_per_second = benchmark?.lastPrefillTokensPerSecond,
                decode_tokens_per_second = benchmark?.lastDecodeTokensPerSecond,
                conversation_token_count = conversation.getTokenCount(),
                hit_output_cap = benchmark?.lastDecodeTokenCount?.let { it >= maxOutputTokens },
            )
            Files.writeString(
                parsed.report,
                GsonBuilder().setPrettyPrinting().create().toJson(report) + "\n",
            )
            println("LiteRT-LM host smoke passed; report=${parsed.report}")
            println("response=$response")
        }
    }
}

private fun parseArguments(args: Array<String>): Arguments {
    val values = mutableMapOf<String, String>()
    var index = 0
    while (index < args.size) {
        val key = args[index]
        require(key.startsWith("--") && index + 1 < args.size) { "invalid argument near: $key" }
        require(values.put(key, args[index + 1]) == null) { "duplicate argument: $key" }
        index += 2
    }
    val model = Path.of(values.require("--model"))
    val raw = values.require("--raw")
    require(raw.isNotBlank()) { "--raw must be non-blank" }
    val rawTokens = values.require("--raw-tokens").toInt()
    require(rawTokens > 0) { "--raw-tokens must be positive" }
    val report = Path.of(values.require("--report"))
    val cacheDir = Path.of(values.require("--cache-dir"))
    val backend = values["--backend"] ?: "cpu"
    val threads = (values["--threads"] ?: "2").toInt()
    require(threads > 0) { "--threads must be positive" }
    val known = setOf("--model", "--raw", "--raw-tokens", "--report", "--cache-dir", "--backend", "--threads")
    require(values.keys.all(known::contains)) { "unknown arguments: ${values.keys - known}" }
    return Arguments(model, raw, rawTokens, report, cacheDir, backend, threads)
}

private fun Map<String, String>.require(key: String): String =
    get(key) ?: error("missing required argument: $key")
