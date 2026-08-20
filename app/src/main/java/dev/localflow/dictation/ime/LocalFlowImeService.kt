package dev.localflow.dictation.ime

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.inputmethodservice.InputMethodService
import android.view.View
import android.view.inputmethod.EditorInfo
import android.widget.Button
import android.widget.TextView
import dev.localflow.dictation.DictationPipelineCoordinator
import dev.localflow.dictation.LocalFlowApplication
import dev.localflow.dictation.LocalFlowLog
import dev.localflow.dictation.MainActivity
import dev.localflow.dictation.R
import dev.localflow.dictation.cleanup.CleanupState
import dev.localflow.dictation.stt.SpeechToTextEngine
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/** Minimal voice-only IME backed by the application-scoped local dictation pipeline. */
class LocalFlowImeService : InputMethodService() {
    private lateinit var statusText: TextView
    private lateinit var detailText: TextView
    private lateinit var metricsText: TextView
    private lateinit var mainButton: Button
    private lateinit var cancelButton: Button
    private lateinit var undoButton: Button
    private lateinit var nextKeyboardButton: Button

    private val serviceJob = SupervisorJob()
    private val serviceScope = CoroutineScope(serviceJob + Dispatchers.Main.immediate)
    private val coordinator: DictationPipelineCoordinator
        get() = (application as LocalFlowApplication).pipelineCoordinator

    private var mode = Mode.NEEDS_MODELS
    private var editorIdentity: EditorIdentity? = null
    private var activeEditorIdentity: EditorIdentity? = null
    private var undoRecord: UndoRecord? = null
    private var operationGeneration = 0L
    private var lastRawText = ""
    private var lastCommittedText = ""
    private var lastMetrics = ""
    private var blockedReason: String? = null

    private val speechStateListener: (SpeechToTextEngine.State) -> Unit = { state ->
        if (state == SpeechToTextEngine.State.FAILED && mode != Mode.PROCESSING) {
            mode = Mode.ERROR
            blockedReason = getString(R.string.ime_model_error)
            render()
        }
    }

    override fun onCreate() {
        super.onCreate()
        coordinator.addSpeechStateListener(speechStateListener)
    }

    override fun onCreateInputView(): View {
        val view = layoutInflater.inflate(R.layout.ime_voice, null)
        statusText = view.findViewById(R.id.imeStatusText)
        detailText = view.findViewById(R.id.imeDetailText)
        metricsText = view.findViewById(R.id.imeMetricsText)
        mainButton = view.findViewById(R.id.imeMainButton)
        cancelButton = view.findViewById(R.id.imeCancelButton)
        undoButton = view.findViewById(R.id.imeUndoButton)
        nextKeyboardButton = view.findViewById(R.id.imeNextKeyboardButton)

        mainButton.setOnClickListener { onMainAction() }
        cancelButton.setOnClickListener { cancelCurrentOperation() }
        undoButton.setOnClickListener { undoLastCommit() }
        nextKeyboardButton.setOnClickListener { switchToNextInputMethod(false) }
        refreshAvailability()
        return view
    }

    override fun onEvaluateFullscreenMode(): Boolean = false

    override fun onStartInput(attribute: EditorInfo?, restarting: Boolean) {
        super.onStartInput(attribute, restarting)
        val previousIdentity = editorIdentity
        editorIdentity = attribute?.toIdentity()
        if (previousIdentity != editorIdentity) {
            undoRecord = null
            lastRawText = ""
            lastCommittedText = ""
            lastMetrics = ""
        }
        refreshAvailability(attribute)
    }

    override fun onStartInputView(info: EditorInfo?, restarting: Boolean) {
        super.onStartInputView(info, restarting)
        refreshAvailability(info)
    }

    override fun onFinishInput() {
        cancelCurrentOperation()
        editorIdentity = null
        activeEditorIdentity = null
        undoRecord = null
        lastRawText = ""
        lastCommittedText = ""
        lastMetrics = ""
        super.onFinishInput()
    }

    override fun onWindowHidden() {
        if (coordinator.speechEngine.state == SpeechToTextEngine.State.RECORDING) {
            cancelCurrentOperation()
        }
        super.onWindowHidden()
    }

    override fun onDestroy() {
        cancelCurrentOperation()
        coordinator.removeSpeechStateListener(speechStateListener)
        serviceScope.cancel()
        super.onDestroy()
    }

    private fun onMainAction() {
        when (mode) {
            Mode.BLOCKED, Mode.NEEDS_PERMISSION -> openSetup()
            Mode.NEEDS_MODELS, Mode.ERROR -> loadModels()
            Mode.READY, Mode.COMMITTED -> startDictation()
            Mode.RECORDING -> stopAndCommit()
            Mode.LOADING, Mode.PROCESSING -> Unit
        }
    }

