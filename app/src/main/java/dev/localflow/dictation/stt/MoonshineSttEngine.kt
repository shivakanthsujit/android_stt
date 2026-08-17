package dev.localflow.dictation.stt

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import ai.moonshine.voice.AssetDownloader
import ai.moonshine.voice.JNI
import ai.moonshine.voice.ModelCache
import ai.moonshine.voice.ModelSpec
import ai.moonshine.voice.Transcriber
import ai.moonshine.voice.TranscriptEvent
import dev.localflow.dictation.LocalFlowLog
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Pixel-first microphone engine backed by Moonshine Small Streaming English.
 *
 * The model remains loaded between utterances, but AudioRecord is created by [start] and stopped
 * and released by [stop]. This is intentionally different from Moonshine's MicTranscriber helper,
 * which keeps its microphone capture thread open between utterances.
 */
class MoonshineSttEngine(
    context: Context,
    private val onProgress: (fraction: Float, file: String) -> Unit,
    private val onStateChanged: (SpeechToTextEngine.State) -> Unit,
    private val onError: (Throwable) -> Unit,
) : SpeechToTextEngine {
    private val appContext = context.applicationContext
    private val mainHandler = Handler(Looper.getMainLooper())
    private val worker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-moonshine").apply { isDaemon = true }
    }
    private val transcriptLock = Any()
    private val completedLines = mutableListOf<String>()
    private val audioQueue = LinkedBlockingQueue<FloatArray>()
    private val stopRequested = AtomicBoolean(false)

    private val modelSpec = ModelSpec.stt(
        MODEL_LANGUAGE,
        JNI.MOONSHINE_MODEL_ARCH_SMALL_STREAMING,
        false,
    )
    private val modelDirectory = ModelCache.directoryFor(appContext, modelSpec, null)
    private val transcriber = Transcriber().apply {
        addListener(::handleTranscriptEvent)
    }

    @Volatile
    override var state: SpeechToTextEngine.State = SpeechToTextEngine.State.UNLOADED
        private set

    private var currentPartial = ""
    private var partialHandler: (String) -> Unit = {}

    @Volatile
    private var stopCallback: ((Result<SttResult>) -> Unit)? = null

    @Volatile
    private var audioRecord: AudioRecord? = null

    @Volatile
    private var captureThread: Thread? = null

    @Volatile
    private var captureError: Throwable? = null

    @Volatile
    private var closed = false

    private var micStartedAtNs = 0L
    private var stopPressedAtNs = 0L

    override fun load(callback: (Result<Unit>) -> Unit) {
        if (state == SpeechToTextEngine.State.READY) {
            mainHandler.post { callback(Result.success(Unit)) }
            return
        }
        if (state != SpeechToTextEngine.State.UNLOADED &&
            state != SpeechToTextEngine.State.FAILED
        ) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("Cannot load while state is $state")))
            }
            return
        }

        updateState(SpeechToTextEngine.State.LOADING)
        worker.execute {
            runCatching {
                AssetDownloader().ensureModelPresent(
                    modelDirectory,
                    modelSpec,
                    ::reportDownloadProgress,
                )
                transcriber.loadFromFiles(
                    modelDirectory.absolutePath,
                    JNI.MOONSHINE_MODEL_ARCH_SMALL_STREAMING,
                )
            }.onSuccess {
                LocalFlowLog.info("Moonshine Small Streaming model ready")
                updateState(SpeechToTextEngine.State.READY)
            }.onFailure {
                LocalFlowLog.error("Moonshine model load failed", it)
                updateState(SpeechToTextEngine.State.FAILED)
            }.also { result -> mainHandler.post { callback(result) } }
        }
    }

    override fun start(
        onPartialTranscript: (String) -> Unit,
        callback: (Result<Unit>) -> Unit,
    ) {
        if (state != SpeechToTextEngine.State.READY) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("Model is not ready")))
            }
            return
        }
        if (appContext.checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            mainHandler.post {
                callback(Result.failure(SecurityException("Microphone permission is not granted")))
            }
            return
        }

        synchronized(transcriptLock) {
            completedLines.clear()
            currentPartial = ""
        }
        partialHandler = onPartialTranscript
        stopCallback = null
        captureError = null
        audioQueue.clear()
        stopRequested.set(false)
        updateState(SpeechToTextEngine.State.RECORDING)

        worker.execute { runRecording(callback) }
    }

    override fun stop(callback: (Result<SttResult>) -> Unit) {
        if (state != SpeechToTextEngine.State.RECORDING) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("No dictation is active")))
            }
            return
        }

        stopPressedAtNs = SystemClock.elapsedRealtimeNanos()
        stopCallback = callback
        updateState(SpeechToTextEngine.State.FINALIZING)
        stopRequested.set(true)

        // Stop recording immediately so Android releases the active microphone indicator. The
        // capture thread exits its blocking read, and the model worker drains only already-captured
        // audio before forcing Moonshine's final streaming pass.
        stopAudioCapture()
    }

    override fun close() {
        closed = true
        stopCallback = null
        stopRequested.set(true)
        stopAudioCapture()
        worker.execute {
            runCatching { transcriber.close() }
                .onFailure { LocalFlowLog.error("Moonshine close failed", it) }
        }
        worker.shutdown()
    }

    private fun runRecording(startCallback: (Result<Unit>) -> Unit) {
        var streamStarted = false
        var startReported = false
        var record: AudioRecord? = null
        try {
            transcriber.start()
            streamStarted = true

            record = createAudioRecord()
            audioRecord = record
            record.startRecording()
            if (record.recordingState != AudioRecord.RECORDSTATE_RECORDING) {
                throw IllegalStateException("Android did not start microphone recording")
            }

            micStartedAtNs = SystemClock.elapsedRealtimeNanos()
            startCaptureThread(record)
            startReported = true
            LocalFlowLog.info("Microphone transcription started")
            mainHandler.post { startCallback(Result.success(Unit)) }

            while (!stopRequested.get() || audioQueue.isNotEmpty() || captureThread?.isAlive == true) {
                audioQueue.poll(AUDIO_QUEUE_POLL_MS, TimeUnit.MILLISECONDS)?.let { audio ->
                    transcriber.addAudio(audio, SAMPLE_RATE)
                }
            }

            captureThread?.join(CAPTURE_JOIN_TIMEOUT_MS)
            captureError?.let { throw it }
            transcriber.stop()
            streamStarted = false
            finishStopSuccessfully()
        } catch (error: Throwable) {
            LocalFlowLog.error("Moonshine recording failed", error)
            if (streamStarted) {
                runCatching { transcriber.stop() }
                    .onFailure { LocalFlowLog.error("Moonshine stream stop failed", it) }
            }
            updateState(SpeechToTextEngine.State.FAILED)
            if (!startReported) {
                mainHandler.post { startCallback(Result.failure(error)) }
            } else {
                finishStopWithError(error)
            }
        } finally {
            stopRequested.set(true)
            stopAudioCapture()
            captureThread?.interrupt()
            runCatching { captureThread?.join(CAPTURE_JOIN_TIMEOUT_MS) }
            runCatching { record?.release() }
            captureThread = null
            audioRecord = null
            audioQueue.clear()
        }
    }

    private fun createAudioRecord(): AudioRecord {
        if (appContext.checkSelfPermission(Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            throw SecurityException("Microphone permission was revoked before recording started")
        }
        val format = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(SAMPLE_RATE)
            .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
            .build()
        val minimumBytes = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minimumBytes <= 0) {
            throw IllegalStateException("Android reported an invalid microphone buffer size")
        }
        val record = AudioRecord.Builder()
            .setAudioSource(MediaRecorder.AudioSource.MIC)
            .setAudioFormat(format)
            .setBufferSizeInBytes(maxOf(minimumBytes, AUDIO_RECORD_BUFFER_BYTES))
            .build()
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            throw IllegalStateException("Android failed to initialize the microphone")
        }
        return record
    }

    private fun startCaptureThread(record: AudioRecord) {
        captureThread = Thread(
            {
                val samples = ShortArray(AUDIO_CHUNK_SAMPLES)
                try {
                    while (!stopRequested.get() && !Thread.currentThread().isInterrupted) {
                        val read = record.read(
                            samples,
                            0,
                            samples.size,
                            AudioRecord.READ_BLOCKING,
                        )
                        if (read > 0) {
                            val audio = FloatArray(read) { index -> samples[index] / 32768.0f }
                            audioQueue.put(audio)
                        } else if (!stopRequested.get()) {
                            throw IllegalStateException("Microphone read failed with code $read")
                        }
                    }
                } catch (interrupted: InterruptedException) {
                    Thread.currentThread().interrupt()
                } catch (error: Throwable) {
                    if (!stopRequested.get()) {
                        captureError = error
                        stopRequested.set(true)
                    }
                }
            },
            "local-flow-audio-capture",
        ).apply {
            isDaemon = true
            start()
        }
    }

    private fun stopAudioCapture() {
        audioRecord?.let { record ->
            if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                runCatching { record.stop() }
                    .onSuccess { LocalFlowLog.info("Android microphone stopped") }
                    .onFailure { LocalFlowLog.error("Android microphone stop failed", it) }
            }
        }
    }

    private fun handleTranscriptEvent(event: TranscriptEvent) {
        when (event) {
            is TranscriptEvent.LineTextChanged -> {
                val transcript = synchronized(transcriptLock) {
                    currentPartial = event.line.text.orEmpty()
                    combinedTranscriptLocked()
                }
                mainHandler.post { partialHandler(transcript) }
            }

            is TranscriptEvent.LineCompleted -> {
                val transcript = synchronized(transcriptLock) {
                    event.line.text?.trim()?.takeIf(String::isNotEmpty)?.let(completedLines::add)
                    currentPartial = ""
                    combinedTranscriptLocked()
                }
                mainHandler.post { partialHandler(transcript) }
            }

            is TranscriptEvent.Error -> {
                captureError = event.cause
                stopRequested.set(true)
                stopAudioCapture()
            }

            else -> Unit
        }
    }

    private fun finishStopSuccessfully() {
        if (closed) {
            return
        }
        val callback = stopCallback
        stopCallback = null
        val finalAtNs = SystemClock.elapsedRealtimeNanos()
        val text = synchronized(transcriptLock) { combinedTranscriptLocked() }
        val result = SttResult(
            text = text,
            micStartedAtNs = micStartedAtNs,
            stopPressedAtNs = stopPressedAtNs,
            finalTextAtNs = finalAtNs,
        )
        LocalFlowLog.info(
            "Transcription finalized: recording=${result.recordingDurationMs}ms, " +
                "tail=${result.finalizationLatencyMs}ms",
        )
        updateState(SpeechToTextEngine.State.READY)
        mainHandler.post { callback?.invoke(Result.success(result)) }
    }

    private fun finishStopWithError(error: Throwable) {
        val callback = stopCallback
        stopCallback = null
        if (callback != null) {
            mainHandler.post { callback(Result.failure(error)) }
        } else if (!closed) {
            mainHandler.post { onError(error) }
        }
    }

    private fun reportDownloadProgress(
        relativePath: String,
        fileIndex: Int,
        totalFiles: Int,
        bytesDownloaded: Long,
        bytesTotal: Long,
    ) {
        val withinFile = if (bytesTotal > 0L) {
            bytesDownloaded.toFloat() / bytesTotal.toFloat()
        } else {
            0f
        }
        val fraction = if (totalFiles > 0) {
            ((fileIndex - 1) + withinFile) / totalFiles.toFloat()
        } else {
            withinFile
        }
        mainHandler.post { onProgress(fraction.coerceIn(0f, 1f), relativePath) }
    }

    private fun combinedTranscriptLocked(): String =
        (completedLines + currentPartial.trim().takeIf(String::isNotEmpty))
            .filterNotNull()
            .joinToString(separator = "\n")
            .trim()

    private fun updateState(newState: SpeechToTextEngine.State) {
        state = newState
        mainHandler.post { onStateChanged(newState) }
    }

    private companion object {
        const val MODEL_LANGUAGE = "en"
        const val SAMPLE_RATE = 16_000
        const val AUDIO_CHUNK_SAMPLES = 1_024
        const val AUDIO_RECORD_BUFFER_BYTES = 8_192
        const val AUDIO_QUEUE_POLL_MS = 20L
        const val CAPTURE_JOIN_TIMEOUT_MS = 1_000L
    }
}
