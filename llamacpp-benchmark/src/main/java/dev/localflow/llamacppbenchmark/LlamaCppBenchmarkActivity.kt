package dev.localflow.llamacppbenchmark

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.os.Trace
import android.view.WindowManager
import android.widget.TextView
import java.io.BufferedWriter
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import org.json.JSONArray
import org.json.JSONObject

/** Isolated, transcript-only S1-mini benchmark. No expected cleanup output is accepted or read. */
class LlamaCppBenchmarkActivity : Activity() {
    private lateinit var statusView: TextView
    private val worker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "s1-llamacpp-benchmark").apply { isDaemon = true }
    }
    private val nativeLlama = NativeLlama()
    private var writer: BufferedWriter? = null
    private var benchmarkTraceActive = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        statusView = TextView(this).apply {
            textSize = 18f
            setPadding(48, 48, 48, 48)
            text = "Preparing isolated llama.cpp benchmark…"
        }
        setContentView(statusView)

        val configured = runCatching { configureRun() }
        configured.onSuccess { run -> worker.execute { executeRun(run) } }
            .onFailure(::fail)
    }

    override fun onDestroy() {
        worker.shutdown()
        super.onDestroy()
    }

    private fun configureRun(): ConfiguredRun {
        val runId = intent.getStringExtra(EXTRA_RUN_ID).orEmpty()
        require(SAFE_NAME.matches(runId)) { "Invalid or missing run_id" }
        val modelFileName = intent.getStringExtra(EXTRA_MODEL_FILE_NAME).orEmpty()
        require(modelFileName == S1Contract.MODEL_FILE_NAME) { "Unexpected model filename" }
        val requestedSha = intent.getStringExtra(EXTRA_MODEL_SHA256).orEmpty().lowercase()
        require(requestedSha == S1Contract.MODEL_SHA256) { "Unexpected model SHA-256" }

        val measuredRepeats =
            intent.getIntExtra(EXTRA_MEASURED_REPEATS, DEFAULT_MEASURED_REPEATS)
        val warmupRuns = intent.getIntExtra(EXTRA_WARMUP_RUNS, DEFAULT_WARMUP_RUNS)
        require(measuredRepeats in 1..MAX_REPEATS) { "measured_repeats is out of range" }
        require(warmupRuns in 0..MAX_REPEATS) { "warmup_runs is out of range" }

        val config = BenchmarkConfig(
            contextTokens = intent.getIntExtra(EXTRA_CONTEXT_TOKENS, 2_560),
            generationThreads = intent.getIntExtra(EXTRA_GENERATION_THREADS, 2),
            batchThreads = intent.getIntExtra(EXTRA_BATCH_THREADS, 2),
            batchSize = intent.getIntExtra(EXTRA_BATCH_SIZE, 512),
            microBatchSize = intent.getIntExtra(EXTRA_MICRO_BATCH_SIZE, 512),
            useMmap = intent.getBooleanExtra(EXTRA_USE_MMAP, true),
            flashAttention = intent.getBooleanExtra(EXTRA_FLASH_ATTENTION, false),
            gpuLayers = intent.getIntExtra(EXTRA_GPU_LAYERS, 0),
        )

        val modelRoot = File(filesDir, MODEL_DIRECTORY).canonicalFile
        val benchmarkRoot = File(filesDir, BENCHMARK_DIRECTORY).canonicalFile
        require(modelRoot.isDirectory) { "Model staging directory is missing" }
        require(benchmarkRoot.isDirectory) { "Benchmark staging directory is missing" }
        val modelFile = childFile(modelRoot, modelFileName)
        val casesFile = childFile(benchmarkRoot, CASES_FILE_NAME)
        val partialResult = childFile(benchmarkRoot, "results-$runId.jsonl.partial")
        val finalResult = childFile(benchmarkRoot, "results-$runId.jsonl")
        val errorResult = childFile(benchmarkRoot, "error-$runId.json")
        require(!partialResult.exists() && !finalResult.exists() && !errorResult.exists()) {
            "Run output already exists"
        }
        return ConfiguredRun(
            runId = runId,
            modelFile = modelFile,
            casesFile = casesFile,
            partialResult = partialResult,
            finalResult = finalResult,
            errorResult = errorResult,
            measuredRepeats = measuredRepeats,
            warmupRuns = warmupRuns,
            config = config,
        )
    }

    private fun executeRun(run: ConfiguredRun) {
        runCatching {
            validateModelFile(run.modelFile)
            val cases = readCases(run.casesFile)
            updateStatus("Loading pinned S1-mini GGUF…")
            val loadStartedAtNs = SystemClock.elapsedRealtimeNanos()
            val modelInfo = nativeLlama.loadModel(run.modelFile.path, run.config)
            val modelLoadMs = elapsedMs(loadStartedAtNs)
            NativeResultContract.validateModelInfo(modelInfo, run.config)
            val appBuildInfo = appBuildInfo()

            writer = BufferedWriter(
                OutputStreamWriter(
                    FileOutputStream(run.partialResult, false),
                    StandardCharsets.UTF_8,
                ),
            )
            val jobs = buildBenchmarkJobOrder(
                caseCount = cases.size,
                warmupRuns = run.warmupRuns,
                measuredRepeats = run.measuredRepeats,
            )
            Trace.beginAsyncSection(TRACE_BENCHMARK, TRACE_BENCHMARK_COOKIE)
            benchmarkTraceActive = true
            jobs.forEachIndexed { index, job ->
                val case = cases[job.caseIndex]
                updateStatus("${job.phase}: ${case.caseId} (${index + 1}/${jobs.size})")
                nativeLlama.resetContext()
                val preflight = NativeResultContract.validateTokenization(
                    nativeLlama.tokenize(case.rawText),
                    case.rawText,
                )
                val maxOutputTokens = S1Contract.outputCap(preflight.rawTokenCount)
                require(preflight.promptTokenCount + maxOutputTokens <= run.config.contextTokens) {
                    "${case.caseId}: prompt plus output cap exceeds selected context"
                }

                val traceMeasured = job.phase == PHASE_MEASURED
                if (traceMeasured) Trace.beginAsyncSection(TRACE_INFERENCE, index)
                val cpuStartedAtMs = Process.getElapsedCpuTime()
                val generation = try {
                    nativeLlama.generate(case.rawText, maxOutputTokens)
                } finally {
                    if (traceMeasured) Trace.endAsyncSection(TRACE_INFERENCE, index)
                }
                val processCpuMs =
                    (Process.getElapsedCpuTime() - cpuStartedAtMs).coerceAtLeast(0L)
                NativeResultContract.validateGeneration(
                    generation,
                    preflight,
                    case.rawText,
                    maxOutputTokens,
                )
                val record = buildBenchmarkRecord(
                    runId = run.runId,
                    job = job,
                    case = case,
                    maxOutputTokens = maxOutputTokens,
                    modelSha256 = S1Contract.MODEL_SHA256,
                    requestedConfig = run.config.toJson(),
                    nativeModelInfo = modelInfo,
                    appBuildInfo = appBuildInfo,
                    nativeGeneration = generation,
                    hostMetrics = HostMetrics(
                        processCpuMs = processCpuMs,
                        processPssKb = Debug.getPss(),
                        nativeHeapBytes = Debug.getNativeHeapAllocatedSize(),
                        thermalStatus =
                            getSystemService(PowerManager::class.java).currentThermalStatus,
                    ),
                    modelLoadMs = modelLoadMs,
                    createdAtUtc = Instant.now().toString(),
                )
                requireNotNull(writer).apply {
                    write(record.toString())
                    newLine()
                    flush()
                }
            }
            finishSuccessfully(run, jobs.size)
        }.onFailure { error -> failRun(run, error) }
        endBenchmarkTrace()
        runCatching { writer?.close() }
        writer = null
        runCatching { nativeLlama.close() }
    }

    private fun finishSuccessfully(run: ConfiguredRun, jobCount: Int) {
        requireNotNull(writer).close()
        writer = null
        require(run.partialResult.renameTo(run.finalResult)) { "Could not finalize result file" }
        endBenchmarkTrace()
        runOnUiThread {
            statusView.text = "Finished $jobCount runs\n${run.finalResult.name}"
            finish()
        }
    }

    private fun failRun(run: ConfiguredRun, error: Throwable) {
        endBenchmarkTrace()
        runCatching { writer?.close() }
        writer = null
        runCatching {
            run.errorResult.writeText(
                JSONObject()
                    .put("run_id", run.runId)
                    .put("error_type", error.javaClass.name)
                    .put("error", error.message ?: "Unknown error")
                    .put("created_at_utc", Instant.now().toString())
                    .toString(2),
            )
        }
        fail(error)
    }

    private fun fail(error: Throwable) {
        runOnUiThread {
            statusView.text =
                "llama.cpp benchmark failed: ${error.message ?: error.javaClass.simpleName}"
        }
    }

    private fun updateStatus(value: String) {
        runOnUiThread { statusView.text = value }
    }

    private fun readCases(file: File): List<TranscriptCase> {
        require(file.isFile) { "Missing transcript-only cases file" }
        val cases = file.useLines { lines ->
            lines.filter(String::isNotBlank)
                .mapIndexed { index, line -> TranscriptCaseParser.parseLine(line, index + 1) }
                .toList()
        }
        require(cases.isNotEmpty()) { "Cases file is empty" }
        require(cases.map(TranscriptCase::caseId).distinct().size == cases.size) {
            "Cases file contains duplicate IDs"
        }
        return cases
    }

    private fun validateModelFile(file: File) {
        require(file.isFile) { "Pinned model is missing" }
        require(file.name == S1Contract.MODEL_FILE_NAME) { "Pinned model filename changed" }
        require(file.length() == S1Contract.MODEL_SIZE_BYTES) {
            "Pinned model size mismatch: ${file.length()}"
        }
        val digest = MessageDigest.getInstance("SHA-256")
        FileInputStream(file).use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        val actualSha = digest.digest().joinToString("") { byte -> "%02x".format(byte) }
        require(actualSha == S1Contract.MODEL_SHA256) { "Pinned model SHA-256 mismatch" }
    }

    private fun appBuildInfo(): JSONObject = JSONObject()
        .put("application_id", BuildConfig.APPLICATION_ID)
        .put("version_name", BuildConfig.VERSION_NAME)
        .put("version_code", BuildConfig.VERSION_CODE)
        .put("build_type", BuildConfig.BUILD_TYPE)
        .put("llama_cpp_revision", BuildConfig.LLAMA_CPP_REVISION)
        .put("ndk_version", BuildConfig.PINNED_NDK_VERSION)
        .put("cmake_version", BuildConfig.PINNED_CMAKE_VERSION)
        .put("device", Build.DEVICE)
        .put("model", Build.MODEL)
        .put("manufacturer", Build.MANUFACTURER)
        .put("sdk_int", Build.VERSION.SDK_INT)
        .put("supported_abis", JSONArray(Build.SUPPORTED_ABIS.toList()))

    private fun childFile(root: File, relativePath: String): File {
        val file = File(root, relativePath).canonicalFile
        require(file.path.startsWith(root.path + File.separator)) { "Path escapes staging root" }
        return file
    }

    private fun elapsedMs(startedAtNs: Long): Long =
        (SystemClock.elapsedRealtimeNanos() - startedAtNs).coerceAtLeast(0L) / 1_000_000L

    private fun endBenchmarkTrace() {
        if (benchmarkTraceActive) {
            Trace.endAsyncSection(TRACE_BENCHMARK, TRACE_BENCHMARK_COOKIE)
            benchmarkTraceActive = false
        }
    }

    private data class ConfiguredRun(
        val runId: String,
        val modelFile: File,
        val casesFile: File,
        val partialResult: File,
        val finalResult: File,
        val errorResult: File,
        val measuredRepeats: Int,
        val warmupRuns: Int,
        val config: BenchmarkConfig,
    )

    private companion object {
        const val EXTRA_RUN_ID = "run_id"
        const val EXTRA_MODEL_FILE_NAME = "model_file_name"
        const val EXTRA_MODEL_SHA256 = "model_sha256"
        const val EXTRA_MEASURED_REPEATS = "measured_repeats"
        const val EXTRA_WARMUP_RUNS = "warmup_runs"
        const val EXTRA_CONTEXT_TOKENS = "context_tokens"
        const val EXTRA_GENERATION_THREADS = "generation_threads"
        const val EXTRA_BATCH_THREADS = "batch_threads"
        const val EXTRA_BATCH_SIZE = "batch_size"
        const val EXTRA_MICRO_BATCH_SIZE = "micro_batch_size"
        const val EXTRA_USE_MMAP = "use_mmap"
        const val EXTRA_FLASH_ATTENTION = "flash_attention"
        const val EXTRA_GPU_LAYERS = "gpu_layers"
        const val MODEL_DIRECTORY = "models"
        const val BENCHMARK_DIRECTORY = "benchmark"
        const val CASES_FILE_NAME = "cases.jsonl"
        const val DEFAULT_MEASURED_REPEATS = 3
        const val DEFAULT_WARMUP_RUNS = 1
        const val MAX_REPEATS = 10
        const val TRACE_BENCHMARK = "localflow_llamacpp_benchmark"
        const val TRACE_INFERENCE = "localflow_llamacpp_inference"
        const val TRACE_BENCHMARK_COOKIE = 1
        val SAFE_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    }
}
