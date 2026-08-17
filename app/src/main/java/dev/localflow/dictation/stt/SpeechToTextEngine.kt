package dev.localflow.dictation.stt

/**
 * Boundary between the benchmark UI and an on-device speech recognizer.
 *
 * Implementations own their audio capture and must never upload audio or text.
 */
interface SpeechToTextEngine {
    val state: State

    fun load(callback: (Result<Unit>) -> Unit)

    fun start(
        onPartialTranscript: (String) -> Unit,
        callback: (Result<Unit>) -> Unit,
    )

    fun stop(callback: (Result<SttResult>) -> Unit)

    fun close()

    enum class State {
        UNLOADED,
        LOADING,
        READY,
        RECORDING,
        FINALIZING,
        FAILED,
    }
}

