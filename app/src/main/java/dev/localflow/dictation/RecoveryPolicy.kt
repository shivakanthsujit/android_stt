package dev.localflow.dictation

/** Pipeline boundary where a user-visible failure occurred. */
enum class PipelineFailureStage {
    MODEL_LOAD,
    STT,
    CLEANUP,
    EDITOR_COMMIT,
}

/** Stable failure categories used to choose one safe recovery action. */
enum class PipelineFailureKind {
    PERMISSION,
    MODEL_ARTIFACT,
    MODEL_LOAD,
    STT,
    CLEANUP,
    EDITOR_COMMIT,
}

enum class RecoveryAction {
    NONE,
    OPEN_SETUP,
    LOAD_MODELS,
    DISMISS,
}

data class RecoveryDirective(
    val action: RecoveryAction,
    val preserveRawTranscript: Boolean,
    val mayRetryEditorCommit: Boolean = false,
)

/** Fail-safe recovery rules shared by the Activity and daily-driver IME. */
object RecoveryPolicy {
    fun classify(stage: PipelineFailureStage, error: Throwable): PipelineFailureKind = when {
        error.hasCause<SecurityException>() -> PipelineFailureKind.PERMISSION
        error.hasCause<ModelArtifactException>() -> PipelineFailureKind.MODEL_ARTIFACT
        stage == PipelineFailureStage.MODEL_LOAD -> PipelineFailureKind.MODEL_LOAD
        stage == PipelineFailureStage.STT -> PipelineFailureKind.STT
        stage == PipelineFailureStage.CLEANUP -> PipelineFailureKind.CLEANUP
        else -> PipelineFailureKind.EDITOR_COMMIT
    }

    fun directive(kind: PipelineFailureKind): RecoveryDirective = when (kind) {
        PipelineFailureKind.PERMISSION,
        PipelineFailureKind.MODEL_ARTIFACT -> RecoveryDirective(
            action = RecoveryAction.OPEN_SETUP,
            preserveRawTranscript = true,
        )
        PipelineFailureKind.MODEL_LOAD,
        PipelineFailureKind.STT,
        PipelineFailureKind.CLEANUP -> RecoveryDirective(
            action = RecoveryAction.LOAD_MODELS,
            preserveRawTranscript = true,
        )
        PipelineFailureKind.EDITOR_COMMIT -> RecoveryDirective(
            action = RecoveryAction.DISMISS,
            preserveRawTranscript = true,
            mayRetryEditorCommit = false,
        )
    }

    private inline fun <reified T : Throwable> Throwable.hasCause(): Boolean {
        var current: Throwable? = this
        while (current != null) {
            if (current is T) return true
            val next = current.cause
            current = if (next === current) null else next
        }
        return false
    }
}
