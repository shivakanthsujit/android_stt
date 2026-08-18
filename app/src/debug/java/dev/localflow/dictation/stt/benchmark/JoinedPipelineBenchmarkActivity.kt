package dev.localflow.dictation.stt.benchmark

import android.app.Activity
import android.os.Debug
import android.os.Bundle
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
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
import java.security.MessageDigest
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

/** Debug-only file-fed Parakeet -> Sotto integration runner. The microphone is never opened. */
class JoinedPipelineBenchmarkActivity : Activity() {
    private lateinit var status: TextView
    private val ioWorker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-joined-benchmark-io").apply { isDaemon = true }
    }
    private val uiJob = SupervisorJob()
    private val uiScope = CoroutineScope(uiJob + Dispatchers.Main.immediate)
    private val parakeetLazy = lazy {
        ParakeetSttEngine(
            modelFile = IntegrationModels.parakeetFile(applicationContext),
            modelVariant = PARAKEET_VARIANT,
        )
    }
    private val cleanupLazy = lazy {
        SottoCleanupEngine(
            context = applicationContext,
            modelFile = IntegrationModels.modelDirectory(applicationContext).resolve(sottoFileName),
            expectedModelSha256 = sottoSha256,
        )
    }
    private val parakeet by parakeetLazy
    private val cleanup by cleanupLazy

    private lateinit var benchmarkRoot: File
    private lateinit var runId: String
    private lateinit var partialResult: File
    private lateinit var finalResult: File
    private var writer: BufferedWriter? = null
    private var parakeetLoadMs = 0L
    private var cleanupLoadMs = 0L
    private lateinit var sottoFileName: String
    private lateinit var sottoSha256: String
    private var benchmarkTraceActive = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        status = TextView(this).apply {
            textSize = 18f
            setPadding(48, 48, 48, 48)
            text = "Starting file-fed joined pipeline…"
        }
        setContentView(status)
        runCatching { configureRun() }
            .onSuccess { loadManifestAndModels() }
            .onFailure(::fail)
    }

    override fun onDestroy() {
        endBenchmarkTrace()
        runCatching { writer?.close() }
        if (parakeetLazy.isInitialized()) parakeetLazy.value.close()
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
        require(benchmarkRoot.isDirectory) {
            "Joined benchmark directory is missing; run scripts/run-joined-file-eval.sh"
        }
        runId = intent.getStringExtra(EXTRA_RUN_ID).orEmpty()
        require(SAFE_NAME.matches(runId)) { "Invalid or missing run_id" }
        sottoFileName = intent.getStringExtra(EXTRA_SOTTO_FILE_NAME)
            ?: IntegrationModels.SOTTO_FILE_NAME
        require(SAFE_GGUF_NAME.matches(sottoFileName)) { "Invalid Sotto model filename" }
        sottoSha256 = (intent.getStringExtra(EXTRA_SOTTO_SHA256)
            ?: IntegrationModels.SOTTO_SHA256).lowercase()
        require(SHA256.matches(sottoSha256)) { "Invalid Sotto SHA-256" }
        partialResult = childFile("results-$runId.jsonl.partial")
        finalResult = childFile("results-$runId.jsonl")
        require(!partialResult.exists() && !finalResult.exists()) {
            "Result already exists for run_id=$runId"
        }
    }

    private fun loadManifestAndModels() {
        ioWorker.execute {
            runCatching {
                val cases = readManifest(childFile(MANIFEST_FILE))
                IntegrationModels.requireVerified(
                    IntegrationModels.parakeetFile(applicationContext),
                    IntegrationModels.PARAKEET_SHA256,
                    "Parakeet Q4_K",
                )
                cases
            }.onSuccess { cases ->
                runOnUiThread { loadParakeet(cases) }
            }.onFailure { error -> runOnUiThread { fail(error) } }
        }
    }

    private fun loadParakeet(cases: List<JoinedCase>) {
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        status.text = "Loading staged Parakeet…"
        parakeet.load { result ->
            result.onSuccess {
                parakeetLoadMs = elapsedMs(startedAtNs)
                loadCleanup(cases)
            }.onFailure(::fail)
        }
    }

    private fun loadCleanup(cases: List<JoinedCase>) {
        status.text = "Loading staged Sotto…"
        uiScope.launch {
            val startedAtNs = SystemClock.elapsedRealtimeNanos()
            runCatching { cleanup.load() }
                .onSuccess {
                    cleanupLoadMs = elapsedMs(startedAtNs)
                    runCatching { writer = BufferedWriter(FileWriter(partialResult, false)) }
                        .onSuccess {
                            Trace.beginAsyncSection(TRACE_SECTION_NAME, TRACE_COOKIE)
                            benchmarkTraceActive = true
                            runCase(cases, 0)
                        }
                        .onFailure(::fail)
                }
                .onFailure(::fail)
        }
    }

    private fun runCase(cases: List<JoinedCase>, index: Int) {
        if (index >= cases.size) {
            finishSuccessfully(cases.size)
            return
        }
        val case = cases[index]
        status.text = "${case.caseId} (${index + 1}/${cases.size})"
        ioWorker.execute {
            runCatching {
                val audioFile = childFile(case.audioFile)
                require(audioFile.isFile) { "Missing audio: ${case.audioFile}" }
                require(sha256(audioFile) == case.audioSha256) {
                    "Audio checksum mismatch: ${case.audioFile}"
                }
                Pcm16WavReader.read(audioFile)
            }.onSuccess { audio ->
                runOnUiThread { transcribeAndClean(cases, index, case, audio) }
            }.onFailure { error -> runOnUiThread { fail(error) } }
        }
    }

    private fun transcribeAndClean(
        cases: List<JoinedCase>,
        index: Int,
        case: JoinedCase,
        audio: PcmAudio,
    ) {
        val pipelineStartedAtNs = SystemClock.elapsedRealtimeNanos()
        Trace.beginAsyncSection(TRACE_STT_SECTION_NAME, index)
        parakeet.transcribePcm(audio.samples, audio.sampleRate) { sttResult ->
            Trace.endAsyncSection(TRACE_STT_SECTION_NAME, index)
            sttResult.onSuccess { stt ->
                uiScope.launch {
                    runCatching {
                        val cleanupCpuStartedAtMs = Process.getElapsedCpuTime()
                        Trace.beginAsyncSection(TRACE_CLEANUP_SECTION_NAME, index)
                        val cleanupResult = try {
                            cleanup.clean(stt.text, CleanupPromptVariant.SOTTO_NATIVE)
                        } finally {
                            Trace.endAsyncSection(TRACE_CLEANUP_SECTION_NAME, index)
                        }
                        val cleanupProcessCpuMs =
                            (Process.getElapsedCpuTime() - cleanupCpuStartedAtMs).coerceAtLeast(0L)
                        val pipelineCompletedAtNs = SystemClock.elapsedRealtimeNanos()
                        JSONObject()
                            .put("schema_version", SCHEMA_VERSION)
                            .put("run_id", runId)
                            .put("case_id", case.caseId)
                            .put("audio_file", case.audioFile)
                            .put("audio_sha256", case.audioSha256)
                            .put("reference", case.reference)
                            .put("audio_duration_ms", audio.durationMs)
                            .put("parakeet_model_load_ms", parakeetLoadMs)
                            .put("sotto_model_load_ms", cleanupLoadMs)
                            .put("sotto_model_file", sottoFileName)
                            .put("sotto_model_sha256", sottoSha256)
                            .put("stt_inference_ms", stt.inferenceDurationMs)
                            .put("stt_process_cpu_ms", stt.processCpuDurationMs)
                            .put("raw_stt", stt.text)
                            .put("model_input", cleanupResult.modelInputText)
                            .put("removed_fillers", JSONArray(cleanupResult.removedFillers))
                            .put("raw_model_output", cleanupResult.modelText)
                            .put("guarded_output", cleanupResult.cleanedText)
                            .put("used_fallback", cleanupResult.usedFallback)
                            .put(
                                "fallback_reason",
                                cleanupResult.fallbackReason ?: JSONObject.NULL,
                            )
                            .put(
                                "cleanup_ttft_ms",
                                cleanupResult.timeToFirstTokenMs ?: JSONObject.NULL,
                            )
                            .put("cleanup_total_ms", cleanupResult.totalLatencyMs)
                            .put("cleanup_process_cpu_ms", cleanupProcessCpuMs)
                            .put(
                                "cleanup_prompt_tokens",
                                cleanupResult.promptTokens ?: JSONObject.NULL,
                            )
                            .put(
                                "cleanup_completion_tokens",
                                cleanupResult.completionTokens ?: JSONObject.NULL,
                            )
                            .put(
                                "cleanup_tokens_per_second",
                                cleanupResult.tokensPerSecond ?: JSONObject.NULL,
                            )
                            .put(
                                "pipeline_total_ms",
                                (pipelineCompletedAtNs - pipelineStartedAtNs)
                                    .coerceAtLeast(0L) / 1_000_000L,
                            )
                            .put("process_pss_kb_after_pipeline", Debug.getPss())
                            .put(
                                "native_heap_bytes_after_pipeline",
                                Debug.getNativeHeapAllocatedSize(),
                            )
                            .put(
                                "thermal_status_after_pipeline",
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
                            }.onSuccess { runOnUiThread { runCase(cases, index + 1) } }
                                .onFailure { error -> runOnUiThread { fail(error) } }
                        }
                    }.onFailure(::fail)
                }
            }.onFailure(::fail)
        }
    }

    private fun finishSuccessfully(caseCount: Int) {
        runCatching {
            requireNotNull(writer).close()
            writer = null
            require(partialResult.renameTo(finalResult)) { "Could not finalize result file" }
            endBenchmarkTrace()
        }.onSuccess {
            status.text = "Finished $caseCount joined cases\n${finalResult.name}"
            LocalFlowLog.info(
                "Joined file benchmark finished: cases=$caseCount, result=${finalResult.name}",
            )
            finish()
        }.onFailure(::fail)
    }

    private fun fail(error: Throwable) {
        endBenchmarkTrace()
        LocalFlowLog.error("Joined file benchmark failed", error)
        status.text = "Joined benchmark failed: ${error.message ?: error.javaClass.simpleName}"
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

    private fun readManifest(file: File): List<JoinedCase> {
        require(file.isFile) { "Missing $MANIFEST_FILE" }
        val cases = file.useLines { lines ->
            lines.filter(String::isNotBlank).mapIndexed { index, line ->
                val json = runCatching { JSONObject(line) }.getOrElse {
                    throw IllegalArgumentException("Invalid manifest line ${index + 1}", it)
                }
                val caseId = json.getString("case_id")
                val audioFile = json.getString("audio_file")
                val audioSha256 = json.getString("audio_sha256").lowercase()
                require(SAFE_NAME.matches(caseId)) { "Invalid case_id on line ${index + 1}" }
                require(SAFE_AUDIO_PATH.matches(audioFile)) {
                    "Invalid audio_file on line ${index + 1}"
                }
                require(SHA256.matches(audioSha256)) {
                    "Invalid audio_sha256 on line ${index + 1}"
                }
                JoinedCase(
                    caseId = caseId,
                    audioFile = audioFile,
                    audioSha256 = audioSha256,
                    reference = json.optString("reference").trim(),
                )
            }.toList()
        }
        require(cases.isNotEmpty()) { "Manifest is empty" }
        require(cases.map(JoinedCase::caseId).distinct().size == cases.size) {
            "Manifest contains duplicate case IDs"
        }
        return cases
    }

    private fun childFile(relativePath: String): File {
        val file = File(benchmarkRoot, relativePath).canonicalFile
        require(file.path.startsWith(benchmarkRoot.path + File.separator)) {
            "Path escapes joined benchmark directory"
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

    private fun elapsedMs(startedAtNs: Long): Long =
        (SystemClock.elapsedRealtimeNanos() - startedAtNs).coerceAtLeast(0L) / 1_000_000L

    private fun endBenchmarkTrace() {
        if (benchmarkTraceActive) {
            Trace.endAsyncSection(TRACE_SECTION_NAME, TRACE_COOKIE)
            benchmarkTraceActive = false
        }
    }

    private data class JoinedCase(
        val caseId: String,
        val audioFile: String,
        val audioSha256: String,
        val reference: String,
    )

    private companion object {
        const val EXTRA_RUN_ID = "run_id"
        const val EXTRA_SOTTO_FILE_NAME = "sotto_file_name"
        const val EXTRA_SOTTO_SHA256 = "sotto_sha256"
        const val BENCHMARK_DIRECTORY = "joined-eval"
        const val MANIFEST_FILE = "manifest.jsonl"
        const val PARAKEET_VARIANT = "q4-k"
        const val SCHEMA_VERSION = 1
        const val TRACE_SECTION_NAME = "localflow_joined_benchmark"
        const val TRACE_STT_SECTION_NAME = "localflow_joined_stt_inference"
        const val TRACE_CLEANUP_SECTION_NAME = "localflow_joined_cleanup_inference"
        const val TRACE_COOKIE = 1
        val SAFE_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
        val SAFE_GGUF_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}\\.gguf")
        val SAFE_AUDIO_PATH = Regex("audio/[A-Za-z0-9][A-Za-z0-9._-]{0,127}\\.wav")
        val SHA256 = Regex("[0-9a-f]{64}")
    }
}