    private fun loadModels() {
        mode = Mode.LOADING
        blockedReason = null
        render()
        serviceScope.launch {
            runCatching {
                coordinator.loadModels { progress ->
                    serviceScope.launch {
                        if (mode == Mode.LOADING) {
                            detailText.text = getString(
                                R.string.ime_cleanup_load_progress,
                                (progress.fraction * 100f).toInt(),
                            )
                        }
                    }
                }
            }.onSuccess { result ->
                lastMetrics = getString(R.string.ime_model_load_metric, result.durationMs)
                mode = Mode.READY
                render()
            }.onFailure { error ->
                LocalFlowLog.error("IME model load failed", error)
                blockedReason = error.rootMessage()
                mode = Mode.ERROR
                render()
            }
        }
    }

    private fun startDictation() {
        val info = currentInputEditorInfo
        refreshAvailability(info)
        if (mode != Mode.READY && mode != Mode.COMMITTED) return

        val identity = info?.toIdentity() ?: return
        activeEditorIdentity = identity
        undoRecord = null
        lastRawText = ""
        lastCommittedText = ""
        lastMetrics = ""
        val generation = ++operationGeneration
        serviceScope.launch {
            runCatching {
                coordinator.startDictation { partialTranscript ->
                    serviceScope.launch {
                        if (generation == operationGeneration && mode == Mode.RECORDING) {
                            lastRawText = partialTranscript
                            render()
                        }
                    }
                }
            }
                .onSuccess {
                    if (generation == operationGeneration) {
                        mode = Mode.RECORDING
                        render()
                    }
                }.onFailure { error ->
                    if (generation == operationGeneration) {
                        LocalFlowLog.error("IME dictation start failed", error)
                        blockedReason = error.rootMessage()
                        mode = Mode.ERROR
                        render()
                    }
                }
        }
    }

    private fun stopAndCommit() {
        if (mode != Mode.RECORDING) return
        mode = Mode.PROCESSING
        render()
        val generation = operationGeneration
        val startedForEditor = activeEditorIdentity ?: run {
            blockedReason = getString(R.string.ime_commit_failed)
            mode = Mode.ERROR
            render()
            return
        }
        serviceScope.launch {
            runCatching { coordinator.stopAndClean() }
                .onSuccess { result ->
                    if (generation != operationGeneration || startedForEditor != editorIdentity) {
                        refreshAvailability()
                        return@onSuccess
                    }
                    lastRawText = result.sttResult.text
                    lastCommittedText = result.committedText
                    lastMetrics = getString(
                        R.string.ime_pipeline_metric,
                        result.sttResult.recordingDurationMs,
                        result.sttResult.finalizationLatencyMs,
                        result.cleanupResult?.totalLatencyMs ?: 0L,
                        result.stopToCompletionMs,
                    )
                    if (result.committedText.isEmpty()) {
                        blockedReason = getString(R.string.ime_no_speech)
                        mode = Mode.READY
                        render()
                        return@onSuccess
                    }

                    val connection = currentInputConnection
                    val committed = connection?.commitText(result.committedText, 1) == true
                    if (!committed) {
                        blockedReason = getString(R.string.ime_commit_failed)
                        mode = Mode.ERROR
                    } else {
                        undoRecord = UndoRecord(startedForEditor, result.committedText)
                        blockedReason = when {
                            result.cleanupError != null -> getString(R.string.ime_committed_raw)
                            result.usedCleanupFallback -> getString(R.string.ime_committed_fallback)
                            else -> null
                        }
                        mode = Mode.COMMITTED
                        LocalFlowLog.info(
                            "IME committed locally: recording=${result.sttResult.recordingDurationMs}ms, " +
                                "stt=${result.sttResult.finalizationLatencyMs}ms, " +
                                "tail=${result.stopToCompletionMs}ms, " +
                                "fallback=${result.usedCleanupFallback}",
                        )
                    }
                    render()
                }.onFailure { error ->
                    if (generation == operationGeneration) {
                        LocalFlowLog.error("IME pipeline failed", error)
                        blockedReason = error.rootMessage()
                        mode = Mode.ERROR
                        render()
                    } else {
                        refreshAvailability()
                    }
                }
        }
    }

    private fun cancelCurrentOperation() {
        operationGeneration += 1
        activeEditorIdentity = null
        if (coordinator.speechEngine.state == SpeechToTextEngine.State.RECORDING) {
            coordinator.cancelDictation { result ->
                result.onFailure { LocalFlowLog.error("IME cancel failed", it) }
                refreshAvailability()
            }
        }
        if (::statusText.isInitialized) {
            blockedReason = getString(R.string.ime_canceled)
            refreshAvailability()
        }
    }

