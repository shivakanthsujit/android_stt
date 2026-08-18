package dev.localflow.dictation.stt.benchmark

import android.app.Activity
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.SystemClock
import android.os.Trace
import android.view.WindowManager
import android.widget.TextView
import dev.localflow.dictation.LocalFlowLog
import dev.localflow.dictation.stt.FileSttBenchmarkResult
import dev.localflow.dictation.stt.FileSttBenchmarkEngine
import dev.localflow.dictation.stt.MoonshineSttEngine
import dev.localflow.dictation.stt.SpeechToTextEngine
import org.json.JSONObject
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

/** Debug-only, ADB-driven, file-fed STT benchmark. No microphone is opened. */
class SttBenchmarkActivity : Activity() {
    private lateinit var status: TextView
    private val ioWorker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-stt-benchmark-io").apply { isDaemon = true }
    }
    private val engineLazy = lazy {
        when (intent.getStringExtra(EXTRA_ENGINE).orEmpty().ifBlank { ENGINE_MOONSHINE }) {
            ENGINE_MOONSHINE -> {
                val moonshine = MoonshineSttEngine(
                    context = applicationContext,
                    onProgress = { fraction, _ ->
                        status.text = "Preparing Moonshine model: ${(fraction * 100).toInt()}%"
                    },
                    onStateChanged = {},
                    onError = ::fail,
                )
                BenchmarkEngine(moonshine, moonshine)
            }

            ENGINE_PARAKEET -> {
                val modelPath = intent.getStringExtra(EXTRA_MODEL_FILE).orEmpty()
                require(SAFE_MODEL_PATH.matches(modelPath)) { "Invalid or missing model_file" }
                val variant = intent.getStringExtra(EXTRA_MODEL_VARIANT).orEmpty()
                require(SAFE_NAME.matches(variant)) { "Invalid or missing model_variant" }
                val parakeet = ParakeetSttEngine(childFile(modelPath), variant)
                BenchmarkEngine(parakeet, parakeet)
            }

            else -> error("Unsupported benchmark engine")
        }
    }
    private val engine by engineLazy

    private lateinit var benchmarkRoot: File
    private lateinit var runId: String
    private lateinit var partialResult: File
    private lateinit var finalResult: File
    private var writer: BufferedWriter? = null
    private var modelLoadDurationMs = 0.0
    private var measuredRepeats = DEFAULT_MEASURED_REPEATS
    private var warmupRuns = DEFAULT_WARMUP_RUNS
    private var benchmarkTraceActive = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        status = TextView(this).apply {
            textSize = 18f
            setPadding(48, 48, 48, 48)
            text = "Starting file-fed STT benchmark…"
        }
        setContentView(status)

        runCatching { configureRun() }
            .onSuccess { loadManifestAndModel() }
            .onFailure(::fail)
    }

    override fun onDestroy() {
        runCatching { writer?.close() }
        if (engineLazy.isInitialized()) {
            engineLazy.value.speech.close()
        }
        ioWorker.shutdownNow()
        super.onDestroy()
    }

    private fun configureRun() {
        benchmarkRoot = File(requireNotNull(getExternalFilesDir(null)), BENCHMARK_DIRECTORY)
            .canonicalFile
        require(benchmarkRoot.isDirectory) {
            "Benchmark directory is missing; push it with scripts/run-stt-eval.sh"
        }

        runId = intent.getStringExtra(EXTRA_RUN_ID).orEmpty()
        require(SAFE_NAME.matches(runId)) { "Invalid or missing run_id" }
        measuredRepeats = intent.getIntExtra(EXTRA_MEASURED_REPEATS, DEFAULT_MEASURED_REPEATS)
        warmupRuns = intent.getIntExtra(EXTRA_WARMUP_RUNS, DEFAULT_WARMUP_RUNS)
        require(measuredRepeats in 1..MAX_REPEATS) { "measured_repeats must be 1..$MAX_REPEATS" }
        require(warmupRuns in 0..MAX_REPEATS) { "warmup_runs must be 0..$MAX_REPEATS" }

        partialResult = childFile("results-$runId.jsonl.partial")
        finalResult = childFile("results-$runId.jsonl")
        require(!partialResult.exists() && !finalResult.exists()) {
            "Result already exists for run_id=$runId"
        }
    }

    private fun loadManifestAndModel() {
        ioWorker.execute {
            runCatching { readManifest(childFile(MANIFEST_FILE)) }
                .onSuccess { cases ->
                    runOnUiThread {
                        runCatching {
                            val loadStartedAtNs = SystemClock.elapsedRealtimeNanos()
                            status.text = "Loading ${engine.file.benchmarkEngineId}…"
                            engine.speech.load { loadResult ->
                                loadResult.onSuccess {
                                    modelLoadDurationMs = elapsedMs(loadStartedAtNs)
                                    startBenchmark(cases)
                                }.onFailure(::fail)
                            }
                        }.onFailure(::fail)
                    }
                }
                .onFailure { runOnUiThread { fail(it) } }
        }
    }

    private fun startBenchmark(cases: List<BenchmarkCase>) {
        runCatching {
            writer = BufferedWriter(FileWriter(partialResult, false))
            Trace.beginAsyncSection(TRACE_SECTION_NAME, TRACE_COOKIE)
            benchmarkTraceActive = true
            val jobs = buildList {
                repeat(warmupRuns) { repeatIndex ->
                    add(BenchmarkJob(cases.first(), "warmup", repeatIndex))
                }
                cases.forEach { case ->
                    repeat(measuredRepeats) { repeatIndex ->
                        add(BenchmarkJob(case, "measured", repeatIndex))
                    }
                }
            }
            runJob(jobs, 0)
        }.onFailure(::fail)
    }

    private fun runJob(jobs: List<BenchmarkJob>, index: Int) {
        if (index >= jobs.size) {
            finishSuccessfully(jobs.size)
            return
        }
        val job = jobs[index]
        status.text = "${job.phase}: ${job.case.caseId} (${index + 1}/${jobs.size})"
        ioWorker.execute {
            runCatching {
                val audioFile = childFile(job.case.audioFile)
                require(audioFile.isFile) { "Missing audio: ${job.case.audioFile}" }
                require(sha256(audioFile) == job.case.audioSha256) {
                    "Audio checksum mismatch: ${job.case.audioFile}"
                }
                Pcm16WavReader.read(audioFile)
            }.onSuccess { audio ->
                runOnUiThread {
                    val traceInference = job.phase == "measured"
                    if (traceInference) {
                        Trace.beginAsyncSection(TRACE_INFERENCE_SECTION_NAME, index)
                    }
                    engine.file.transcribePcm(audio.samples, audio.sampleRate) { result ->
                        if (traceInference) {
                            Trace.endAsyncSection(TRACE_INFERENCE_SECTION_NAME, index)
                        }
                        result.onSuccess { inference ->
                            runCatching { writeResult(job, audio, inference) }
                                .onSuccess { runJob(jobs, index + 1) }
                                .onFailure(::fail)
                        }.onFailure(::fail)
                    }
                }
            }.onFailure { runOnUiThread { fail(it) } }
        }
    }

    private fun writeResult(
        job: BenchmarkJob,
        audio: PcmAudio,
        inference: FileSttBenchmarkResult,
    ) {
        val inferenceMs = inference.inferenceDurationMs
        val record = JSONObject()
            .put("schema_version", SCHEMA_VERSION)
            .put("run_id", runId)
            .put("engine", engine.file.benchmarkEngineId)
            .put("phase", job.phase)
            .put("case_id", job.case.caseId)
            .put("repeat_index", job.repeatIndex)
            .put("audio_file", job.case.audioFile)
            .put("audio_sha256", job.case.audioSha256)
            .put("reference", job.case.reference)
            .put("hypothesis", inference.text)
            .put("sample_rate", audio.sampleRate)
            .put("sample_count", audio.samples.size)
            .put("audio_duration_ms", audio.durationMs)
            .put("model_load_duration_ms", modelLoadDurationMs)
            .put("inference_duration_ms", inferenceMs)
            .put("process_cpu_duration_ms", inference.processCpuDurationMs)
            .put(
                "average_process_cpu_cores",
                inference.processCpuDurationMs / inferenceMs,
            )
            .put("real_time_factor", inferenceMs / audio.durationMs)
            .put("process_pss_kb_after_inference", Debug.getPss())
            .put("native_heap_bytes_after_inference", Debug.getNativeHeapAllocatedSize())
            .put(
                "thermal_status_after_inference",
                getSystemService(PowerManager::class.java).currentThermalStatus,
            )
            .put("created_at_utc", Instant.now().toString())
        requireNotNull(writer).apply {
            write(record.toString())
            newLine()
            flush()
        }
    }

    private fun finishSuccessfully(totalJobs: Int) {
        runCatching {
            requireNotNull(writer).close()
            writer = null
            require(partialResult.renameTo(finalResult)) { "Could not finalize result file" }
            endBenchmarkTrace()
        }.onSuccess {
            status.text = "Finished $totalJobs runs\n${finalResult.name}"
            LocalFlowLog.info(
                "STT benchmark finished: engine=${engine.file.benchmarkEngineId}, " +
                    "runs=$totalJobs, result=${finalResult.name}",
            )
            finish()
        }.onFailure(::fail)
    }

    private fun fail(error: Throwable) {
        endBenchmarkTrace()
        LocalFlowLog.error("STT benchmark failed", error)
        status.text = "Benchmark failed: ${error.message ?: error.javaClass.simpleName}"
        runCatching { writer?.close() }
        writer = null
        if (::benchmarkRoot.isInitialized && ::runId.isInitialized) {
            runCatching {
                val failure = JSONObject()
                    .put("run_id", runId)
                    .put("error_type", error.javaClass.name)
                    .put("error", error.message ?: "Unknown error")
                    .put("created_at_utc", Instant.now().toString())
                childFile("error-$runId.json").writeText(failure.toString(2))
            }
        }
    }

    private fun readManifest(file: File): List<BenchmarkCase> {
        require(file.isFile) { "Missing $MANIFEST_FILE" }
        val cases = file.useLines { lines ->
            lines.filter(String::isNotBlank).mapIndexed { index, line ->
                val json = runCatching { JSONObject(line) }
                    .getOrElse { throw IllegalArgumentException("Invalid manifest line ${index + 1}", it) }
                val caseId = json.getString("case_id")
                val audioFile = json.getString("audio_file")
                val audioSha256 = json.getString("audio_sha256").lowercase()
                val reference = json.getString("reference").trim()
                require(SAFE_NAME.matches(caseId)) { "Invalid case_id on line ${index + 1}" }
                require(SAFE_AUDIO_PATH.matches(audioFile)) {
                    "Invalid audio_file on line ${index + 1}"
                }
                require(SHA256.matches(audioSha256)) {
                    "Invalid audio_sha256 on line ${index + 1}"
                }
                require(reference.isNotEmpty()) { "Empty reference on line ${index + 1}" }
                BenchmarkCase(caseId, audioFile, audioSha256, reference)
            }.toList()
        }
        require(cases.isNotEmpty()) { "Manifest has no cases" }
        require(cases.map { it.caseId }.toSet().size == cases.size) { "Duplicate case_id" }
        return cases
    }

    private fun childFile(relativePath: String): File {
        val file = File(benchmarkRoot, relativePath).canonicalFile
        require(file.path.startsWith(benchmarkRoot.path + File.separator)) {
            "Path escapes benchmark directory"
        }
        return file
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().buffered().use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
    }

    private fun elapsedMs(startedAtNs: Long): Double =
        (SystemClock.elapsedRealtimeNanos() - startedAtNs).coerceAtLeast(0L) / 1_000_000.0

    private fun endBenchmarkTrace() {
        if (benchmarkTraceActive) {
            Trace.endAsyncSection(TRACE_SECTION_NAME, TRACE_COOKIE)
            benchmarkTraceActive = false
        }
    }

    private data class BenchmarkCase(
        val caseId: String,
        val audioFile: String,
        val audioSha256: String,
        val reference: String,
    )

    private data class BenchmarkJob(
        val case: BenchmarkCase,
        val phase: String,
        val repeatIndex: Int,
    )

    private data class BenchmarkEngine(
        val speech: SpeechToTextEngine,
        val file: FileSttBenchmarkEngine,
    )

    private companion object {
        const val EXTRA_RUN_ID = "run_id"
        const val EXTRA_ENGINE = "engine"
        const val EXTRA_MODEL_FILE = "model_file"
        const val EXTRA_MODEL_VARIANT = "model_variant"
        const val EXTRA_MEASURED_REPEATS = "measured_repeats"
        const val EXTRA_WARMUP_RUNS = "warmup_runs"
        const val BENCHMARK_DIRECTORY = "stt-eval"
        const val MANIFEST_FILE = "manifest.jsonl"
        const val DEFAULT_MEASURED_REPEATS = 3
        const val DEFAULT_WARMUP_RUNS = 1
        const val MAX_REPEATS = 10
        const val SCHEMA_VERSION = 1
        const val ENGINE_MOONSHINE = "moonshine"
        const val ENGINE_PARAKEET = "parakeet"
        const val TRACE_SECTION_NAME = "localflow_stt_benchmark"
        const val TRACE_INFERENCE_SECTION_NAME = "localflow_stt_inference"
        const val TRACE_COOKIE = 1
        val SAFE_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        val SAFE_AUDIO_PATH = Regex("audio/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\\.wav")
        val SAFE_MODEL_PATH = Regex("models/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\\.gguf")
        val SHA256 = Regex("[0-9a-f]{64}")
    }
}
