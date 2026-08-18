package dev.localflow.dictation.stt.benchmark

import android.app.Activity
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.Process
import android.os.Trace
import android.view.WindowManager
import android.widget.TextView
import dev.localflow.dictation.IntegrationModels
import dev.localflow.dictation.LocalFlowLog
import dev.localflow.dictation.cleanup.CleanupPromptVariant
import dev.localflow.dictation.cleanup.SottoCleanupEngine
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.time.Instant
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject

/** Debug-only direct-text cleanup benchmark. Expected outputs never enter model context. */
class CleanupBenchmarkActivity : Activity() {
    private lateinit var status: TextView
    private val ioWorker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-cleanup-benchmark-io").apply { isDaemon = true }
    }
    private val uiJob = SupervisorJob()
    private val uiScope = CoroutineScope(uiJob + Dispatchers.Main.immediate)
    private val cleanupLazy = lazy {
        SottoCleanupEngine(
            context = applicationContext,
            modelFile = IntegrationModels.modelDirectory(applicationContext).resolve(modelFileName),
            expectedModelSha256 = modelSha256,
        )
    }
    private val cleanup by cleanupLazy

    private lateinit var benchmarkRoot: File
    private lateinit var runId: String
    private lateinit var modelFileName: String
    private lateinit var modelSha256: String
    private lateinit var partialResult: File
    private lateinit var finalResult: File
    private var measuredRepeats = DEFAULT_MEASURED_REPEATS
    private var warmupRuns = DEFAULT_WARMUP_RUNS
    private var modelLoadMs = 0L
    private var writer: BufferedWriter? = null
    private var benchmarkTraceActive = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        status = TextView(this).apply {
            textSize = 18f
            setPadding(48, 48, 48, 48)
            text = "Starting direct cleanup benchmark…"
        }
        setContentView(status)
        runCatching { configureRun() }
            .onSuccess { loadCasesAndModel() }
            .onFailure(::fail)
    }

    override fun onDestroy() {
        endBenchmarkTrace()
        runCatching { writer?.close() }
        if (cleanupLazy.isInitialized()) {
            val engine = cleanupLazy.value
            CoroutineScope(SupervisorJob() + Dispatchers.Default).launch {
                runCatching { engine.unload() }
            }
        }
        uiScope.cancel()
        ioWorker.shutdownNow()
        super.onDestroy()
    }

    private fun configureRun() {
        benchmarkRoot = File(requireNotNull(getExternalFilesDir(null)), BENCHMARK_DIRECTORY)
            .canonicalFile
        require(benchmarkRoot.isDirectory) { "Cleanup benchmark directory is missing" }
        runId = intent.getStringExtra(EXTRA_RUN_ID).orEmpty()
        require(SAFE_NAME.matches(runId)) { "Invalid or missing run_id" }
        modelFileName = intent.getStringExtra(EXTRA_MODEL_FILE_NAME).orEmpty()
        require(SAFE_GGUF_NAME.matches(modelFileName)) { "Invalid or missing model filename" }
        modelSha256 = intent.getStringExtra(EXTRA_MODEL_SHA256).orEmpty().lowercase()
        require(SHA256.matches(modelSha256)) { "Invalid or missing model SHA-256" }
        measuredRepeats = intent.getIntExtra(EXTRA_MEASURED_REPEATS, DEFAULT_MEASURED_REPEATS)
        warmupRuns = intent.getIntExtra(EXTRA_WARMUP_RUNS, DEFAULT_WARMUP_RUNS)
        require(measuredRepeats in 1..MAX_REPEATS) { "measured_repeats is out of range" }
        require(warmupRuns in 0..MAX_REPEATS) { "warmup_runs is out of range" }
        partialResult = childFile("results-$runId.jsonl.partial")
        finalResult = childFile("results-$runId.jsonl")
        require(!partialResult.exists() && !finalResult.exists()) {
            "Result already exists for run_id=$runId"
        }
    }

    private fun loadCasesAndModel() {
        ioWorker.execute {
            runCatching { readCases(childFile(CASES_FILE)) }
                .onSuccess { cases -> runOnUiThread { loadModel(cases) } }
                .onFailure { error -> runOnUiThread { fail(error) } }
        }
    }

    private fun loadModel(cases: List<CleanupCase>) {
        status.text = "Loading staged cleanup model…"
        uiScope.launch {
            val startedAtNs = android.os.SystemClock.elapsedRealtimeNanos()
            runCatching { cleanup.load() }
                .onSuccess {
                    modelLoadMs = elapsedMs(startedAtNs)
                    runCatching { writer = BufferedWriter(FileWriter(partialResult, false)) }
                        .onSuccess { startBenchmark(cases) }
                        .onFailure(::fail)
                }
                .onFailure(::fail)
        }
    }

    private fun startBenchmark(cases: List<CleanupCase>) {
        Trace.beginAsyncSection(TRACE_SECTION_NAME, TRACE_COOKIE)
        benchmarkTraceActive = true
        val jobs = buildList {
            repeat(warmupRuns) { repeatIndex ->
                add(CleanupJob(cases.first(), PHASE_WARMUP, repeatIndex))
            }
            cases.forEach { case ->
                repeat(measuredRepeats) { repeatIndex ->
                    add(CleanupJob(case, PHASE_MEASURED, repeatIndex))
                }
            }
        }
        runJob(jobs, 0)
    }

    private fun runJob(jobs: List<CleanupJob>, index: Int) {
        if (index >= jobs.size) {
            finishSuccessfully(jobs.size)
            return
        }
        val job = jobs[index]
        status.text = "${job.phase}: ${job.case.caseId} (${index + 1}/${jobs.size})"
        uiScope.launch {
            runCatching {
                val traceInference = job.phase == PHASE_MEASURED
                if (traceInference) Trace.beginAsyncSection(TRACE_INFERENCE_SECTION_NAME, index)
                val cpuStartedAtMs = Process.getElapsedCpuTime()
                val result = try {
                    cleanup.clean(job.case.rawText, CleanupPromptVariant.SOTTO_NATIVE)
                } finally {
                    if (traceInference) Trace.endAsyncSection(TRACE_INFERENCE_SECTION_NAME, index)
                }
                val processCpuMs =
                    (Process.getElapsedCpuTime() - cpuStartedAtMs).coerceAtLeast(0L)
                JSONObject()
                    .put("schema_version", SCHEMA_VERSION)
                    .put("run_id", runId)
                    .put("phase", job.phase)
                    .put("repeat_index", job.repeatIndex)
                    .put("case_id", job.case.caseId)
                    .put("categories", JSONArray(job.case.categories))
                    .put("raw_text", job.case.rawText)
                    .put("model_input", result.modelInputText)
                    .put("removed_fillers", JSONArray(result.removedFillers))
                    .put("raw_model_output", result.modelText)
                    .put("guarded_output", result.cleanedText)
                    .put("used_fallback", result.usedFallback)
                    .put("fallback_reason", result.fallbackReason ?: JSONObject.NULL)
                    .put("model_file", modelFileName)
                    .put("model_sha256", modelSha256)
                    .put("model_load_ms", modelLoadMs)
                    .put("cleanup_ttft_ms", result.timeToFirstTokenMs ?: JSONObject.NULL)
                    .put("cleanup_total_ms", result.totalLatencyMs)
                    .put("process_cpu_ms", processCpuMs)
                    .put("prompt_tokens", result.promptTokens ?: JSONObject.NULL)
                    .put("completion_tokens", result.completionTokens ?: JSONObject.NULL)
                    .put("tokens_per_second", result.tokensPerSecond ?: JSONObject.NULL)
                    .put("finish_reason", result.finishReason ?: JSONObject.NULL)
                    .put("process_pss_kb_after_inference", Debug.getPss())
                    .put("native_heap_bytes_after_inference", Debug.getNativeHeapAllocatedSize())
                    .put(
                        "thermal_status_after_inference",
                        getSystemService(PowerManager::class.java).currentThermalStatus,
                    )
                    .put("created_at_utc", Instant.now().toString())
            }.onSuccess { record ->
                ioWorker.execute {
                    runCatching {
                        requireNotNull(writer).apply {
                            write(record.toString())
                            newLine()
                            flush()
                        }
                    }.onSuccess { runOnUiThread { runJob(jobs, index + 1) } }
                        .onFailure { error -> runOnUiThread { fail(error) } }
                }
            }.onFailure(::fail)
        }
    }

    private fun finishSuccessfully(jobCount: Int) {
        runCatching {
            requireNotNull(writer).close()
            writer = null
            require(partialResult.renameTo(finalResult)) { "Could not finalize result file" }
            endBenchmarkTrace()
        }.onSuccess {
            status.text = "Finished $jobCount cleanup runs\n${finalResult.name}"
            LocalFlowLog.info("Cleanup benchmark finished: runs=$jobCount, result=${finalResult.name}")
            finish()
        }.onFailure(::fail)
    }

    private fun fail(error: Throwable) {
        endBenchmarkTrace()
        LocalFlowLog.error("Cleanup benchmark failed", error)
        status.text = "Cleanup benchmark failed: ${error.message ?: error.javaClass.simpleName}"
        runCatching { writer?.close() }
        writer = null
        if (::benchmarkRoot.isInitialized && ::runId.isInitialized) {
            runCatching {
                childFile("error-$runId.json").writeText(
                    JSONObject()
                        .put("run_id", runId)
                        .put("error_type", error.javaClass.name)
                        .put("error", error.message ?: "Unknown error")
                        .put("created_at_utc", Instant.now().toString())
                        .toString(2),
                )
            }
        }
    }

    private fun readCases(file: File): List<CleanupCase> {
        require(file.isFile) { "Missing $CASES_FILE" }
        val cases = file.useLines { lines ->
            lines.filter(String::isNotBlank).mapIndexed { index, line ->
                val json = runCatching { JSONObject(line) }.getOrElse {
                    throw IllegalArgumentException("Invalid cases line ${index + 1}", it)
                }
                val caseId = json.getString("id")
                val rawText = json.getString("raw")
                val categoriesJson = json.getJSONArray("categories")
                val categories = List(categoriesJson.length()) { categoriesJson.getString(it) }
                require(SAFE_NAME.matches(caseId)) { "Invalid case id on line ${index + 1}" }
                require(rawText.isNotBlank()) { "Empty raw text on line ${index + 1}" }
                CleanupCase(caseId, rawText, categories)
            }.toList()
        }
        require(cases.isNotEmpty()) { "Cases file is empty" }
        require(cases.map(CleanupCase::caseId).distinct().size == cases.size) {
            "Cases file contains duplicate IDs"
        }
        return cases
    }

    private fun childFile(relativePath: String): File {
        val file = File(benchmarkRoot, relativePath).canonicalFile
        require(file.path.startsWith(benchmarkRoot.path + File.separator)) {
            "Path escapes cleanup benchmark directory"
        }
        return file
    }

    private fun elapsedMs(startedAtNs: Long): Long =
        (android.os.SystemClock.elapsedRealtimeNanos() - startedAtNs)
            .coerceAtLeast(0L) / 1_000_000L

    private fun endBenchmarkTrace() {
        if (benchmarkTraceActive) {
            Trace.endAsyncSection(TRACE_SECTION_NAME, TRACE_COOKIE)
            benchmarkTraceActive = false
        }
    }

    private data class CleanupCase(
        val caseId: String,
        val rawText: String,
        val categories: List<String>,
    )

    private data class CleanupJob(
        val case: CleanupCase,
        val phase: String,
        val repeatIndex: Int,
    )

    private companion object {
        const val EXTRA_RUN_ID = "run_id"
        const val EXTRA_MODEL_FILE_NAME = "model_file_name"
        const val EXTRA_MODEL_SHA256 = "model_sha256"
        const val EXTRA_MEASURED_REPEATS = "measured_repeats"
        const val EXTRA_WARMUP_RUNS = "warmup_runs"
        const val BENCHMARK_DIRECTORY = "cleanup-eval"
        const val CASES_FILE = "cases.jsonl"
        const val DEFAULT_MEASURED_REPEATS = 3
        const val DEFAULT_WARMUP_RUNS = 1
        const val MAX_REPEATS = 10
        const val SCHEMA_VERSION = 1
        const val PHASE_WARMUP = "warmup"
        const val PHASE_MEASURED = "measured"
        const val TRACE_SECTION_NAME = "localflow_cleanup_benchmark"
        const val TRACE_INFERENCE_SECTION_NAME = "localflow_cleanup_inference"
        const val TRACE_COOKIE = 1
        val SAFE_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        val SAFE_GGUF_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}\\.gguf")
        val SHA256 = Regex("[0-9a-f]{64}")
    }
}
