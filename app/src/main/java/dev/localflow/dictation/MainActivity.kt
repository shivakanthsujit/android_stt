package dev.localflow.dictation

import android.Manifest
import android.app.Activity
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.SystemClock
import android.provider.Settings
import android.view.View
import android.view.inputmethod.InputMethodManager
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import dev.localflow.dictation.cleanup.CleanupBatchRunner
import dev.localflow.dictation.cleanup.CleanupEngine
import dev.localflow.dictation.cleanup.CleanupPromptVariant
import dev.localflow.dictation.cleanup.CleanupResult
import dev.localflow.dictation.cleanup.CleanupState
import dev.localflow.dictation.ime.LocalFlowImeService
import dev.localflow.dictation.stt.SpeechToTextEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class MainActivity : Activity() {
    private lateinit var statusText: TextView
    private lateinit var transcriptText: EditText
    private lateinit var cleanupStatusText: TextView
    private lateinit var cleanupModelInputText: TextView
    private lateinit var modelOutputText: TextView
    private lateinit var cleanedText: TextView
    private lateinit var metricsText: TextView
    private lateinit var loadModelButton: Button
    private lateinit var dictationButton: Button
    private lateinit var loadCleanupModelButton: Button
    private lateinit var cleanTextButton: Button
    private lateinit var runCleanupEvalButton: Button
    private lateinit var evaluationStatusText: TextView
    private lateinit var imeSetupStatusText: TextView
    private lateinit var enableImeButton: Button
    private lateinit var chooseImeButton: Button
    private lateinit var grantMicrophoneButton: Button

    private var modelLoadStartedAtNs = 0L
    private var modelLoadDurationMs: Long? = null
    private var recordingDurationMs: Long? = null
    private var sttTailMs: Long? = null
    private var pipelineTailMs: Long? = null
    private var cleanupLoadDurationMs: Long? = null
    private var lastCleanupResult: CleanupResult? = null
    private var cleanupBatchRunning = false
    private var startAfterPermissionGrant = false
    private var activityOwnsRecording = false
    private val uiJob = SupervisorJob()
    private val uiScope = CoroutineScope(uiJob + Dispatchers.Main.immediate)

    private val pipelineCoordinator: DictationPipelineCoordinator by lazy {
        (application as LocalFlowApplication).pipelineCoordinator
    }
    private val engine: SpeechToTextEngine
        get() = pipelineCoordinator.speechEngine
    private val cleanupEngine: CleanupEngine
        get() = pipelineCoordinator.cleanupEngine
    private val speechStateListener: (SpeechToTextEngine.State) -> Unit = ::renderState

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        transcriptText = findViewById(R.id.transcriptText)
        cleanupStatusText = findViewById(R.id.cleanupStatusText)
        cleanupModelInputText = findViewById(R.id.cleanupModelInputText)
        modelOutputText = findViewById(R.id.modelOutputText)
        cleanedText = findViewById(R.id.cleanedText)
        metricsText = findViewById(R.id.metricsText)
        loadModelButton = findViewById(R.id.loadModelButton)
        dictationButton = findViewById(R.id.dictationButton)
        loadCleanupModelButton = findViewById(R.id.loadCleanupModelButton)
        cleanTextButton = findViewById(R.id.cleanTextButton)
        runCleanupEvalButton = findViewById(R.id.runCleanupEvalButton)
        evaluationStatusText = findViewById(R.id.evaluationStatusText)
        imeSetupStatusText = findViewById(R.id.imeSetupStatusText)
        enableImeButton = findViewById(R.id.enableImeButton)
        chooseImeButton = findViewById(R.id.chooseImeButton)
        grantMicrophoneButton = findViewById(R.id.grantMicrophoneButton)

        loadModelButton.setOnClickListener { loadModel() }
        loadCleanupModelButton.setOnClickListener { loadCleanupModel() }
        cleanTextButton.setOnClickListener { cleanRawText() }
        runCleanupEvalButton.setOnClickListener { runCleanupEvaluation() }
        enableImeButton.setOnClickListener {
            startActivity(Intent(Settings.ACTION_INPUT_METHOD_SETTINGS))
        }
        chooseImeButton.setOnClickListener {
            inputMethodManager().showInputMethodPicker()
        }
        grantMicrophoneButton.setOnClickListener {
            requestPermissions(
                arrayOf(Manifest.permission.RECORD_AUDIO),
                MICROPHONE_PERMISSION_REQUEST,
            )
        }
        dictationButton.setOnClickListener {
            when (engine.state) {
                SpeechToTextEngine.State.READY -> startDictation()
                SpeechToTextEngine.State.RECORDING -> stopDictation()
                else -> Unit
            }
        }

        pipelineCoordinator.addSpeechStateListener(speechStateListener)
        renderState(engine.state)
        renderCleanupState(cleanupEngine.state)
        statusText.setText(
            if (engine.state == SpeechToTextEngine.State.READY) {
                R.string.status_model_ready
            } else {
                R.string.status_model_not_loaded
            },
        )
        cleanupStatusText.setText(
            if (cleanupEngine.state == CleanupState.READY) {
                R.string.status_cleanup_ready
            } else {
                R.string.status_cleanup_model_not_loaded
            },
        )
        renderImeSetupState()
    }

    override fun onResume() {
        super.onResume()
        if (::imeSetupStatusText.isInitialized) renderImeSetupState()
    }

    override fun onDestroy() {
        if (activityOwnsRecording && engine.state == SpeechToTextEngine.State.RECORDING) {
            activityOwnsRecording = false
            pipelineCoordinator.cancelDictation { result ->
                result.onFailure { LocalFlowLog.error("Activity dictation cancel failed", it) }
            }
        }
        pipelineCoordinator.removeSpeechStateListener(speechStateListener)
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
        renderImeSetupState()
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
        updateTranscript("")
        cleanedText.setText(R.string.cleaned_transcript_placeholder)
        cleanupModelInputText.setText(R.string.cleanup_model_input_placeholder)
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
                updateTranscript(transcript, R.string.transcript_listening)
            },
        ) { result ->
            result.onSuccess {
                activityOwnsRecording = true
                statusText.setText(R.string.status_listening)
            }.onFailure {
                activityOwnsRecording = false
                showError(it)
            }
        }
    }

    private fun stopDictation() {
        activityOwnsRecording = false
        statusText.setText(R.string.status_finalizing)
        dictationButton.isEnabled = false
        engine.stop { result ->
            result.onSuccess { sttResult ->
                updateTranscript(sttResult.text, R.string.transcript_no_speech)
                recordingDurationMs = sttResult.recordingDurationMs
                sttTailMs = sttResult.finalizationLatencyMs
                renderMetrics()
                renderCleanupState(currentCleanupState())
                statusText.setText(R.string.status_finished)
                if (
                    sttResult.text.isNotBlank() &&
                    currentCleanupState() == CleanupState.READY
                ) {
                    cleanText(
                        rawText = sttResult.text,
                        pipelineStopPressedAtNs = sttResult.stopPressedAtNs,
                        preferredBoundaryOffsets = sttResult.preferredCleanupBoundaryOffsets,
                    )
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

    private fun updateTranscript(text: String, emptyHintRes: Int? = null) {
        val followTail = !transcriptText.canScrollVertically(1)
        val previousScrollY = transcriptText.scrollY
        transcriptText.setText(text)
        transcriptText.hint = if (text.isBlank() && emptyHintRes != null) {
            getString(emptyHintRes)
        } else {
            null
        }
        transcriptText.post {
            val layoutHeight = transcriptText.layout?.height ?: return@post
            val viewportHeight = (
                transcriptText.height -
                    transcriptText.compoundPaddingTop -
                    transcriptText.compoundPaddingBottom
                ).coerceAtLeast(0)
            val maximumScrollY = (layoutHeight - viewportHeight).coerceAtLeast(0)
            if (followTail) {
                transcriptText.setSelection(transcriptText.text.length)
                transcriptText.scrollTo(0, maximumScrollY)
            } else {
                transcriptText.scrollTo(0, previousScrollY.coerceAtMost(maximumScrollY))
            }
        }
    }

    private fun cleanText(
        rawText: String,
        pipelineStopPressedAtNs: Long?,
        preferredBoundaryOffsets: List<Int> = emptyList(),
    ) {
        if (rawText.isEmpty()) {
            cleanupStatusText.setText(R.string.status_cleanup_empty_input)
            return
        }

        cleanupStatusText.setText(R.string.status_cleanup_generating)
        cleanupModelInputText.setText(R.string.cleanup_model_input_preparing)
        modelOutputText.text = ""
        cleanedText.text = ""
        renderCleanupState(CleanupState.GENERATING)
        uiScope.launch {
            runCatching {
                cleanupEngine.cleanTranscript(
                    text = rawText,
                    promptVariant = CleanupPromptVariant.S1_MINI_NATIVE,
                    preferredBoundaryOffsets = preferredBoundaryOffsets,
                )
            }
                .onSuccess { result ->
                    lastCleanupResult = result
                    pipelineTailMs = pipelineStopPressedAtNs?.let { stoppedAtNs ->
                        (result.completedAtNs - stoppedAtNs).coerceAtLeast(0L) / 1_000_000L
                    }
                    cleanupModelInputText.text = result.modelInputText.ifBlank {
                        getString(R.string.cleanup_model_input_empty)
                    }
                    modelOutputText.text = result.modelText.ifBlank {
                        if (result.modelWasRun) {
                            getString(R.string.model_output_empty)
                        } else {
                            getString(R.string.model_skipped_after_preprocessing)
                        }
                    }
                    cleanedText.text = result.cleanedText
                    cleanupStatusText.text = when {
                        result.usedFallback -> getString(
                            R.string.status_cleanup_fallback,
                            result.fallbackReason ?: "output validity check",
                        )
                        !result.modelWasRun ->
                            getString(R.string.status_cleanup_preprocessing_only)
                        else -> getString(R.string.status_cleanup_finished)
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
                    promptVariants = listOf(CleanupPromptVariant.S1_MINI_NATIVE),
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
                if (result.removedFillers.isNotEmpty()) {
                    add(
                        getString(
                            R.string.metric_fillers_removed,
                            result.removedFillers.size,
                        ),
                    )
                }
                result.timeToFirstTokenMs?.let {
                    add(getString(R.string.metric_cleanup_ttft, it))
                }
                add(getString(R.string.metric_cleanup_total, result.totalLatencyMs))
                if (result.cleanupPassCount > 1) {
                    add(getString(R.string.metric_cleanup_passes, result.cleanupPassCount))
                }
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

    private fun currentCleanupState(): CleanupState = cleanupEngine.state

    private fun renderImeSetupState() {
        val permissionGranted = checkSelfPermission(Manifest.permission.RECORD_AUDIO) ==
            PackageManager.PERMISSION_GRANTED
        val enabled = inputMethodManager().enabledInputMethodList.any { info ->
            info.serviceInfo.packageName == packageName &&
                info.serviceInfo.name == LocalFlowImeService::class.java.name
        }
        val selectedId = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.DEFAULT_INPUT_METHOD,
        )
        val component = ComponentName(this, LocalFlowImeService::class.java)
        val selected = selectedId == component.flattenToString() ||
            selectedId == component.flattenToShortString()

        imeSetupStatusText.text = getString(
            R.string.ime_setup_status,
            if (permissionGranted) getString(R.string.setup_yes) else getString(R.string.setup_no),
            if (enabled) getString(R.string.setup_yes) else getString(R.string.setup_no),
            if (selected) getString(R.string.setup_yes) else getString(R.string.setup_no),
        )
        grantMicrophoneButton.visibility = if (permissionGranted) View.GONE else View.VISIBLE
        chooseImeButton.isEnabled = enabled
    }

    private fun inputMethodManager(): InputMethodManager =
        getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager

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
