package dev.localflow.llamacppbenchmark

import org.json.JSONArray
import org.json.JSONObject

internal object S1Contract {
    const val MODEL_FILE_NAME = "s1-mini-q4_k_m.gguf"
    const val MODEL_SIZE_BYTES = 484_219_808L
    const val MODEL_SHA256 =
        "3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634"
    const val SYSTEM_PROMPT =
        "You are a text normalizer for speech-to-text transcripts. The input begins with a control line specifying the styling, structure, and context settings; clean the transcript to match those settings and output only the cleaned text."
    const val CONTROL_LINE =
        "[Styling: semi-formal] [Structure: prose] [Context: general]"
    const val PROMPT_PROFILE = "s1-mini-v1-publisher"
    const val EXPECTED_FIXED_PROMPT_TOKENS = 78
    const val MAX_RAW_TOKENS = 1_000
    const val MAX_OUTPUT_TOKENS = 2_048

    fun renderPrompt(rawText: String): String =
        "<|im_start|>system\n$SYSTEM_PROMPT<|im_end|>\n" +
            "<|im_start|>user\n$CONTROL_LINE\n$rawText<|im_end|>\n" +
            "<|im_start|>assistant\n<think>\n\n</think>\n\n"

    fun outputCap(rawTokenCount: Int): Int {
        require(rawTokenCount in 1..MAX_RAW_TOKENS) { "raw token count is out of range" }
        return ((13L * rawTokenCount + 9L) / 10L + 32L).toInt().also { cap ->
            require(cap <= MAX_OUTPUT_TOKENS) { "output cap exceeds native safety limit" }
        }
    }
}

internal data class BenchmarkConfig(
    val contextTokens: Int = 2_560,
    val generationThreads: Int = 2,
    val batchThreads: Int = 2,
    val batchSize: Int = 512,
    val microBatchSize: Int = 512,
    val useMmap: Boolean = true,
    val flashAttention: Boolean = false,
    val gpuLayers: Int = 0,
) {
    init {
        require(contextTokens in APPROVED_CONTEXT_TOKENS) { "unapproved context size" }
        require(generationThreads in APPROVED_GENERATION_THREADS) {
            "unapproved generation thread count"
        }
        require(batchThreads in APPROVED_BATCH_THREADS) { "unapproved batch thread count" }
        require(batchSize in APPROVED_BATCH_SIZES) { "unapproved batch size" }
        require(microBatchSize in APPROVED_BATCH_SIZES) { "unapproved micro-batch size" }
        require(microBatchSize <= batchSize) { "micro-batch size exceeds batch size" }
        require(gpuLayers == 0) { "GPU offload is not enabled for the CPU benchmark" }
    }

    fun toJson(): JSONObject = JSONObject()
        .put("context_tokens", contextTokens)
        .put("generation_threads", generationThreads)
        .put("batch_threads", batchThreads)
        .put("batch_size", batchSize)
        .put("micro_batch_size", microBatchSize)
        .put("use_mmap", useMmap)
        .put("flash_attention", flashAttention)
        .put("gpu_layers", gpuLayers)

    companion object {
        val APPROVED_CONTEXT_TOKENS = setOf(2_560, 3_072, 4_096)
        val APPROVED_GENERATION_THREADS = setOf(2, 3, 4, 6, 8)
        val APPROVED_BATCH_THREADS = setOf(2, 4, 6, 8)
        val APPROVED_BATCH_SIZES = setOf(128, 256, 512)
    }
}

internal const val PHASE_WARMUP = "warmup"
internal const val PHASE_MEASURED = "measured"

internal data class BenchmarkJobOrderEntry(
    val caseIndex: Int,
    val phase: String,
    val repeatIndex: Int,
)

internal fun buildBenchmarkJobOrder(
    caseCount: Int,
    warmupRuns: Int,
    measuredRepeats: Int,
): List<BenchmarkJobOrderEntry> {
    require(caseCount > 0) { "caseCount must be positive" }
    require(warmupRuns >= 0) { "warmupRuns must be non-negative" }
    require(measuredRepeats > 0) { "measuredRepeats must be positive" }
    val measuredOrder = if (caseCount == 1) listOf(0) else (1 until caseCount).toList() + 0
    return buildList {
        repeat(warmupRuns) { repeatIndex ->
            add(BenchmarkJobOrderEntry(0, PHASE_WARMUP, repeatIndex))
        }
        repeat(measuredRepeats) { repeatIndex ->
            measuredOrder.forEach { caseIndex ->
                add(BenchmarkJobOrderEntry(caseIndex, PHASE_MEASURED, repeatIndex))
            }
        }
    }
}

internal data class TranscriptCase(
    val caseId: String,
    val rawText: String,
    val categories: List<String>,
)

internal object TranscriptCaseParser {
    private val safeId = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    private val allowedFields = setOf("id", "raw", "categories")

    fun parseLine(line: String, lineNumber: Int): TranscriptCase {
        val json = runCatching { JSONObject(line) }.getOrElse {
            throw IllegalArgumentException("invalid cases line $lineNumber", it)
        }
        val fields = json.keys().asSequence().toSet()
        require(fields == allowedFields) {
            "cases line $lineNumber must contain only id, raw, and categories"
        }
        val caseId = json.getString("id")
        val rawText = json.getString("raw")
        val categoryJson = json.getJSONArray("categories")
        val categories = List(categoryJson.length()) { index -> categoryJson.getString(index) }
        require(safeId.matches(caseId)) { "invalid case id on line $lineNumber" }
        require(rawText.isNotBlank()) { "empty transcript on line $lineNumber" }
        require(categories.all(String::isNotBlank)) { "empty category on line $lineNumber" }
        return TranscriptCase(caseId, rawText, categories)
    }
}

internal data class HostMetrics(
    val processCpuMs: Long,
    val processPssKb: Long,
    val nativeHeapBytes: Long,
    val thermalStatus: Int,
)

internal fun buildBenchmarkRecord(
    runId: String,
    job: BenchmarkJobOrderEntry,
    case: TranscriptCase,
    maxOutputTokens: Int,
    modelSha256: String,
    requestedConfig: JSONObject,
    nativeModelInfo: JSONObject,
    appBuildInfo: JSONObject,
    nativeGeneration: JSONObject,
    hostMetrics: HostMetrics,
    modelLoadMs: Long,
    createdAtUtc: String,
): JSONObject {
    val record = JSONObject()
        .put("schema_version", 1)
        .put("run_id", runId)
        .put("phase", job.phase)
        .put("repeat_index", job.repeatIndex)
        .put("case_id", case.caseId)
        .put("categories", JSONArray(case.categories))
        .put("raw_text", case.rawText)
        .put("model_file", S1Contract.MODEL_FILE_NAME)
        .put("model_sha256", modelSha256)
        .put("prompt_profile", S1Contract.PROMPT_PROFILE)
        .put("requested_max_output_tokens", maxOutputTokens)
        .put("model_load_ms", modelLoadMs)
        .put("requested_config", requestedConfig)
        .put("native_model_info", nativeModelInfo)
        .put("app_build", appBuildInfo)
        .put("process_cpu_ms", hostMetrics.processCpuMs)
        .put("process_pss_kb_after_inference", hostMetrics.processPssKb)
        .put("native_heap_bytes_after_inference", hostMetrics.nativeHeapBytes)
        .put("thermal_status_after_inference", hostMetrics.thermalStatus)
        .put("created_at_utc", createdAtUtc)

    nativeGeneration.keys().forEach { key ->
        require(!record.has(key)) { "native generation field collides with host field: $key" }
        record.put(key, nativeGeneration.get(key))
    }
    return record
}
