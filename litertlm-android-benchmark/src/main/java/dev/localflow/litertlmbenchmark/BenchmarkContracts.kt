package dev.localflow.litertlmbenchmark

import org.json.JSONArray
import org.json.JSONObject

internal object S1LiteRtContract {
    const val MODEL_FILE_NAME = "s1-mini-block32-ctx4096.litertlm"
    const val MODEL_SIZE_BYTES = 436_596_864L
    const val MODEL_SHA256 =
        "8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403"
    const val CONTEXT_TOKENS = 4_096
    const val FIXED_PROMPT_TOKENS = 78
    const val PROMPT_PROFILE = "s1-mini-v1-publisher"
    const val SYSTEM_PROMPT =
        "You are a text normalizer for speech-to-text transcripts. The input begins with a control line specifying the styling, structure, and context settings; clean the transcript to match those settings and output only the cleaned text."
    const val CONTROL_LINE =
        "[Styling: semi-formal] [Structure: prose] [Context: general]"

    fun userText(rawText: String): String = "$CONTROL_LINE\n$rawText"

    fun renderPrompt(rawText: String): String =
        "<|im_start|>system\n$SYSTEM_PROMPT<|im_end|>\n" +
            "<|im_start|>user\n${userText(rawText)}<|im_end|>\n" +
            "<|im_start|>assistant\n<think>\n\n</think>\n\n"

    fun outputCap(rawTokenCount: Int): Int {
        require(rawTokenCount in 1..1_000) { "raw token count is out of range" }
        return ((13L * rawTokenCount + 9L) / 10L + 32L).toInt()
    }

    fun selectExactRenderedPrompt(
        expected: String,
        preface: String,
        renderedMessage: String,
    ): String = when {
        renderedMessage == expected -> renderedMessage
        preface + renderedMessage == expected -> preface + renderedMessage
        else -> error("LiteRT-LM rendered prompt differs from the frozen S1 contract")
    }
}

internal data class TranscriptCase(
    val caseId: String,
    val rawText: String,
    val categories: List<String>,
    val rawTokenCount: Int,
)

internal object TranscriptCaseParser {
    private val safeId = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    private val allowedFields = setOf("id", "raw", "categories", "raw_tokens")

    fun parseLine(line: String, lineNumber: Int): TranscriptCase {
        val json = runCatching { JSONObject(line) }.getOrElse {
            throw IllegalArgumentException("invalid cases line $lineNumber", it)
        }
        require(json.keys().asSequence().toSet() == allowedFields) {
            "cases line $lineNumber must contain only id, raw, categories, and raw_tokens"
        }
        val id = json.getString("id")
        val raw = json.getString("raw")
        val rawTokens = json.getInt("raw_tokens")
        val categoriesJson = json.getJSONArray("categories")
        val categories = List(categoriesJson.length()) { categoriesJson.getString(it) }
        require(safeId.matches(id)) { "invalid case id on line $lineNumber" }
        require(raw.isNotBlank()) { "empty transcript on line $lineNumber" }
        require(rawTokens in 1..1_000) { "invalid raw token count on line $lineNumber" }
        require(categories.all(String::isNotBlank)) { "empty category on line $lineNumber" }
        return TranscriptCase(id, raw, categories, rawTokens)
    }
}

internal const val PHASE_WARMUP = "warmup"
internal const val PHASE_MEASURED = "measured"

internal data class BenchmarkJob(
    val caseIndex: Int,
    val phase: String,
    val repeatIndex: Int,
)

internal fun buildJobOrder(
    caseCount: Int,
    warmupRuns: Int,
    measuredRepeats: Int,
): List<BenchmarkJob> {
    require(caseCount > 0)
    require(warmupRuns >= 0)
    require(measuredRepeats > 0)
    val measuredOrder = if (caseCount == 1) listOf(0) else (1 until caseCount).toList() + 0
    return buildList {
        repeat(warmupRuns) { add(BenchmarkJob(0, PHASE_WARMUP, it)) }
        repeat(measuredRepeats) { repeat ->
            measuredOrder.forEach { add(BenchmarkJob(it, PHASE_MEASURED, repeat)) }
        }
    }
}

internal fun categoriesJson(categories: List<String>): JSONArray = JSONArray(categories)
