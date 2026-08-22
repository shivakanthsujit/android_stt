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
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import org.json.JSONObject

/** Live cache-aware Parakeet transcription with an explicit project-owned microphone lifecycle. */
class ParakeetLiveSttEngine(
    context: Context,
    private val modelFile: File,
    private val expectedModelSha256: String,
    private val onStateChanged: (SpeechToTextEngine.State) -> Unit,
    private val onAudioLevel: (Float) -> Unit = {},
) : SpeechToTextEngine {
    private val appContext = context.applicationContext
    private val mainHandler = Handler(Looper.getMainLooper())
    private val worker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-parakeet").apply { isDaemon = true }
    }
    private val streamQueue = LinkedBlockingQueue<FloatArray>()
    private val streamLock = Any()
    private val streamingTranscript = StringBuilder()
    private val preferredCleanupBoundaries = mutableListOf<Int>()
    private val stopRequested = AtomicBoolean(false)
    private val streamingCancelled = AtomicBoolean(false)
    private val capturedSampleCount = AtomicInteger(0)

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
    private var streamingThread: Thread? = null

    @Volatile
    private var captureError: Throwable? = null

    @Volatile
    private var streamingError: Throwable? = null

    @Volatile
    private var closed = false

    private var micStartedAtNs = 0L
    private var stopPressedAtNs = 0L
    private var lastAudioLevelAtNs = 0L

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
                    displayName = "Parakeet Realtime EOU 120M Q4_K",
                )
                val abiVersion = ParakeetNative.nativeAbiVersion()
                require(abiVersion == EXPECTED_C_API_ABI) {
                    "Expected Parakeet C API ABI $EXPECTED_C_API_ABI, found $abiVersion"
                }
                ParakeetNative.nativeLoad(modelFile.absolutePath).also { handle ->
                    require(handle != 0L) { "Parakeet returned a null model context" }
                    nativeContext = handle
                }
                // Reject an offline-only GGUF before the user opens the microphone.
                val probe = ParakeetNative.nativeStreamBegin(nativeContext)
                require(probe != 0L) { "Parakeet did not create a streaming session" }
                ParakeetNative.nativeStreamFree(probe)
            }.onSuccess {
                LocalFlowLog.info("Parakeet Realtime EOU 120M Q4_K model ready")
                updateState(SpeechToTextEngine.State.READY)
            }.onFailure { error ->
                val handle = nativeContext
                nativeContext = 0L
                if (handle != 0L) runCatching { ParakeetNative.nativeFree(handle) }
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
            val result = runCatching {
                resetUtteranceState()
                val streamHandle = ParakeetNative.nativeStreamBegin(nativeContext)
                require(streamHandle != 0L) { "Parakeet did not create a streaming session" }
                startStreamingThread(streamHandle, onPartialTranscript)

                val record = createAudioRecord()
                audioRecord = record
                record.startRecording()
                check(record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                    "Android did not start microphone recording"
                }
                micStartedAtNs = SystemClock.elapsedRealtimeNanos()
                startCaptureThread(record)
                updateState(SpeechToTextEngine.State.RECORDING)
                LocalFlowLog.info("Parakeet streaming microphone capture started")
            }
            result.onFailure { error ->
                streamingCancelled.set(true)
                stopRequested.set(true)
                stopAudioCapture()
                streamQueue.clear()
                streamQueue.offer(END_OF_STREAM)
                runCatching { streamingThread?.join(STREAM_JOIN_TIMEOUT_MS) }
                runCatching { audioRecord?.release() }
                audioRecord = null
                captureThread = null
                streamingThread = null
                updateState(SpeechToTextEngine.State.READY)
                LocalFlowLog.error("Parakeet microphone start failed", error)
            }
            mainHandler.post { callback(result.map { Unit }) }
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

        // Stop synchronously so Android releases the microphone indicator at the Stop tap. The
        // stream worker drains already-captured audio and flushes only the undecoded tail.
        stopAudioCapture()
        worker.execute {
            val result = runCatching {
                joinThread(captureThread, CAPTURE_JOIN_TIMEOUT_MS, "microphone capture")
                captureError?.let { throw it }
                joinThread(streamingThread, STREAM_JOIN_TIMEOUT_MS, "streaming transcription")
                streamingError?.let { throw it }
                require(capturedSampleCount.get() > 0) { "No microphone audio was captured" }
                val finalAtNs = SystemClock.elapsedRealtimeNanos()
                val (text, boundaries) = synchronized(streamLock) {
                    val untrimmed = streamingTranscript.toString()
                    val leadingWhitespace = untrimmed.indexOfFirst { !it.isWhitespace() }
                        .let { index -> if (index >= 0) index else untrimmed.length }
                    val trimmed = untrimmed.trim()
                    trimmed to preferredCleanupBoundaries
                        .map { offset -> offset - leadingWhitespace }
                        .filter { offset -> offset in 1 until trimmed.length }
                }
                SttResult(
                    text = text,
                    micStartedAtNs = micStartedAtNs,
                    stopPressedAtNs = stopPressedAtNs,
                    finalTextAtNs = finalAtNs,
                    preferredCleanupBoundaryOffsets = boundaries,
                )
            }
            releaseUtteranceResources()
            if (!closed) {
                updateState(
                    if (result.isSuccess) SpeechToTextEngine.State.READY
                    else SpeechToTextEngine.State.FAILED,
                )
            }
            result.onSuccess { stt ->
                LocalFlowLog.info(
                    "Parakeet stream finalized: recording=${stt.recordingDurationMs}ms, " +
                        "tail=${stt.finalizationLatencyMs}ms",
                )
            }.onFailure { error -> LocalFlowLog.error("Parakeet finalization failed", error) }
            mainHandler.post { callback(result) }
        }
    }

    override fun cancel(callback: (Result<Unit>) -> Unit) {
        if (state != SpeechToTextEngine.State.RECORDING) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("No dictation is active")))
            }
            return
        }

        streamingCancelled.set(true)
        stopRequested.set(true)
        updateState(SpeechToTextEngine.State.FINALIZING)
        stopAudioCapture()
        worker.execute {
            val result = runCatching {
                joinThread(captureThread, CAPTURE_JOIN_TIMEOUT_MS, "microphone capture")
                streamQueue.clear()
                streamQueue.offer(END_OF_STREAM)
                joinThread(streamingThread, STREAM_JOIN_TIMEOUT_MS, "streaming cancellation")
                Unit
            }
            releaseUtteranceResources()
            if (!closed) {
                updateState(
                    if (result.isSuccess) SpeechToTextEngine.State.READY
                    else SpeechToTextEngine.State.FAILED,
                )
            }
            result.onSuccess { LocalFlowLog.info("Parakeet dictation canceled before cleanup") }
                .onFailure { LocalFlowLog.error("Parakeet cancellation failed", it) }
            mainHandler.post { callback(result) }
        }
    }

    override fun close() {
        closed = true
        streamingCancelled.set(true)
        stopRequested.set(true)
        stopAudioCapture()
        streamQueue.clear()
        streamQueue.offer(END_OF_STREAM)
        val handle = nativeContext
        nativeContext = 0L
        worker.execute {
            runCatching { captureThread?.join(CAPTURE_JOIN_TIMEOUT_MS) }
            runCatching { streamingThread?.join(STREAM_JOIN_TIMEOUT_MS) }
            runCatching { audioRecord?.release() }
            if (handle != 0L) ParakeetNative.nativeFree(handle)
        }
        worker.shutdown()
    }

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
                            capturedSampleCount.addAndGet(read)
                            publishAudioLevelIfDue(chunk)
                            streamQueue.put(chunk)
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
                } finally {
                    streamQueue.offer(END_OF_STREAM)
                }
            },
            "local-flow-parakeet-capture",
        ).apply {
            isDaemon = true
            start()
        }
    }

    private fun startStreamingThread(
        streamHandle: Long,
        onPartialTranscript: (String) -> Unit,
    ) {
        streamingThread = Thread(
            {
                try {
                    while (true) {
                        val chunk = streamQueue.take()
                        if (chunk === END_OF_STREAM) break
                        if (streamingCancelled.get()) continue
                        val update = ParakeetNative.nativeStreamFeedJson(streamHandle, chunk)
                        if (!streamingCancelled.get()) {
                            applyStreamingUpdate(update, onPartialTranscript)
                        }
                    }
                    if (!streamingCancelled.get()) {
                        applyStreamingUpdate(
                            ParakeetNative.nativeStreamFinalizeJson(streamHandle),
                            onPartialTranscript,
                        )
                    }
                } catch (error: Throwable) {
                    if (!streamingCancelled.get()) {
                        streamingError = error
                        stopRequested.set(true)
                        stopAudioCapture()
                    }
                } finally {
                    ParakeetNative.nativeStreamFree(streamHandle)
                }
            },
            "local-flow-parakeet-stream",
        ).apply {
            isDaemon = true
            start()
        }
    }

    private fun applyStreamingUpdate(
        updateJson: String,
        onPartialTranscript: (String) -> Unit,
    ) {
        val update = JSONObject(updateJson)
        val delta = update.optString("text")
        val hasEou = update.optInt("eou") != 0
        val transcript = synchronized(streamLock) {
            if (delta.isNotEmpty()) streamingTranscript.append(delta)
            if (hasEou) {
                val offset = streamingTranscript.length
                if (offset > 0 && preferredCleanupBoundaries.lastOrNull() != offset) {
                    preferredCleanupBoundaries += offset
                }
            }
            streamingTranscript.toString()
        }
        if (delta.isNotEmpty()) {
            mainHandler.post {
                if (
                    state == SpeechToTextEngine.State.RECORDING ||
                    state == SpeechToTextEngine.State.FINALIZING
                ) {
                    onPartialTranscript(transcript)
                }
            }
        }
    }

    private fun resetUtteranceState() {
        streamQueue.clear()
        stopRequested.set(false)
        streamingCancelled.set(false)
        capturedSampleCount.set(0)
        captureError = null
        streamingError = null
        lastAudioLevelAtNs = 0L
        synchronized(streamLock) {
            streamingTranscript.clear()
            preferredCleanupBoundaries.clear()
        }
    }

    private fun releaseUtteranceResources() {
        runCatching { audioRecord?.release() }
        audioRecord = null
        captureThread = null
        streamingThread = null
        streamQueue.clear()
    }

    private fun joinThread(thread: Thread?, timeoutMs: Long, label: String) {
        thread?.join(timeoutMs)
        check(thread?.isAlive != true) { "Timed out waiting for $label" }
    }

    private fun stopAudioCapture() {
        audioRecord?.let { record ->
            if (record.recordingState == AudioRecord.RECORDSTATE_RECORDING) {
                runCatching { record.stop() }
                    .onSuccess { LocalFlowLog.info("Android microphone stopped") }
                    .onFailure { LocalFlowLog.error("Android microphone stop failed", it) }
            }
        }
        mainHandler.post { onAudioLevel(0f) }
    }

    private fun publishAudioLevelIfDue(chunk: FloatArray) {
        val nowNs = SystemClock.elapsedRealtimeNanos()
        if (nowNs - lastAudioLevelAtNs < AUDIO_LEVEL_INTERVAL_NS) return
        lastAudioLevelAtNs = nowNs
        val level = AudioLevelMeter.displayLevel(chunk)
        mainHandler.post {
            if (state == SpeechToTextEngine.State.RECORDING) onAudioLevel(level)
        }
    }

    private fun updateState(newState: SpeechToTextEngine.State) {
        state = newState
        mainHandler.post { onStateChanged(newState) }
    }

    private companion object {
        const val EXPECTED_C_API_ABI = 6
        const val SAMPLE_RATE = 16_000
        const val AUDIO_CHUNK_SAMPLES = 1_024
        const val AUDIO_RECORD_BUFFER_BYTES = 8_192
        const val CAPTURE_JOIN_TIMEOUT_MS = 1_000L
        const val STREAM_JOIN_TIMEOUT_MS = 30_000L
        const val AUDIO_LEVEL_INTERVAL_NS = 50_000_000L
        val END_OF_STREAM = FloatArray(0)
    }
}
