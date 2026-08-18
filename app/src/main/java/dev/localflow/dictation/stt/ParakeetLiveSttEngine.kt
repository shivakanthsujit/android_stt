package dev.localflow.dictation.stt

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import dev.localflow.dictation.IntegrationModels
import dev.localflow.dictation.LocalFlowLog
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Live microphone integration for the selected Parakeet 110M Q4_K artifact.
 *
 * The current pinned Parakeet model is an offline TDT/CTC model. Audio is captured locally while
 * dictation is active and a single final inference is run after Stop. No partial transcript is
 * fabricated. A cache-aware streaming model remains a later, independently measured STT option.
 */
class ParakeetLiveSttEngine(
    context: Context,
    private val modelFile: File,
    private val expectedModelSha256: String,
    private val onStateChanged: (SpeechToTextEngine.State) -> Unit,
) : SpeechToTextEngine {
    private val appContext = context.applicationContext
    private val mainHandler = Handler(Looper.getMainLooper())
    private val worker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-parakeet").apply { isDaemon = true }
    }
    private val captureLock = Any()
    private val capturedChunks = mutableListOf<FloatArray>()
    private val stopRequested = AtomicBoolean(false)

    @Volatile
    override var state = SpeechToTextEngine.State.UNLOADED
        private set

    @Volatile
    private var nativeContext = 0L

    @Volatile
    private var audioRecord: AudioRecord? = null

    @Volatile
    private var captureThread: Thread? = null

    @Volatile
    private var captureError: Throwable? = null

    @Volatile
    private var closed = false

    private var capturedSampleCount = 0
    private var micStartedAtNs = 0L
    private var stopPressedAtNs = 0L

    override fun load(callback: (Result<Unit>) -> Unit) {
        if (state == SpeechToTextEngine.State.READY) {
            mainHandler.post { callback(Result.success(Unit)) }
            return
        }
        if (state != SpeechToTextEngine.State.UNLOADED && state != SpeechToTextEngine.State.FAILED) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("Cannot load while state is $state")))
            }
            return
        }

        updateState(SpeechToTextEngine.State.LOADING)
        worker.execute {
            runCatching {
                IntegrationModels.requireVerified(
                    file = modelFile,
                    expectedSha256 = expectedModelSha256,
                    displayName = "Parakeet Q4_K",
                )
                val abiVersion = ParakeetNative.nativeAbiVersion()
                require(abiVersion == EXPECTED_C_API_ABI) {
                    "Expected Parakeet C API ABI $EXPECTED_C_API_ABI, found $abiVersion"
                }
                ParakeetNative.nativeLoad(modelFile.absolutePath).also { handle ->
                    require(handle != 0L) { "Parakeet returned a null model context" }
                    nativeContext = handle
                }
            }.onSuccess {
                LocalFlowLog.info("Parakeet 110M Q4_K model ready")
                updateState(SpeechToTextEngine.State.READY)
            }.onFailure { error ->
                LocalFlowLog.error("Parakeet model load failed", error)
                updateState(SpeechToTextEngine.State.FAILED)
            }.also { result -> mainHandler.post { callback(result.map { Unit }) } }
        }
    }

    override fun start(
        onPartialTranscript: (String) -> Unit,
        callback: (Result<Unit>) -> Unit,
    ) {
        if (state != SpeechToTextEngine.State.READY || nativeContext == 0L) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("Parakeet model is not ready")))
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

        worker.execute {
            runCatching {
                synchronized(captureLock) {
                    capturedChunks.clear()
                    capturedSampleCount = 0
                }
                captureError = null
                stopRequested.set(false)
                val record = createAudioRecord()
                audioRecord = record
                record.startRecording()
                check(record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    "Android did not start microphone recording"
                }
                micStartedAtNs = SystemClock.elapsedRealtimeNanos()
                startCaptureThread(record)
                updateState(SpeechToTextEngine.State.RECORDING)
                LocalFlowLog.info("Parakeet microphone capture started")
            }.onFailure { error ->
                stopRequested.set(true)
                stopAudioCapture()
                runCatching { audioRecord?.release() }
                audioRecord = null
                updateState(SpeechToTextEngine.State.READY)
                LocalFlowLog.error("Parakeet microphone start failed", error)
            }.also { result -> mainHandler.post { callback(result.map { Unit }) } }
        }
    }

    override fun stop(callback: (Result<SttResult>) -> Unit) {
        if (state != SpeechToTextEngine.State.RECORDING) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("No dictation is active")))
            }
            return
        }

        stopPressedAtNs = SystemClock.elapsedRealtimeNanos()
        stopRequested.set(true)
        updateState(SpeechToTextEngine.State.FINALIZING)

        // This is synchronous so Android releases the microphone indicator at the Stop tap. Only
        // already-captured samples are copied and transcribed by the background worker afterward.
        stopAudioCapture()
        worker.execute {
            val result = runCatching {
                captureThread?.join(CAPTURE_JOIN_TIMEOUT_MS)
                captureError?.let { throw it }
                val samples = combinedSamples()
                require(samples.isNotEmpty()) { "No microphone audio was captured" }
                val text = ParakeetNative.nativeTranscribePcm(
                    nativeContext,
                    samples,
                    SAMPLE_RATE,
                    DECODER_DEFAULT,
                ).trim()
                val finalAtNs = SystemClock.elapsedRealtimeNanos()
                SttResult(
                    text = text,
                    micStartedAtNs = micStartedAtNs,
                    stopPressedAtNs = stopPressedAtNs,
                    finalTextAtNs = finalAtNs,
                )
            }
            runCatching { audioRecord?.release() }
            audioRecord = null
            captureThread = null
            synchronized(captureLock) {
                capturedChunks.clear()
                capturedSampleCount = 0
            }
            if (!closed) updateState(SpeechToTextEngine.State.READY)
            result.onSuccess { stt ->
                LocalFlowLog.info(
                    "Parakeet finalized: recording=${stt.recordingDurationMs}ms, " +
                        "tail=${stt.finalizationLatencyMs}ms",
                )
            }.onFailure { error -> LocalFlowLog.error("Parakeet finalization failed", error) }
            mainHandler.post { callback(result) }
        }
    }

    override fun close() {
        closed = true
        stopRequested.set(true)
        stopAudioCapture()
        captureThread?.interrupt()
        val handle = nativeContext
        nativeContext = 0L
        worker.execute {
            runCatching { captureThread?.join(CAPTURE_JOIN_TIMEOUT_MS) }
            runCatching { audioRecord?.release() }
            if (handle != 0L) ParakeetNative.nativeFree(handle)
        }
        worker.shutdown()
    }

    // start() checks RECORD_AUDIO immediately before this worker call. Construction still lives
    // inside runCatching so a permission revocation race is returned to the UI instead of crashing.
    @SuppressLint("MissingPermission")
    private fun createAudioRecord(): AudioRecord {
        val minimumBytes = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        check(minimumBytes > 0) { "Android reported an invalid microphone buffer size" }
        val format = AudioFormat.Builder()
            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
            .setSampleRate(SAMPLE_RATE)
            .setChannelMask(AudioFormat.CHANNEL_IN_MONO)
            .build()
        return AudioRecord.Builder()
            .setAudioSource(MediaRecorder.AudioSource.MIC)
            .setAudioFormat(format)
            .setBufferSizeInBytes(maxOf(minimumBytes, AUDIO_RECORD_BUFFER_BYTES))
            .build()
            .also { record ->
                if (record.state != AudioRecord.STATE_INITIALIZED) {
                    record.release()
                    error("Android failed to initialize the microphone")
                }
            }
    }

    private fun startCaptureThread(record: AudioRecord) {
        captureThread = Thread(
            {
                val shortSamples = ShortArray(AUDIO_CHUNK_SAMPLES)
                try {
                    while (!stopRequested.get() && !Thread.currentThread().isInterrupted) {
                        val read = record.read(
                            shortSamples,
                            0,
                            shortSamples.size,
                            AudioRecord.READ_BLOCKING,
                        )
                        if (read > 0) {
                            val chunk = FloatArray(read) { index ->
                                shortSamples[index] / 32768.0f
                            }
                            synchronized(captureLock) {
                                capturedChunks += chunk
                                capturedSampleCount += read
                            }
                        } else if (!stopRequested.get()) {
                            error("Microphone read failed with code $read")
                        }
                    }
                } catch (error: Throwable) {
                    if (!stopRequested.get()) {
                        captureError = error
                        stopRequested.set(true)
                        stopAudioCapture()
                    }
                }
            },
            "local-flow-parakeet-capture",
        ).apply {
            isDaemon = true
            start()
        }
    }

    private fun combinedSamples(): FloatArray = synchronized(captureLock) {
        FloatArray(capturedSampleCount).also { result ->
            var offset = 0
            capturedChunks.forEach { chunk ->
                chunk.copyInto(result, destinationOffset = offset)
                offset += chunk.size
            }
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

    private fun updateState(newState: SpeechToTextEngine.State) {
        state = newState
        mainHandler.post { onStateChanged(newState) }
    }

    private companion object {
        const val EXPECTED_C_API_ABI = 6
        const val DECODER_DEFAULT = 0
        const val SAMPLE_RATE = 16_000
        const val AUDIO_CHUNK_SAMPLES = 1_024
        const val AUDIO_RECORD_BUFFER_BYTES = 8_192
        const val CAPTURE_JOIN_TIMEOUT_MS = 1_000L
    }
}
