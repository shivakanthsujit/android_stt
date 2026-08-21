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
import dev.localflow.dictation.cleanup.CleanupLoadResult
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

internal const val CLEANUP_BENCHMARK_PHASE_WARMUP = "warmup"
internal const val CLEANUP_BENCHMARK_PHASE_MEASURED = "measured"

internal data class CleanupBenchmarkJobOrderEntry(
    val caseIndex: Int,
    val phase: String,
    val repeatIndex: Int,
)

internal fun buildCleanupBenchmarkJobOrder(
    caseCount: Int,
    warmupRuns: Int,
    measuredRepeats: Int,
): List<CleanupBenchmarkJobOrderEntry> {
    require(caseCount > 0) { "caseCount must be positive" }
    require(warmupRuns >= 0) { "warmupRuns must be non-negative" }
    require(measuredRepeats > 0) { "measuredRepeats must be positive" }

    val measuredCaseOrder = if (caseCount > 1) {
        (1 until caseCount).toList() + 0
    } else {
        listOf(0)
    }
    return buildList {
        repeat(warmupRuns) { repeatIndex ->
            add(
                CleanupBenchmarkJobOrderEntry(
                    caseIndex = 0,
                    phase = CLEANUP_BENCHMARK_PHASE_WARMUP,
                    repeatIndex = repeatIndex,
                ),
            )
        }
        repeat(measuredRepeats) { repeatIndex ->
            measuredCaseOrder.forEach { caseIndex ->
                add(
                    CleanupBenchmarkJobOrderEntry(
                        caseIndex = caseIndex,
                        phase = CLEANUP_BENCHMARK_PHASE_MEASURED,
                        repeatIndex = repeatIndex,
                    ),
                )
            }
        }
    }
}

internal fun requireCleanupBenchmarkCacheSeparation(
    caseCount: Int,
    cacheMaxEntries: Int,
) {
    require(caseCount > cacheMaxEntries) {
        "Cache benchmarks require more unique cases than cache entries: " +
            "cases=$caseCount, entries=$cacheMaxEntries"
    }
}

