package dev.localflow.dictation

import android.content.Context
import android.os.SystemClock
import dev.localflow.dictation.cleanup.CleanupEngine
import dev.localflow.dictation.cleanup.CleanupLoadProgress
import dev.localflow.dictation.cleanup.CleanupPromptVariant
import dev.localflow.dictation.cleanup.CleanupResult
import dev.localflow.dictation.cleanup.CleanupState
import dev.localflow.dictation.cleanup.S1MiniCleanupEngine
import dev.localflow.dictation.stt.ParakeetLiveSttEngine
import dev.localflow.dictation.stt.SpeechToTextEngine
import dev.localflow.dictation.stt.SttResult
import java.util.concurrent.CopyOnWriteArraySet
import kotlin.coroutines.resume
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Application-scoped owner of the selected local STT and cleanup engines.
 *
 * The ordinary Activity and IME share these instances so opening one surface cannot allocate a
 * second copy of either model. The coordinator never owns an editor or logs transcript text.
 */
class DictationPipelineCoordinator(context: Context) {
    private val appContext = context.applicationContext
    private val stateListeners = CopyOnWriteArraySet<(SpeechToTextEngine.State) -> Unit>()
    private val loadMutex = Mutex()
    private val finishMutex = Mutex()
    private val closeScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)

    val speechEngine: SpeechToTextEngine = ParakeetLiveSttEngine(
        context = appContext,
        modelFile = IntegrationModels.parakeetFile(appContext),
        expectedModelSha256 = IntegrationModels.PARAKEET_SHA256,
        onStateChanged = ::publishSpeechState,
    )

    val cleanupEngine: CleanupEngine = S1MiniCleanupEngine(
        context = appContext,
        modelFile = IntegrationModels.cleanupFile(appContext),
        expectedModelSha256 = IntegrationModels.CLEANUP_SHA256,
    )

    fun addSpeechStateListener(listener: (SpeechToTextEngine.State) -> Unit) {
        stateListeners += listener
        listener(speechEngine.state)
    }

    fun removeSpeechStateListener(listener: (SpeechToTextEngine.State) -> Unit) {
        stateListeners -= listener
    }

    suspend fun loadModels(
        onCleanupProgress: (CleanupLoadProgress) -> Unit = {},
    ): PipelineLoadResult = loadMutex.withLock {
        val startedAtNs = SystemClock.elapsedRealtimeNanos()
        awaitSpeechLoad()
        val cleanupLoad = cleanupEngine.load(onCleanupProgress)
        PipelineLoadResult(
            completedAtNs = SystemClock.elapsedRealtimeNanos(),
            startedAtNs = startedAtNs,
            cleanupReusedLoadedRunner = cleanupLoad.reusedLoadedRunner,
        )
    }

    suspend fun startDictation(
        onPartialTranscript: (String) -> Unit = {},
    ) {
        suspendCancellableCoroutine { continuation ->
            speechEngine.start(onPartialTranscript) { result ->
                if (continuation.isActive) continuation.resume(result)
            }
        }.getOrThrow()
    }

    suspend fun stopAndClean(): DictationPipelineResult = finishMutex.withLock {
        val sttResult = suspendCancellableCoroutine<Result<SttResult>> { continuation ->
            speechEngine.stop { result ->
                if (continuation.isActive) continuation.resume(result)
            }
        }.getOrThrow()

        val rawText = sttResult.text.trim()
        if (rawText.isEmpty()) {
            return@withLock DictationPipelineResult(
                sttResult = sttResult,
                cleanupResult = null,
                committedText = "",
                cleanupError = null,
                completedAtNs = sttResult.finalTextAtNs,
            )
        }

        val cleanupAttempt = if (cleanupEngine.state == CleanupState.READY) {
            runCatching {
                cleanupEngine.cleanTranscript(
                    text = rawText,
                    promptVariant = CleanupPromptVariant.S1_MINI_NATIVE,
                    preferredBoundaryOffsets = sttResult.preferredCleanupBoundaryOffsets,
                )
            }
        } else {
            Result.failure(IllegalStateException("S1-mini is not ready"))
        }
        val cleanupResult = cleanupAttempt.getOrNull()
        DictationPipelineResult(
            sttResult = sttResult,
            cleanupResult = cleanupResult,
            committedText = cleanupResult?.cleanedText?.trim().orEmpty().ifEmpty { rawText },
            cleanupError = cleanupAttempt.exceptionOrNull()?.rootMessage(),
            completedAtNs = cleanupResult?.completedAtNs ?: SystemClock.elapsedRealtimeNanos(),
        )
    }

    fun cancelDictation(callback: (Result<Unit>) -> Unit = {}) {
        speechEngine.cancel(callback)
    }

    fun close() {
        speechEngine.close()
        closeScope.launch {
            runCatching { cleanupEngine.unload() }
                .onFailure { LocalFlowLog.error("Shared cleanup unload failed", it) }
        }
    }

    private suspend fun awaitSpeechLoad() {
        suspendCancellableCoroutine<Result<Unit>> { continuation ->
            speechEngine.load { result ->
                if (continuation.isActive) continuation.resume(result)
            }
        }.getOrThrow()
    }

    private fun publishSpeechState(state: SpeechToTextEngine.State) {
        stateListeners.forEach { listener -> listener(state) }
    }

    private fun Throwable.rootMessage(): String {
        var root = this
        while (root.cause != null && root.cause !== root) root = root.cause!!
        return root.message ?: root.javaClass.simpleName
    }
}

data class PipelineLoadResult(
    val startedAtNs: Long,
    val completedAtNs: Long,
    val cleanupReusedLoadedRunner: Boolean,
) {
    val durationMs: Long
        get() = (completedAtNs - startedAtNs).coerceAtLeast(0L) / 1_000_000L
}

data class DictationPipelineResult(
    val sttResult: SttResult,
    val cleanupResult: CleanupResult?,
    val committedText: String,
    val cleanupError: String?,
    val completedAtNs: Long,
) {
    val stopToCompletionMs: Long
        get() = (completedAtNs - sttResult.stopPressedAtNs).coerceAtLeast(0L) / 1_000_000L

    val usedCleanupFallback: Boolean
        get() = cleanupResult?.usedFallback == true
}
