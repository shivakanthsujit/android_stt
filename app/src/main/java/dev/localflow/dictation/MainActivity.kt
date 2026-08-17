package dev.localflow.dictation

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.SystemClock
import android.view.View
import android.widget.Button
import android.widget.TextView
import dev.localflow.dictation.stt.MoonshineSttEngine
import dev.localflow.dictation.stt.SpeechToTextEngine

class MainActivity : Activity() {
    private lateinit var statusText: TextView
    private lateinit var transcriptText: TextView
    private lateinit var metricsText: TextView
    private lateinit var loadModelButton: Button
    private lateinit var dictationButton: Button

    private var modelLoadStartedAtNs = 0L
    private var modelLoadDurationMs: Long? = null
    private var startAfterPermissionGrant = false

    private val engine by lazy {
        MoonshineSttEngine(
            context = applicationContext,
            onProgress = ::showDownloadProgress,
            onStateChanged = ::renderState,
            onError = ::showError,
        )
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        transcriptText = findViewById(R.id.transcriptText)
        metricsText = findViewById(R.id.metricsText)
        loadModelButton = findViewById(R.id.loadModelButton)
        dictationButton = findViewById(R.id.dictationButton)

        loadModelButton.setOnClickListener { loadModel() }
        dictationButton.setOnClickListener {
            when (engine.state) {
                SpeechToTextEngine.State.READY -> startDictation()
                SpeechToTextEngine.State.RECORDING -> stopDictation()
                else -> Unit
            }
        }

        renderState(SpeechToTextEngine.State.UNLOADED)
        statusText.setText(R.string.status_model_not_loaded)
    }

    override fun onDestroy() {
        engine.close()
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
                metricsText.text = getString(R.string.metric_model_load, modelLoadDurationMs)
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
        transcriptText.text = ""
        metricsText.text = modelLoadDurationMs?.let {
            getString(R.string.metric_model_load, it)
        } ?: getString(R.string.metrics_model_ready)
        statusText.setText(R.string.status_opening_microphone)
        dictationButton.isEnabled = false
        engine.start(
            onPartialTranscript = { transcript ->
                transcriptText.text = transcript.ifBlank { getString(R.string.transcript_listening) }
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
                transcriptText.text = sttResult.text.ifBlank {
                    getString(R.string.transcript_no_speech)
                }
                metricsText.text = buildString {
                    modelLoadDurationMs?.let {
                        appendLine(getString(R.string.metric_model_load, it))
                    }
                    appendLine(getString(R.string.metric_recording, sttResult.recordingDurationMs))
                    append(getString(R.string.metric_stt_tail, sttResult.finalizationLatencyMs))
                }
                statusText.setText(R.string.status_finished)
            }.onFailure(::showError)
        }
    }

    private fun showDownloadProgress(fraction: Float, file: String) {
        val percent = (fraction.coerceIn(0f, 1f) * 100f).toInt()
        val displayFile = file.substringAfterLast('/').takeIf(String::isNotBlank)
        statusText.text = if (displayFile == null) {
            getString(R.string.status_downloading_model, percent)
        } else {
            getString(R.string.status_downloading_model_file, percent, displayFile)
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
    }

    private fun showError(error: Throwable) {
        LocalFlowLog.error("Benchmark UI error", error)
        statusText.text = getString(R.string.status_error, error.rootMessage())
        renderState(engine.state)
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
