package dev.localflow.litertlmbenchmark

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.os.Debug
import android.os.PowerManager
import android.os.Process
import android.os.SystemClock
import android.view.WindowManager
import android.widget.TextView
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.MessageCallback
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.ThinkingConfig
import java.io.BufferedWriter
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.OutputStreamWriter
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.time.Instant
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference
import org.json.JSONArray
import org.json.JSONObject

/** Isolated transcript-only LiteRT-LM probe. It declares and opens no microphone permission. */
@OptIn(ExperimentalApi::class)
class LiteRtLmBenchmarkActivity : Activity() {
    private lateinit var statusView: TextView
    private val worker = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "s1-litertlm-benchmark").apply { isDaemon = true }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        statusView = TextView(this).apply {
            textSize = 18f
            setPadding(48, 48, 48, 48)
            text = "Preparing isolated LiteRT-LM benchmark…"
        }
        setContentView(statusView)
        runCatching(::configureRun)
            .onSuccess { worker.execute { executeRun(it) } }
            .onFailure(::showFailure)
    }

    override fun onDestroy() {
        worker.shutdown()
        super.onDestroy()
    }

    private fun configureRun(): ConfiguredRun {
        val runId = intent.getStringExtra(EXTRA_RUN_ID).orEmpty()
        require(SAFE_NAME.matches(runId)) { "invalid or missing run_id" }
        val backendName = intent.getStringExtra(EXTRA_BACKEND).orEmpty()
        require(backendName in setOf("cpu", "gpu")) { "backend must be cpu or gpu" }
        val cpuThreads = intent.getIntExtra(EXTRA_CPU_THREADS, 2)
        require(cpuThreads in 1..8) { "cpu_threads must be between 1 and 8" }
        val measuredRepeats = intent.getIntExtra(EXTRA_MEASURED_REPEATS, 1)
        val warmupRuns = intent.getIntExtra(EXTRA_WARMUP_RUNS, 1)
        require(measuredRepeats in 1..10 && warmupRuns in 0..10) { "invalid repeat counts" }
        require(intent.getStringExtra(EXTRA_MODEL_SHA256).orEmpty().lowercase() == S1LiteRtContract.MODEL_SHA256) {
            "unexpected model SHA-256"
        }
        require(intent.getStringExtra(EXTRA_MODEL_FILE_NAME) == S1LiteRtContract.MODEL_FILE_NAME) {
            "unexpected model filename"
        }

        val modelRoot = File(filesDir, MODEL_DIRECTORY).canonicalFile
        val benchmarkRoot = File(filesDir, BENCHMARK_DIRECTORY).canonicalFile
        require(modelRoot.isDirectory && benchmarkRoot.isDirectory) { "staging directories are missing" }
        return ConfiguredRun(
            runId = runId,
            backendName = backendName,
            cpuThreads = cpuThreads,
            measuredRepeats = measuredRepeats,
            warmupRuns = warmupRuns,
            modelFile = childFile(modelRoot, S1LiteRtContract.MODEL_FILE_NAME),
            casesFile = childFile(benchmarkRoot, CASES_FILE_NAME),
            partialResult = childFile(benchmarkRoot, "results-$runId.jsonl.partial"),
            finalResult = childFile(benchmarkRoot, "results-$runId.jsonl"),
            errorResult = childFile(benchmarkRoot, "error-$runId.json"),
            cacheDir = File(cacheDir, "litertlm-$backendName").canonicalFile,
        ).also {
            require(!it.partialResult.exists() && !it.finalResult.exists() && !it.errorResult.exists()) {
                "run output already exists"
            }
        }
    }

    private fun executeRun(run: ConfiguredRun) {
        var writer: BufferedWriter? = null
        var engine: Engine? = null
        runCatching {
            validateModel(run.modelFile)
            val cases = readCases(run.casesFile)
            run.cacheDir.mkdirs()
            require(run.cacheDir.isDirectory) { "could not create backend cache directory" }
            val backend = if (run.backendName == "cpu") {
                Backend.CPU(threadCount = run.cpuThreads)
            } else {
                Backend.GPU()
            }
            updateStatus("Loading S1 LiteRT-LM ${run.backendName.uppercase()}…")
            val loadStart = SystemClock.elapsedRealtimeNanos()
            engine = Engine(
                EngineConfig(
                    modelPath = run.modelFile.path,
                    backend = backend,
                    maxNumTokens = S1LiteRtContract.CONTEXT_TOKENS,
                    cacheDir = run.cacheDir.path,
                ),
            ).also(Engine::initialize)
            val modelLoadMs = elapsedMs(loadStart)
            writer = BufferedWriter(
                OutputStreamWriter(FileOutputStream(run.partialResult, false), StandardCharsets.UTF_8),
            )
            val jobs = buildJobOrder(cases.size, run.warmupRuns, run.measuredRepeats)
            jobs.forEachIndexed { index, job ->
                val case = cases[job.caseIndex]
                updateStatus("${job.phase}: ${case.caseId} (${index + 1}/${jobs.size})")
                val maxOutputTokens = S1LiteRtContract.outputCap(case.rawTokenCount)
                val expectedPromptTokens = S1LiteRtContract.FIXED_PROMPT_TOKENS + case.rawTokenCount
                require(expectedPromptTokens + maxOutputTokens <= S1LiteRtContract.CONTEXT_TOKENS)
                val extraContext = mapOf<String, Any>("enable_thinking" to false)
                val thinkingConfig = ThinkingConfig(enableThinking = false)
                val config = ConversationConfig(
                    systemInstruction = Contents.of(S1LiteRtContract.SYSTEM_PROMPT),
                    samplerConfig = SamplerConfig(1, 1.0, 0.0, 0),
                    extraContext = extraContext,
                    prefillPrefaceOnInit = false,
                    maxOutputToken = maxOutputTokens,
                    thinkingConfig = thinkingConfig,
                )
                requireNotNull(engine).createConversation(config).use { conversation ->
                    val message = Message.user(S1LiteRtContract.userText(case.rawText))
                    val renderedPrompt = S1LiteRtContract.selectExactRenderedPrompt(
                        expected = S1LiteRtContract.renderPrompt(case.rawText),
                        preface = conversation.renderPrefaceIntoString(),
                        renderedMessage = conversation.renderMessageIntoString(message, extraContext),
                    )
                    val cpuStartMs = Process.getElapsedCpuTime()
                    val generationStartNs = SystemClock.elapsedRealtimeNanos()
                    val completion = CountDownLatch(1)
                    val response = StringBuilder()
                    val firstChunkAtNs = AtomicLong(0L)
                    val chunkCount = AtomicInteger(0)
                    val asyncFailure = AtomicReference<Throwable?>(null)
                    val callback = object : MessageCallback {
                        override fun onMessage(message: Message) {
                            val chunk = message.toString()
                            if (chunk.isNotEmpty()) {
                                firstChunkAtNs.compareAndSet(0L, SystemClock.elapsedRealtimeNanos())
                                synchronized(response) { response.append(chunk) }
                                chunkCount.incrementAndGet()
                            }
                        }

                        override fun onDone() {
                            completion.countDown()
                        }

                        override fun onError(throwable: Throwable) {
                            asyncFailure.set(throwable)
                            completion.countDown()
                        }
                    }
                    conversation.sendMessageAsync(
                        message = message,
                        callback = callback,
                        extraContext = extraContext,
                        maxOutputToken = maxOutputTokens,
                        thinkingConfig = thinkingConfig,
                    )
                    require(completion.await(300, TimeUnit.SECONDS)) { "generation timed out" }
                    asyncFailure.get()?.let { throw it }
                    val totalMs = elapsedMs(generationStartNs)
                    val firstTokenMs = firstChunkAtNs.get().takeIf { it > 0L }
                        ?.let { (it - generationStartNs).coerceAtLeast(0L) / 1_000_000L }
                    val processCpuMs = (Process.getElapsedCpuTime() - cpuStartMs).coerceAtLeast(0L)
                    var benchmarkError: String? = null
                    val benchmark = runCatching { conversation.getBenchmarkInfo() }
                        .onFailure { benchmarkError = "${it.javaClass.name}: ${it.message}" }
                        .getOrNull()
                    val record = JSONObject()
                        .put("schema_version", 1)
                        .put("run_id", run.runId)
                        .put("phase", job.phase)
                        .put("repeat_index", job.repeatIndex)
                        .put("case_id", case.caseId)
                        .put("categories", categoriesJson(case.categories))
                        .put("raw_text", case.rawText)
                        .put("raw_token_count", case.rawTokenCount)
                        .put("prompt_token_count_expected", expectedPromptTokens)
                        .put("fixed_prompt_tokens", S1LiteRtContract.FIXED_PROMPT_TOKENS)
                        .put("rendered_prompt", renderedPrompt)
                        .put("rendered_prompt_sha256", sha256(renderedPrompt.toByteArray()))
                        .put("requested_max_output_tokens", maxOutputTokens)
                        .put("raw_output", synchronized(response) { response.toString() })
                        .put("response_chunk_count", chunkCount.get())
                        .put("time_to_first_token_ms", firstTokenMs ?: JSONObject.NULL)
                        .put("conversation_token_count", conversation.getTokenCount())
                        .put("total_ms", totalMs)
                        .put("process_cpu_ms", processCpuMs)
                        .put("process_pss_kb_after_inference", Debug.getPss())
                        .put("native_heap_bytes_after_inference", Debug.getNativeHeapAllocatedSize())
                        .put("thermal_status_after_inference", getSystemService(PowerManager::class.java).currentThermalStatus)
                        .put("model_file", S1LiteRtContract.MODEL_FILE_NAME)
                        .put("model_sha256", S1LiteRtContract.MODEL_SHA256)
                        .put("model_load_ms", modelLoadMs)
                        .put("context_tokens", S1LiteRtContract.CONTEXT_TOKENS)
                        .put("backend", run.backendName)
                        .put("cpu_threads", if (run.backendName == "cpu") run.cpuThreads else JSONObject.NULL)
                        .put("litert_lm_version", BuildConfig.LITERT_LM_VERSION)
                        .put("benchmark_available", benchmark != null)
                        .put("benchmark_error", benchmarkError ?: JSONObject.NULL)
                        .put("benchmark_init_seconds", benchmark?.initTimeInSecond ?: JSONObject.NULL)
                        .put("time_to_first_token_seconds", benchmark?.timeToFirstTokenInSecond ?: JSONObject.NULL)
                        .put("benchmark_prefill_tokens", benchmark?.lastPrefillTokenCount ?: JSONObject.NULL)
                        .put("benchmark_decode_tokens", benchmark?.lastDecodeTokenCount ?: JSONObject.NULL)
                        .put("benchmark_prefill_tokens_per_second", benchmark?.lastPrefillTokensPerSecond ?: JSONObject.NULL)
                        .put("benchmark_decode_tokens_per_second", benchmark?.lastDecodeTokensPerSecond ?: JSONObject.NULL)
                        .put("device", Build.DEVICE)
                        .put("model", Build.MODEL)
                        .put("sdk_int", Build.VERSION.SDK_INT)
                        .put("supported_abis", JSONArray(Build.SUPPORTED_ABIS.toList()))
                        .put("created_at_utc", Instant.now().toString())
                    requireNotNull(writer).apply {
                        write(record.toString())
                        newLine()
                        flush()
                    }
                }
            }
            requireNotNull(writer).close()
            writer = null
            require(run.partialResult.renameTo(run.finalResult)) { "could not finalize result" }
            runOnUiThread {
                statusView.text = "Finished ${jobs.size} runs\n${run.finalResult.name}"
                finish()
            }
        }.onFailure { failure ->
            runCatching { writer?.close() }
            writer = null
            runCatching {
                run.errorResult.writeText(
                    JSONObject()
                        .put("run_id", run.runId)
                        .put("error_type", failure.javaClass.name)
                        .put("error", failure.message ?: "unknown error")
                        .put("created_at_utc", Instant.now().toString())
                        .toString(2),
                )
            }
            showFailure(failure)
        }
        runCatching { engine?.close() }
    }

    private fun readCases(file: File): List<TranscriptCase> {
        require(file.isFile) { "missing transcript-only cases file" }
        return file.useLines { lines ->
            lines.filter(String::isNotBlank)
                .mapIndexed { index, line -> TranscriptCaseParser.parseLine(line, index + 1) }
                .toList()
        }.also { cases ->
            require(cases.isNotEmpty()) { "cases file is empty" }
            require(cases.map(TranscriptCase::caseId).distinct().size == cases.size) {
                "duplicate case IDs"
            }
        }
    }

    private fun validateModel(file: File) {
        require(file.isFile && file.name == S1LiteRtContract.MODEL_FILE_NAME) { "pinned model is missing" }
        require(file.length() == S1LiteRtContract.MODEL_SIZE_BYTES) { "pinned model size mismatch" }
        FileInputStream(file).use { input ->
            val digest = MessageDigest.getInstance("SHA-256")
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
            require(digest.digest().joinToString("") { "%02x".format(it) } == S1LiteRtContract.MODEL_SHA256) {
                "pinned model SHA-256 mismatch"
            }
        }
    }

    private fun childFile(root: File, name: String): File = File(root, name).canonicalFile.also {
        require(it.path.startsWith(root.path + File.separator)) { "path escapes staging root" }
    }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }

    private fun elapsedMs(startNs: Long): Long =
        (SystemClock.elapsedRealtimeNanos() - startNs).coerceAtLeast(0L) / 1_000_000L

    private fun updateStatus(value: String) = runOnUiThread { statusView.text = value }

    private fun showFailure(failure: Throwable) = runOnUiThread {
        statusView.text = "LiteRT-LM benchmark failed: ${failure.message ?: failure.javaClass.simpleName}"
    }

    private data class ConfiguredRun(
        val runId: String,
        val backendName: String,
        val cpuThreads: Int,
        val measuredRepeats: Int,
        val warmupRuns: Int,
        val modelFile: File,
        val casesFile: File,
        val partialResult: File,
        val finalResult: File,
        val errorResult: File,
        val cacheDir: File,
    )

    private companion object {
        const val EXTRA_RUN_ID = "run_id"
        const val EXTRA_MODEL_FILE_NAME = "model_file_name"
        const val EXTRA_MODEL_SHA256 = "model_sha256"
        const val EXTRA_BACKEND = "backend"
        const val EXTRA_CPU_THREADS = "cpu_threads"
        const val EXTRA_MEASURED_REPEATS = "measured_repeats"
        const val EXTRA_WARMUP_RUNS = "warmup_runs"
        const val MODEL_DIRECTORY = "models"
        const val BENCHMARK_DIRECTORY = "benchmark"
        const val CASES_FILE_NAME = "cases.jsonl"
        val SAFE_NAME = Regex("[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
    }
}
