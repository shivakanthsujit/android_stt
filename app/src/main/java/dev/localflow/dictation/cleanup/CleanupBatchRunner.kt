package dev.localflow.dictation.cleanup

import android.content.Context
import android.os.SystemClock
import dev.localflow.dictation.LocalFlowLog
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

data class CleanupBatchProgress(
    val promptVariant: CleanupPromptVariant,
    val runIndex: Int,
    val totalRuns: Int,
    val caseId: String,
)

data class CleanupBatchSummary(
    val resultFile: File,
    val totalRuns: Int,
    val exactMatches: Int,
    val fallbackCount: Int,
    val durationMs: Long,
)

/** Runs the checked-in cleanup corpus directly against the loaded model without microphone use. */
class CleanupBatchRunner(
    context: Context,
    private val cleanupEngine: CleanupEngine,
) {
    private val appContext = context.applicationContext

    suspend fun run(
        promptVariants: List<CleanupPromptVariant> = CleanupPromptVariant.entries,
        onProgress: (CleanupBatchProgress) -> Unit = {},
    ): CleanupBatchSummary = withContext(Dispatchers.Default) {
        require(promptVariants.isNotEmpty()) { "At least one prompt variant is required" }
        check(cleanupEngine.state == CleanupState.READY) { "Cleanup model is not ready" }

        val cases = loadCases()
        val totalRuns = cases.size * promptVariants.size
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        var runIndex = 0
        var exactMatches = 0
        var fallbackCount = 0
        // App-specific external storage remains sandboxed from normal apps on modern Android but
        // is intentionally adb-pullable for this developer benchmark. Fall back to internal
        // storage if external app storage is unavailable.
        val resultsRoot = appContext.getExternalFilesDir(null) ?: appContext.filesDir
        val outputDirectory = File(resultsRoot, RESULTS_DIRECTORY).apply { mkdirs() }
        val resultFile = File(outputDirectory, "cleanup-eval-${System.currentTimeMillis()}.jsonl")

        resultFile.bufferedWriter().use { writer ->
            cases.forEachIndexed { caseIndex, evaluationCase ->
                // Rotate A/B/C order per case to reduce warm-up and thermal ordering bias.
                val offset = caseIndex % promptVariants.size
                val orderedVariants = promptVariants.drop(offset) + promptVariants.take(offset)
                orderedVariants.forEach { variant ->
                    runIndex += 1
                    onProgress(
                        CleanupBatchProgress(
                            promptVariant = variant,
                            runIndex = runIndex,
                            totalRuns = totalRuns,
                            caseId = evaluationCase.id,
                        ),
                    )
                    val result = cleanupEngine.clean(evaluationCase.raw, variant)
                    val exactMatch = result.cleanedText.trim() == evaluationCase.expected.trim()
                    if (exactMatch) exactMatches += 1
                    if (result.usedFallback) fallbackCount += 1
                    writer.appendLine(resultJson(evaluationCase, result, exactMatch).toString())
                    writer.flush()
                }
            }
        }

        val durationMs = nanosToMillis(SystemClock.elapsedRealtimeNanos() - startedAtNs)
        LocalFlowLog.info(
            "Cleanup evaluation completed: runs=$totalRuns, exact=$exactMatches, " +
                "fallbacks=$fallbackCount, durationMs=$durationMs, file=${resultFile.name}",
        )
        CleanupBatchSummary(
            resultFile = resultFile,
            totalRuns = totalRuns,
            exactMatches = exactMatches,
            fallbackCount = fallbackCount,
            durationMs = durationMs,
        )
    }

    private fun loadCases(): List<EvaluationCase> =
        appContext.assets.open(CORPUS_ASSET).bufferedReader().useLines { lines ->
            lines.filter(String::isNotBlank).map { line ->
                val json = JSONObject(line)
                EvaluationCase(
                    id = json.getString("id"),
                    raw = json.getString("raw"),
                    expected = json.getString("expected"),
                    categories = json.getJSONArray("categories").toStrings(),
                    mustPreserve = json.getJSONArray("must_preserve").toStrings(),
                )
            }.toList()
        }

    private fun resultJson(
        evaluationCase: EvaluationCase,
        result: CleanupResult,
        exactMatch: Boolean,
    ): JSONObject = JSONObject().apply {
        put("case_id", evaluationCase.id)
        put("model_name", result.modelName)
        put("quantization", result.quantization)
        put("prompt_variant", result.promptVariantId)
        put("raw", result.rawText)
        put("expected", evaluationCase.expected)
        put("categories", JSONArray(evaluationCase.categories))
        put("must_preserve", JSONArray(evaluationCase.mustPreserve))
        put("model_text", result.modelText)
        put("selected_text", result.cleanedText)
        put("exact_match", exactMatch)
        put("used_fallback", result.usedFallback)
        put("fallback_reason", result.fallbackReason ?: JSONObject.NULL)
        put(
            "timings",
            JSONObject().apply {
                put("ttft_ms", result.timeToFirstTokenMs ?: JSONObject.NULL)
                put("total_ms", result.totalLatencyMs)
            },
        )
        put("prompt_tokens", result.promptTokens ?: JSONObject.NULL)
        put("completion_tokens", result.completionTokens ?: JSONObject.NULL)
        put("tokens_per_second", result.tokensPerSecond ?: JSONObject.NULL)
        put("finish_reason", result.finishReason ?: JSONObject.NULL)
        put("max_output_tokens", result.maxOutputTokens)
        put("hit_output_token_limit", result.hitOutputTokenLimit)
    }

    private fun JSONArray.toStrings(): List<String> =
        List(length()) { index -> getString(index) }

    private data class EvaluationCase(
        val id: String,
        val raw: String,
        val expected: String,
        val categories: List<String>,
        val mustPreserve: List<String>,
    )

    private companion object {
        const val CORPUS_ASSET = "cleanup_cases.jsonl"
        const val RESULTS_DIRECTORY = "cleanup-evaluations"

        fun nanosToMillis(nanos: Long): Long = nanos.coerceAtLeast(0L) / 1_000_000L
    }
}
