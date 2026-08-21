package dev.localflow.llamacppbenchmark

import org.json.JSONArray
import org.json.JSONObject

internal object NativeResultContract {
    fun validateModelInfo(info: JSONObject, config: BenchmarkConfig) {
        require(info.getInt("schema_version") == 1) { "unsupported native model-info schema" }
        require(info.getLong("model_size_bytes") == S1Contract.MODEL_SIZE_BYTES) {
            "native model size differs from pinned artifact"
        }
        require(info.getInt("context_size") == config.contextTokens) { "context mismatch" }
        require(info.getInt("threads") == config.generationThreads) { "thread mismatch" }
        require(info.getInt("threads_batch") == config.batchThreads) { "batch-thread mismatch" }
        require(info.getInt("batch_size") == config.batchSize) { "batch-size mismatch" }
        require(info.getInt("micro_batch_size") == config.microBatchSize) {
            "micro-batch-size mismatch"
        }
        require(info.getBoolean("use_mmap") == config.useMmap) { "mmap mismatch" }
        require(info.getBoolean("flash_attention") == config.flashAttention) {
            "flash-attention mismatch"
        }
        require(info.getInt("gpu_layers") == config.gpuLayers) { "GPU-layer mismatch" }
        require(info.getString("chat_template").isNotBlank()) { "model chat template is blank" }
        require(info.getString("model_description").isNotBlank()) { "model description is blank" }
        require(info.getLong("model_parameter_count") > 0L) { "model parameter count is invalid" }
        val backendNames = info.getJSONArray("backend_names").let { names ->
            List(names.length()) { index -> names.getString(index) }
        }
        require(backendNames == listOf("CPU")) {
            "native backend list must be exactly [CPU]"
        }
        require(info.getString("selected_cpu_backend_library") in PINNED_CPU_BACKEND_LIBRARIES) {
            "selected CPU backend library is not a packaged ARM variant"
        }
        require(info.getString("system_info").isNotBlank()) { "native system info is blank" }
        require(info.getBoolean("supports_enable_thinking")) {
            "native template does not support enable_thinking"
        }
        require(info.getInt("fixed_prompt_tokens") == S1Contract.EXPECTED_FIXED_PROMPT_TOKENS) {
            "native fixed prompt-token count mismatch"
        }
        require(info.getString("llama_version") == "0.1.0-dev") {
            "llama.cpp semantic version mismatch"
        }
        require(info.getInt("llama_build_number") == 10_450) {
            "llama.cpp build number mismatch"
        }
        require(info.getString("llama_commit") == BuildConfig.LLAMA_CPP_REVISION) {
            "llama.cpp native commit mismatch"
        }
        require(info.getString("llama_build_target") == "Android aarch64") {
            "llama.cpp native build target mismatch"
        }
        require(info.getString("native_build_type") == "Release") {
            "native benchmark is not a Release build"
        }
        require(info.getString("native_compiler").isNotBlank()) { "native compiler is blank" }
        require(info.getString("native_compile_flags").isNotBlank()) {
            "native compile flags are blank"
        }
        info.getBoolean("supports_gpu_offload")
        if (config.useMmap) {
            require(info.getBoolean("supports_mmap")) { "native runtime does not support mmap" }
        }
    }

    fun validateTokenization(tokenization: JSONObject, rawText: String): TokenizationSnapshot {
        require(tokenization.getInt("schema_version") == 1) {
            "unsupported native tokenization schema"
        }
        return validateTokenizationFields(tokenization, rawText)
    }

    private fun validateTokenizationFields(
        tokenization: JSONObject,
        rawText: String,
    ): TokenizationSnapshot {
        val rawTokenIds = tokenization.getJSONArray("raw_token_ids").toIntList("raw_token_ids")
        val promptTokenIds =
            tokenization.getJSONArray("prompt_token_ids").toIntList("prompt_token_ids")
        val rawTokenCount = tokenization.getInt("raw_token_count")
        val promptTokenCount = tokenization.getInt("prompt_token_count")
        val renderedPrompt = tokenization.getString("rendered_prompt")
        require(rawTokenCount == rawTokenIds.size) { "raw token count/IDs mismatch" }
        require(promptTokenCount == promptTokenIds.size) { "prompt token count/IDs mismatch" }
        require(rawTokenCount in 1..S1Contract.MAX_RAW_TOKENS) { "raw token count is out of range" }
        require(promptTokenCount - rawTokenCount == S1Contract.EXPECTED_FIXED_PROMPT_TOKENS) {
            "fixed prompt/template token count mismatch"
        }
        require(renderedPrompt == S1Contract.renderPrompt(rawText)) {
            "rendered prompt differs from exact S1 contract"
        }
        return TokenizationSnapshot(
            rawTokenIds = rawTokenIds,
            rawTokenCount = rawTokenCount,
            renderedPrompt = renderedPrompt,
            promptTokenIds = promptTokenIds,
            promptTokenCount = promptTokenCount,
        )
    }