    private fun undoLastCommit() {
        val record = undoRecord ?: return
        val connection = currentInputConnection ?: return
        val beforeCursor = connection.getTextBeforeCursor(record.committedText.length, 0)
        if (!ImeEditorPolicy.canUndo(record, editorIdentity, beforeCursor)) {
            blockedReason = getString(R.string.ime_undo_unavailable)
            undoRecord = null
            render()
            return
        }
        if (connection.deleteSurroundingText(record.committedText.length, 0)) {
            undoRecord = null
            lastCommittedText = ""
            blockedReason = getString(R.string.ime_undone)
            mode = Mode.READY
        } else {
            blockedReason = getString(R.string.ime_undo_unavailable)
        }
        render()
    }

    private fun refreshAvailability(info: EditorInfo? = currentInputEditorInfo) {
        if (!::statusText.isInitialized) return
        val currentInfo = info
        editorIdentity = currentInfo?.toIdentity()
        mode = when {
            currentInfo == null || !ImeEditorPolicy.supportsDictation(currentInfo.inputType) -> {
                blockedReason = getString(R.string.ime_unsupported_editor)
                Mode.BLOCKED
            }
            ImeEditorPolicy.isSensitive(currentInfo.inputType, currentInfo.imeOptions) -> {
                blockedReason = getString(R.string.ime_sensitive_editor)
                Mode.BLOCKED
            }
            checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
                PackageManager.PERMISSION_GRANTED -> {
                blockedReason = getString(R.string.ime_permission_required)
                Mode.NEEDS_PERMISSION
            }
            coordinator.speechEngine.state == SpeechToTextEngine.State.RECORDING -> Mode.RECORDING
            coordinator.speechEngine.state == SpeechToTextEngine.State.FINALIZING -> Mode.PROCESSING
            coordinator.cleanupEngine.state == CleanupState.GENERATING ||
                coordinator.cleanupEngine.state == CleanupState.UNLOADING -> Mode.PROCESSING
            coordinator.speechEngine.state == SpeechToTextEngine.State.READY &&
                coordinator.cleanupEngine.state == CleanupState.READY -> {
                if (undoRecord != null) Mode.COMMITTED else Mode.READY
            }
            coordinator.speechEngine.state == SpeechToTextEngine.State.LOADING ||
                coordinator.cleanupEngine.state == CleanupState.LOADING -> Mode.LOADING
            else -> Mode.NEEDS_MODELS
        }
        render()
    }

    private fun render() {
        if (!::statusText.isInitialized) return
        statusText.setText(
            when (mode) {
                Mode.BLOCKED -> R.string.ime_status_blocked
                Mode.NEEDS_PERMISSION -> R.string.ime_status_setup_required
                Mode.NEEDS_MODELS -> R.string.ime_status_models_needed
                Mode.LOADING -> R.string.ime_status_loading
                Mode.READY -> R.string.ime_status_ready
                Mode.RECORDING -> R.string.ime_status_recording
                Mode.PROCESSING -> R.string.ime_status_processing
                Mode.COMMITTED -> R.string.ime_status_committed
                Mode.ERROR -> R.string.ime_status_error
            },
        )
        mainButton.setText(
            when (mode) {
                Mode.BLOCKED, Mode.NEEDS_PERMISSION -> R.string.ime_open_setup
                Mode.NEEDS_MODELS, Mode.ERROR -> R.string.ime_load_models
                Mode.READY, Mode.COMMITTED -> R.string.ime_start
                Mode.RECORDING -> R.string.ime_stop
                Mode.LOADING -> R.string.ime_loading
                Mode.PROCESSING -> R.string.ime_processing
            },
        )
        mainButton.isEnabled = mode != Mode.LOADING && mode != Mode.PROCESSING
        cancelButton.isEnabled = mode == Mode.RECORDING || mode == Mode.PROCESSING
        undoButton.isEnabled = undoRecord != null
        nextKeyboardButton.isEnabled = shouldOfferSwitchingToNextInputMethod()

        detailText.text = buildList {
            blockedReason?.takeIf(String::isNotBlank)?.let(::add)
            lastRawText.takeIf(String::isNotBlank)?.let {
                add(getString(R.string.ime_raw_detail, it))
            }
            lastCommittedText.takeIf(String::isNotBlank)?.let {
                add(getString(R.string.ime_committed_detail, it))
            }
        }.joinToString("\n")
        metricsText.text = lastMetrics
    }

    private fun openSetup() {
        startActivity(
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }

    private fun EditorInfo.toIdentity(): EditorIdentity = EditorIdentity(
        packageName = packageName,
        fieldId = fieldId,
        inputType = inputType,
    )

    private fun Throwable.rootMessage(): String {
        var root = this
        while (root.cause != null && root.cause !== root) root = root.cause!!
        return root.message ?: root.javaClass.simpleName
    }

    private enum class Mode {
        BLOCKED,
        NEEDS_PERMISSION,
        NEEDS_MODELS,
        LOADING,
        READY,
        RECORDING,
        PROCESSING,
        COMMITTED,
        ERROR,
    }
}
