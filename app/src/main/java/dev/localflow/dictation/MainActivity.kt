package dev.localflow.dictation

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.SystemClock
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import dev.localflow.dictation.cleanup.CleanupBatchRunner
import dev.localflow.dictation.cleanup.CleanupPromptVariant
import dev.localflow.dictation.cleanup.CleanupResult
import dev.localflow.dictation.cleanup.CleanupState
import dev.localflow.dictation.cleanup.SottoCleanupEngine
import dev.localflow.dictation.stt.ParakeetLiveSttEngine
import dev.localflow.dictation.stt.SpeechToTextEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class MainActivity : Activity() {
    private lateinit var statusText: TextView
    private lateinit var transcriptText: EditText
    private lateinit var cleanupStatusText: TextView
    private lateinit var modelOutputText: TextView
    private lateinit var cleanedText: TextView
    private lateinit var metricsText: TextView
    private lateinit var loadModelButton: Button
    private lateinit var dictationButton: Button
    private lateinit var loadCleanupModelButton: Button
    private lateinit var cleanTextButton: Button
    private lateinit var runCleanupEvalButton: Button
    private lateinit var evaluationStatusText: TextView

    private var modelLoadStartedAtNs = 0L
    private var modelLoadDurationMs: Long? = null
    private var recordingDurationMs: Long? = null
    private var sttTailMs: Long? = null
    private var pipelineTailMs: Long? = null
    private var cleanupLoadDurationMs: Long? = null
    private var lastCleanupResult: CleanupResult? = null
    private var cleanupBatchRunning = false
    private var startAfterPermissionGrant = false
    private val uiJob = SupervisorJob()
    private val uiScope = CoroutineScope(uiJob + Dispatchers.Main.immediate)

    private val engine by lazy {
        ParakeetLiveSttEngine(
            context = applicationContext,
            modelFile = IntegrationModels.parakeetFile(applicationContext),
            expectedModelSha256 = IntegrationModels.PARAKEET_SHA256,
            onStateChanged = ::renderState,
        )
    }
    private val cleanupEngineLazy = lazy {
        SottoCleanupEngine(
            context = applicationContext,
            modelFile = IntegrationModels.sottoFile(applicationContext),
            expectedModelSha256 = IntegrationModels.SOTTO_SHA256,
        )
    }
    private val cleanupEngine by cleanupEngineLazy

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        transcriptText = findViewById(R.id.transcriptText)
        cleanupStatusText = findViewById(R.id.cleanupStatusText)
        modelOutputText = findViewById(R.id.modelOutputText)
        cleanedText = findViewById(R.id.cleanedText)
        metricsText = findViewById(R.id.metricsText)
        loadModelButton = findViewById(R.id.loadModelButton)
        dictationButton = findViewById(R.id.dictationButton)
        loadCleanupModelButton = findViewById(R.id.loadCleanupModelButton)
        cleanTextButton = findViewById(R.id.cleanTextButton)
        runCleanupEvalButton = findViewById(R.id.runCleanupEvalButton)
        evaluationStatusText = findViewById(R.id.evaluationStatusText)

        loadModelButton.setOnClickListener { loadModel() }
        loadCleanupModelButton.setOnClickListener { loadCleanupModel() }
        cleanTextButton.setOnClickListener { cleanRawText() }
        runCleanupEvalButton.setOnClickListener { runCleanupEvaluation() }
        dictationButton.setOnClickListener {
            when (engine.state) {
                SpeechToTextEngine.State.READY -> startDictation()
                SpeechToTextEngine.State.RECORDING -> stopDictation()
                else -> Unit
            }
        }

        renderState(SpeechToTextEngine.State.UNLOADED)
        renderCleanupState(CleanupState.UNLOADED)
        statusText.setText(R.string.status_model_not_loaded)
    }

    override fun onDestroy() {
        engine.close()
        if (cleanupEngineLazy.isInitialized()) {
            val engineToUnload = cleanupEngineLazy.value
            CoroutineScope(SupervisorJob() + Dispatchers.Default).launch {
                runCatching { engineToUnload.unload() }
                    .onFailure { LocalFlowLog.error("Cleanup unload failed", it) }
            }
        }
        uiJob.cancel()
        super.onDestroy()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode != MICROPHONE_PERMISSION_REQUEST) {
            return
        }
        val shouldStart = startAfterPermissionGrant
        startAfterPermissionGrant = false
        if (grantResults.firstOrNull() == PackageManager.PERMISSION_GRANTED) {
            if (shouldStart) {
                beginDictation()
            }
        } else {
            statusText.setText(R.string.status_microphone_permission_denied)
            renderState(engine.state)
        }
    }

    private fun loadModel() {
        modelLoadStartedAtNs = SystemClock.elapsedRealtimeNanos()
        statusText.setText(R.string.status_preparing_model)
        loadModelButton.isEnabled = false
        engine.load { result ->
            result.onSuccess {
                modelLoadDurationMs = elapsedMillisSince(modelLoadStartedAtNs)
                renderMetrics()
                statusText.setText(R.string.status_model_ready)
            }.onFailure(::showError)
        }
    }

    private fun startDictation() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            startAfterPermissionGrant = true
            statusText.setText(R.string.status_requesting_microphone_permission)
            requestPermissions(
                arrayOf(Manifest.permission.RECORD_AUDIO),
                MICROPHONE_PERMISSION_REQUEST,
            )
            return
        }
        beginDictation()
    }

    private fun beginDictation() {
        transcriptText.setText("")
        cleanedText.setText(R.string.cleaned_transcript_placeholder)
        modelOutputText.setText(R.string.model_output_placeholder)
        recordingDurationMs = null
        sttTailMs = null
        pipelineTailMs = null
        lastCleanupResult = null
        renderMetrics()
        statusText.setText(R.string.status_opening_microphone)
        dictationButton.isEnabled = false
        engine.start(
            onPartialTranscript = { transcript ->
                transcriptText.setText(transcript)
                transcriptText.hint = if (transcript.isBlank()) {
                    getString(R.string.transcript_listening)
                } else {
                    null
                }
            },
        ) { result ->
            result.onSuccess {
                statusText.setText(R.string.status_listening)
            }.onFailure(::showError)
        }
    }

    private fun stopDictation() {
        statusText.setText(R.string.status_finalizing)
        dictationButton.isEnabled = false
        engine.stop { result ->
            result.onSuccess { sttResult ->
                transcriptText.setText(sttResult.text)
                transcriptText.hint = if (sttResult.text.isBlank()) {
                    getString(R.string.transcript_no_speech)
                } else {
                    null
                }
                recordingDurationMs = sttResult.recordingDurationMs
                sttTailMs = sttResult.finalizationLatencyMs
                renderMetrics()
                renderCleanupState(currentCleanupState())
                statusText.setText(R.string.status_finished)
                if (
                    sttResult.text.isNotBlank() &&
                    currentCleanupState() == CleanupState.READY
                ) {
                    cleanText(sttResult.text, sttResult.stopPressedAtNs)
                } else if (sttResult.text.isNotBlank()) {
                    cleanupStatusText.setText(R.string.status_cleanup_load_for_pipeline)
                }
            }.onFailure(::showError)
        }
    }

    private fun loadCleanupModel() {
        cleanupStatusText.setText(R.string.status_cleanup_loading)
        renderCleanupState(CleanupState.LOADING)
        uiScope.launch {
            runCatching {
                cleanupEngine.load { progress ->
                    uiScope.launch {
                        val percent = (progress.fraction * 100f).toInt()
                        cleanupStatusText.text = getString(
                            R.string.status_cleanup_downloading,
                            percent,
                        )
                    }
                }
            }.onSuccess { result ->
                cleanupLoadDurationMs = result.durationMs
                cleanupStatusText.setText(R.string.status_cleanup_ready)
                renderCleanupState(CleanupState.READY)
                renderMetrics()
            }.onFailure(::showCleanupError)
        }
    }

    private fun cleanRawText() {
        val rawText = transcriptText.text.toString().trim()
        cleanText(rawText, pipelineStopPressedAtNs = null)
    }

    private fun cleanText(rawText: String, pipelineStopPressedAtNs: Long?) {
        if (rawText.isEmpty()) {
            cleanupStatusText.setText(R.string.status_cleanup_empty_input)
            return
        }

        cleanupStatusText.setText(R.string.status_cleanup_generating)
        modelOutputText.text = ""
        cleanedText.text = ""
        renderCleanupState(CleanupState.GENERATING)
        uiScope.launch {
            runCatching {
                cleanupEngine.clean(rawText, CleanupPromptVariant.SOTTO_NATIVE)
            }
                .onSuccess { result ->
                    lastCleanupResult = result
                    pipelineTailMs = pipelineStopPressedAtNs?.let { stoppedAtNs ->
                        (result.completedAtNs - stoppedAtNs).coerceAtLeast(0L) / 1_000_000L
                    }
                    modelOutputText.text = result.modelText.ifBlank {
                        getString(R.string.model_output_empty)
                    }
                    cleanedText.text = result.cleanedText
                    cleanupStatusText.text = if (result.usedFallback) {
                        getString(
                            R.string.status_cleanup_fallback,
                            result.fallbackReason ?: "guardrail",
                        )
                    } else {
                        getString(R.string.status_cleanup_finished)
                    }
                    renderCleanupState(CleanupState.READY)
                    renderMetrics()
                }.onFailure(::showCleanupError)
        }
    }

    private fun runCleanupEvaluation() {
        cleanupBatchRunning = true
        evaluationStatusText.setText(R.string.status_evaluation_starting)
        renderCleanupState(CleanupState.GENERATING)
        uiScope.launch {
            runCatching {
                CleanupBatchRunner(applicationContext, cleanupEngine).run(
                    promptVariants = listOf(CleanupPromptVariant.SOTTO_NATIVE),
                ) { progress ->
                    uiScope.launch {
                        evaluationStatusText.text = getString(
                            R.string.status_evaluation_progress,
                            progress.runIndex,
                            progress.totalRuns,
                            progress.promptVariant.id,
                            progress.caseId,
                        )
                    }
                }
            }.onSuccess { summary ->
                cleanupBatchRunning = false
                evaluationStatusText.text = getString(
                    R.string.status_evaluation_finished,
                    summary.totalRuns,
                    summary.exactMatches,
                    summary.fallbackCount,
                    summary.durationMs,
                    summary.resultFile.name,
                )
                renderCleanupState(CleanupState.READY)
            }.onFailure { error ->
                cleanupBatchRunning = false
                showCleanupError(error)
            }
        }
    }

    private fun renderState(state: SpeechToTextEngine.State) {
        loadModelButton.visibility = if (
            state == SpeechToTextEngine.State.UNLOADED ||
            state == SpeechToTextEngine.State.LOADING ||
            state == SpeechToTextEngine.State.FAILED
        ) {
            View.VISIBLE
        } else {
            View.GONE
        }
        loadModelButton.isEnabled = state == SpeechToTextEngine.State.UNLOADED ||
            state == SpeechToTextEngine.State.FAILED
        dictationButton.isEnabled = state == SpeechToTextEngine.State.READY ||
            state == SpeechToTextEngine.State.RECORDING
        dictationButton.text = if (state == SpeechToTextEngine.State.RECORDING) {
            getString(R.string.stop_dictation)
        } else {
            getString(R.string.start_dictation)
        }

        if (state == SpeechToTextEngine.State.FAILED) {
            loadModelButton.setText(R.string.retry_model_load)
        }
        renderCleanupState(currentCleanupState())
    }

    private fun renderCleanupState(state: CleanupState) {
        loadCleanupModelButton.visibility = if (
            state == CleanupState.UNLOADED ||
            state == CleanupState.LOADING ||
            state == CleanupState.FAILED
        ) {
            View.VISIBLE
        } else {
            View.GONE
        }
        val speechBusy = engine.state == SpeechToTextEngine.State.RECORDING ||
            engine.state == SpeechToTextEngine.State.FINALIZING
        loadCleanupModelButton.isEnabled = !speechBusy &&
            (state == CleanupState.UNLOADED || state == CleanupState.FAILED)
        cleanTextButton.isEnabled = !speechBusy && !cleanupBatchRunning &&
            state == CleanupState.READY
        runCleanupEvalButton.isEnabled = !speechBusy && !cleanupBatchRunning &&
            state == CleanupState.READY
        if (state == CleanupState.FAILED) {
            loadCleanupModelButton.setText(R.string.retry_cleanup_model_load)
        }
    }

    private fun renderMetrics() {
        val lines = buildList {
            modelLoadDurationMs?.let { add(getString(R.string.metric_model_load, it)) }
            recordingDurationMs?.let { add(getString(R.string.metric_recording, it)) }
            sttTailMs?.let { add(getString(R.string.metric_stt_tail, it)) }
            pipelineTailMs?.let { add(getString(R.string.metric_pipeline_tail, it)) }
            cleanupLoadDurationMs?.let { add(getString(R.string.metric_cleanup_load, it)) }
            lastCleanupResult?.let { result ->
                result.timeToFirstTokenMs?.let {
                    add(getString(R.string.metric_cleanup_ttft, it))
                }
                add(getString(R.string.metric_cleanup_total, result.totalLatencyMs))
                result.tokensPerSecond?.let {
                    add(getString(R.string.metric_cleanup_rate, it))
                }
                if (result.promptTokens != null && result.completionTokens != null) {
                    add(
                        getString(
                            R.string.metric_cleanup_tokens,
                            result.promptTokens,
                            result.completionTokens,
                        ),
                    )
                }
            }
        }
        metricsText.text = if (lines.isEmpty()) {
            getString(R.string.metrics_placeholder)
        } else {
            lines.joinToString("\n")
        }
    }

    private fun currentCleanupState(): CleanupState =
        if (cleanupEngineLazy.isInitialized()) cleanupEngine.state else CleanupState.UNLOADED

    private fun showError(error: Throwable) {
        LocalFlowLog.error("Benchmark UI error", error)
        statusText.text = getString(R.string.status_error, error.rootMessage())
        renderState(engine.state)
    }

    private fun showCleanupError(error: Throwable) {
        LocalFlowLog.error("Cleanup benchmark UI error", error)
        cleanupStatusText.text = getString(R.string.status_cleanup_error, error.rootMessage())
        renderCleanupState(currentCleanupState())
    }

    private fun elapsedMillisSince(startedAtNs: Long): Long =
        (SystemClock.elapsedRealtimeNanos() - startedAtNs).coerceAtLeast(0L) / 1_000_000L

    private fun Throwable.rootMessage(): String {
        var root = this
        while (root.cause != null && root.cause !== root) {
            root = root.cause!!
        }
        return root.message ?: root.javaClass.simpleName
    }

    private companion object {
        const val MICROPHONE_PERMISSION_REQUEST = 1001
    }
}