    fun validateGeneration(
        generation: JSONObject,
        preflight: TokenizationSnapshot,
        rawText: String,
        maxOutputTokens: Int,
    ) {
        require(!generation.has("schema_version")) {
            "native generation must not own the host record schema version"
        }
        val generatedTokenization = validateTokenizationFields(generation, rawText)
        require(generatedTokenization == preflight) { "generation tokenization changed after preflight" }
        val completionIds =
            generation.getJSONArray("completion_token_ids").toIntList("completion_token_ids")
        val completionTokens = generation.getInt("completion_tokens")
        require(completionTokens == completionIds.size) { "completion token count/IDs mismatch" }
        require(completionTokens in 0..maxOutputTokens) { "completion exceeds requested cap" }
        generation.getString("raw_output")

        val finishReason = generation.getString("finish_reason")
        val hitTokenCap = generation.getBoolean("hit_token_cap")
        require(finishReason == "eog" || finishReason == "token_cap") {
            "unsupported finish reason"
        }
        require(hitTokenCap == (finishReason == "token_cap")) {
            "finish reason and token-cap flag disagree"
        }
        if (hitTokenCap) {
            require(completionTokens == maxOutputTokens) { "token-cap finish occurred below cap" }
            require(generation.isNull("eog_token_id")) { "capped generation reports EOG" }
        } else {
            require(!generation.isNull("eog_token_id")) { "EOG finish omitted EOG token" }
        }

        val startedAtNs = generation.nonnegativeLong("started_at_ns")
        val promptStartedAtNs = generation.nonnegativeLong("prompt_started_at_ns")
        val promptCompletedAtNs = generation.nonnegativeLong("prompt_completed_at_ns")
        val completedAtNs = generation.nonnegativeLong("completed_at_ns")
        require(startedAtNs <= promptStartedAtNs) { "prompt started before generation" }
        require(promptStartedAtNs <= promptCompletedAtNs) { "prompt timestamps are reversed" }
        require(promptCompletedAtNs <= completedAtNs) { "completion precedes prompt evaluation" }
        if (!generation.isNull("first_token_at_ns")) {
            val firstTokenAtNs = generation.nonnegativeLong("first_token_at_ns")
            require(firstTokenAtNs in promptCompletedAtNs..completedAtNs) {
                "first-token timestamp is out of order"
            }
        } else {
            require(completionTokens == 0) { "completion tokens exist without first-token time" }
        }
        for (field in DOUBLE_METRIC_FIELDS) {
            require(generation.getDouble(field) >= 0.0) { "$field is negative" }
        }
        for (field in INTEGER_METRIC_FIELDS) {
            require(generation.getLong(field) >= 0L) { "$field is negative" }
        }
    }

    private fun JSONArray.toIntList(label: String): List<Int> =
        List(length()) { index ->
            runCatching { getInt(index) }.getOrElse {
                throw IllegalArgumentException("$label contains a non-integer", it)
            }
        }

    private fun JSONObject.nonnegativeLong(field: String): Long =
        getLong(field).also { require(it >= 0L) { "$field is negative" } }

    private val DOUBLE_METRIC_FIELDS = listOf(
        "prompt_eval_ms",
        "decode_ms",
        "total_ms",
        "prompt_tokens_per_second",
        "decode_tokens_per_second",
        "perf_prompt_eval_ms",
        "perf_decode_ms",
    )
    private val INTEGER_METRIC_FIELDS = listOf(
        "perf_prompt_tokens",
        "perf_decode_tokens",
        "perf_reused_graphs",
    )

    internal val PINNED_CPU_BACKEND_LIBRARIES = setOf(
        "libggml-cpu-android_armv8.0_1.so",
        "libggml-cpu-android_armv8.2_1.so",
        "libggml-cpu-android_armv8.2_2.so",
        "libggml-cpu-android_armv8.6_1.so",
        "libggml-cpu-android_armv9.0_1.so",
        "libggml-cpu-android_armv9.2_1.so",
        "libggml-cpu-android_armv9.2_2.so",
    )
}

internal data class TokenizationSnapshot(
    val rawTokenIds: List<Int>,
    val rawTokenCount: Int,
    val renderedPrompt: String,
    val promptTokenIds: List<Int>,
    val promptTokenCount: Int,
)