/** Debug-only direct-text cleanup benchmark. Expected outputs never enter model context. */
class CleanupBenchmarkActivity : Activity() {
    private lateinit var status: TextView
    private val ioWorker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-cleanup-benchmark-io").apply { isDaemon = true }
    }
    private val uiJob = SupervisorJob()
    private val uiScope = CoroutineScope(uiJob + Dispatchers.Main.immediate)
    private val sottoCleanupLazy = lazy {
        SottoCleanupEngine(
            context = applicationContext,
            modelFile = IntegrationModels.modelDirectory(applicationContext).resolve(modelFileName),
            expectedModelSha256 = modelSha256,
        )
    }
    private val s1MiniCleanupLazy = lazy {
        S1MiniPixelBenchmarkEngine(
            context = applicationContext,
            modelFile = File(filesDir, MODELS_DIRECTORY).resolve(modelFileName),
            expectedModelSha256 = modelSha256,
            requestedConfig = s1MiniBenchmarkConfig,
        )
    }

    private lateinit var benchmarkRoot: File
    private lateinit var runId: String
    private lateinit var modelFileName: String
    private lateinit var modelSha256: String
    private lateinit var engineProfile: String
    private lateinit var partialResult: File
    private lateinit var finalResult: File
    private var measuredRepeats = DEFAULT_MEASURED_REPEATS
    private var warmupRuns = DEFAULT_WARMUP_RUNS
    private lateinit var s1MiniBenchmarkConfig: S1MiniPixelBenchmarkEngine.Config
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
        if (sottoCleanupLazy.isInitialized() || s1MiniCleanupLazy.isInitialized()) {
            CoroutineScope(SupervisorJob() + Dispatchers.Default).launch {
                runCatching { unloadEngine() }
            }
        }
        uiScope.cancel()
        ioWorker.shutdownNow()
        super.onDestroy()
    }

    private fun configureRun() {
        engineProfile = intent.getStringExtra(EXTRA_ENGINE_PROFILE) ?: ENGINE_PROFILE_SOTTO
        require(engineProfile == ENGINE_PROFILE_SOTTO || engineProfile == ENGINE_PROFILE_S1_MINI) {
            "Unsupported cleanup benchmark engine profile: $engineProfile"
        }
        val benchmarkStorage = if (engineProfile == ENGINE_PROFILE_S1_MINI) {
            filesDir
        } else {
            requireNotNull(getExternalFilesDir(null))
        }
        benchmarkRoot = File(benchmarkStorage, BENCHMARK_DIRECTORY).canonicalFile
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
        s1MiniBenchmarkConfig = if (engineProfile == ENGINE_PROFILE_S1_MINI) {
            val requestedCpuThreads = intent.getIntExtra(EXTRA_LEAP_CPU_THREADS, 0)
            val requestedCacheMemoryMb = intent.getIntExtra(EXTRA_LEAP_CACHE_MEMORY_MB, 0)
            S1MiniPixelBenchmarkEngine.Config(
                contextTokens = intent.getIntExtra(
                    EXTRA_LEAP_CONTEXT_TOKENS,
                    S1MiniPixelBenchmarkEngine.MODEL_CONTEXT_TOKENS,
                ),
                cpuThreads = requestedCpuThreads.takeUnless { it == 0 },
                cacheMemoryMb = requestedCacheMemoryMb.takeUnless { it == 0 },
            )
        } else {
            S1MiniPixelBenchmarkEngine.Config()
        }
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
            runCatching { loadEngine() }
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
        if (s1MiniBenchmarkConfig.cacheEnabled) {
            requireCleanupBenchmarkCacheSeparation(
                caseCount = cases.size,
                cacheMaxEntries = s1MiniBenchmarkConfig.cacheMaxEntries,
            )
        }
        Trace.beginAsyncSection(TRACE_SECTION_NAME, TRACE_COOKIE)
        benchmarkTraceActive = true
        val jobs = buildCleanupBenchmarkJobOrder(
            caseCount = cases.size,
            warmupRuns = warmupRuns,
            measuredRepeats = measuredRepeats,
        ).map { entry ->
            CleanupJob(
                case = cases[entry.caseIndex],
                phase = entry.phase,
                repeatIndex = entry.repeatIndex,
            )
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
                val traceInference = job.phase == CLEANUP_BENCHMARK_PHASE_MEASURED
                if (traceInference) Trace.beginAsyncSection(TRACE_INFERENCE_SECTION_NAME, index)
                val cpuStartedAtMs = Process.getElapsedCpuTime()
                val benchmarkResult = try {
                    clean(job.case)
                } finally {
                    if (traceInference) Trace.endAsyncSection(TRACE_INFERENCE_SECTION_NAME, index)
                }
                val result = benchmarkResult.cleanupResult
                val processCpuMs =
                    (Process.getElapsedCpuTime() - cpuStartedAtMs).coerceAtLeast(0L)
                val record = JSONObject()
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
                    .put("engine_profile", engineProfile)
                    .put("requested_max_output_tokens", job.case.maxOutputTokens ?: JSONObject.NULL)
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
                benchmarkResult.s1Metadata?.let { metadata ->
                    val config = metadata.config
                    record
                        .put("context_size", config.contextTokens)
                        .put("cpu_threads_mode", config.cpuThreadsMode)
                        .put("cpu_threads", config.cpuThreads ?: JSONObject.NULL)
                        .put("resolved_cpu_threads", metadata.resolvedCpuThreads)
                        .put("cache_enabled", config.cacheEnabled)
                        .put("cache_max_memory_bytes", config.cacheMaxMemoryBytes)
                        .put("cache_max_entries", config.cacheMaxEntries)
                        .put("cache_disk_disabled", config.cacheDiskDisabled)
                        .put(
                            "cache_requested_max_disk_entries",
                            config.cacheMaxDiskEntries,
                        )
                        .put("mmap_enabled", true)
                        .put("fixed_prompt_tokens", metadata.fixedPromptTokens)
                        .put(
                            "cached_prompt_tokens",
                            metadata.cachedPromptTokens ?: JSONObject.NULL,
                        )
                }
                record
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
                val maxOutputTokens = if (json.has("max_new_tokens")) {
                    json.getInt("max_new_tokens").also {
                        require(it in 1..S1MiniPixelBenchmarkEngine.MAX_ALLOWED_OUTPUT_TOKENS) {
                            "Invalid max_new_tokens on line ${index + 1}"
                        }
                    }
                } else {
                    null
                }
                require(SAFE_NAME.matches(caseId)) { "Invalid case id on line ${index + 1}" }
                require(rawText.isNotBlank()) { "Empty raw text on line ${index + 1}" }
                CleanupCase(caseId, rawText, categories, maxOutputTokens)
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

    private suspend fun loadEngine(): CleanupLoadResult =
        when (engineProfile) {
            ENGINE_PROFILE_SOTTO -> sottoCleanupLazy.value.load()
            ENGINE_PROFILE_S1_MINI -> s1MiniCleanupLazy.value.load()
            else -> error("Unsupported engine profile: $engineProfile")
        }

    private suspend fun clean(case: CleanupCase): BenchmarkCleanupResult =
        when (engineProfile) {
            ENGINE_PROFILE_SOTTO ->
                BenchmarkCleanupResult(
                    cleanupResult = sottoCleanupLazy.value.clean(
                        case.rawText,
                        CleanupPromptVariant.SOTTO_NATIVE,
                    ),
                )
            ENGINE_PROFILE_S1_MINI -> {
                val result = s1MiniCleanupLazy.value.clean(
                    text = case.rawText,
                    maxOutputTokens = requireNotNull(case.maxOutputTokens) {
                        "S1-mini case ${case.caseId} is missing max_new_tokens"
                    },
                )
                BenchmarkCleanupResult(
                    cleanupResult = result.cleanupResult,
                    s1Metadata = S1BenchmarkMetadata(
                        config = result.requestedConfig,
                        fixedPromptTokens = result.fixedPromptTokens,
                        cachedPromptTokens = result.cachedPromptTokens,
                        resolvedCpuThreads = result.resolvedCpuThreads,
                    ),
                )
            }
            else -> error("Unsupported engine profile: $engineProfile")
        }

    private suspend fun unloadEngine() {
        if (sottoCleanupLazy.isInitialized()) sottoCleanupLazy.value.unload()
        if (s1MiniCleanupLazy.isInitialized()) s1MiniCleanupLazy.value.unload()
    }

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
        val maxOutputTokens: Int?,
    )

    private data class CleanupJob(
        val case: CleanupCase,
        val phase: String,
        val repeatIndex: Int,
    )

    private data class BenchmarkCleanupResult(
        val cleanupResult: dev.localflow.dictation.cleanup.CleanupResult,
        val s1Metadata: S1BenchmarkMetadata? = null,
    )

    private data class S1BenchmarkMetadata(
        val config: S1MiniPixelBenchmarkEngine.Config,
        val fixedPromptTokens: Int,
        val cachedPromptTokens: Long?,
        val resolvedCpuThreads: Int,
    )

    private companion object {
        const val EXTRA_RUN_ID = "run_id"
        const val EXTRA_MODEL_FILE_NAME = "model_file_name"
        const val EXTRA_MODEL_SHA256 = "model_sha256"
        const val EXTRA_ENGINE_PROFILE = "engine_profile"
        const val EXTRA_MEASURED_REPEATS = "measured_repeats"
        const val EXTRA_WARMUP_RUNS = "warmup_runs"
        const val EXTRA_LEAP_CPU_THREADS = "leap_cpu_threads"
        const val EXTRA_LEAP_CONTEXT_TOKENS = "leap_context_tokens"
        const val EXTRA_LEAP_CACHE_MEMORY_MB = "leap_cache_memory_mb"
        const val BENCHMARK_DIRECTORY = "cleanup-eval"
        const val MODELS_DIRECTORY = "models"
        const val CASES_FILE = "cases.jsonl"
        const val DEFAULT_MEASURED_REPEATS = 3
        const val DEFAULT_WARMUP_RUNS = 1
        const val MAX_REPEATS = 10
        const val ENGINE_PROFILE_SOTTO = "sotto-native"
        const val ENGINE_PROFILE_S1_MINI = "s1-mini-v1-publisher"
        const val SCHEMA_VERSION = 1
        const val TRACE_SECTION_NAME = "localflow_cleanup_benchmark"
        const val TRACE_INFERENCE_SECTION_NAME = "localflow_cleanup_inference"
        const val TRACE_COOKIE = 1
        val SAFE_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        val SAFE_GGUF_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}\\.gguf")
        val SHA256 = Regex("[0-9a-f]{64}")
    }
}
