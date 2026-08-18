package dev.localflow.dictation.stt.benchmark

import android.os.Handler
import android.os.Looper
import android.os.Process
import android.os.SystemClock
import dev.localflow.dictation.stt.FileSttBenchmarkEngine
import dev.localflow.dictation.stt.FileSttBenchmarkResult
import dev.localflow.dictation.stt.ParakeetNative
import dev.localflow.dictation.stt.SpeechToTextEngine
import java.io.File
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors

internal class ParakeetSttEngine(
    private val modelFile: File,
    modelVariant: String,
    private val decoder: Int = DECODER_DEFAULT,
) : SpeechToTextEngine, FileSttBenchmarkEngine {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val worker: ExecutorService = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "local-flow-parakeet").apply { isDaemon = true }
    }

    @Volatile
    override var state = SpeechToTextEngine.State.UNLOADED
        private set

    override val benchmarkEngineId = "parakeet-cpp-0.5.0-tdt-ctc-110m-$modelVariant"

    @Volatile
    private var nativeContext = 0L

    override fun load(callback: (Result<Unit>) -> Unit) {
        if (state != SpeechToTextEngine.State.UNLOADED && state != SpeechToTextEngine.State.FAILED) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("Cannot load while state is $state")))
            }
            return
        }
        state = SpeechToTextEngine.State.LOADING
        worker.execute {
            runCatching {
                require(modelFile.isFile) { "Missing Parakeet model: ${modelFile.name}" }
                val abiVersion = ParakeetNative.nativeAbiVersion()
                require(abiVersion == EXPECTED_C_API_ABI) {
                    "Expected Parakeet C API ABI $EXPECTED_C_API_ABI, found $abiVersion"
                }
                ParakeetNative.nativeLoad(modelFile.absolutePath).also { handle ->
                    require(handle != 0L) { "Parakeet returned a null model context" }
                    nativeContext = handle
                }
            }.onSuccess {
                state = SpeechToTextEngine.State.READY
            }.onFailure {
                state = SpeechToTextEngine.State.FAILED
            }.also { result -> mainHandler.post { callback(result.map { Unit }) } }
        }
    }

    override fun transcribePcm(
        samples: FloatArray,
        sampleRate: Int,
        callback: (Result<FileSttBenchmarkResult>) -> Unit,
    ) {
        if (state != SpeechToTextEngine.State.READY || nativeContext == 0L) {
            mainHandler.post {
                callback(Result.failure(IllegalStateException("Parakeet model is not ready")))
            }
            return
        }
        worker.execute {
            runCatching {
                val cpuStartedAtMs = Process.getElapsedCpuTime()
                val startedAtNs = SystemClock.elapsedRealtimeNanos()
                val text = ParakeetNative.nativeTranscribePcm(
                    nativeContext,
                    samples,
                    sampleRate,
                    decoder,
                )
                val finishedAtNs = SystemClock.elapsedRealtimeNanos()
                val cpuFinishedAtMs = Process.getElapsedCpuTime()
                FileSttBenchmarkResult(
                    text = text.trim(),
                    inferenceDurationNs = finishedAtNs - startedAtNs,
                    processCpuDurationMs = (cpuFinishedAtMs - cpuStartedAtMs).coerceAtLeast(0L),
                )
            }.also { result -> mainHandler.post { callback(result) } }
        }
    }

    override fun start(
        onPartialTranscript: (String) -> Unit,
        callback: (Result<Unit>) -> Unit,
    ) {
        mainHandler.post {
            callback(Result.failure(UnsupportedOperationException("File benchmark engine only")))
        }
    }

    override fun stop(callback: (Result<dev.localflow.dictation.stt.SttResult>) -> Unit) {
        mainHandler.post {
            callback(Result.failure(UnsupportedOperationException("File benchmark engine only")))
        }
    }

    override fun close() {
        val handle = nativeContext
        nativeContext = 0L
        if (handle != 0L) {
            worker.execute { ParakeetNative.nativeFree(handle) }
        }
        worker.shutdown()
    }

    private companion object {
        const val EXPECTED_C_API_ABI = 6
        const val DECODER_DEFAULT = 0
    }
}
