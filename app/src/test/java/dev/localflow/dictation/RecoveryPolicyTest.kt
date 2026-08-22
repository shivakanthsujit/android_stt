package dev.localflow.dictation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RecoveryPolicyTest {
    @Test
    fun permissionFailureAlwaysOpensSetupAndPreservesVisibleRawText() {
        val kind = RecoveryPolicy.classify(
            PipelineFailureStage.STT,
            IllegalStateException("capture failed", SecurityException("revoked")),
        )

        assertEquals(PipelineFailureKind.PERMISSION, kind)
        assertEquals(RecoveryAction.OPEN_SETUP, RecoveryPolicy.directive(kind).action)
        assertTrue(RecoveryPolicy.directive(kind).preserveRawTranscript)
    }

    @Test
    fun missingOrInvalidArtifactOpensSetupInsteadOfLoopingModelLoad() {
        val missing = RecoveryPolicy.classify(
            PipelineFailureStage.MODEL_LOAD,
            MissingModelArtifactException("missing"),
        )
        val invalid = RecoveryPolicy.classify(
            PipelineFailureStage.MODEL_LOAD,
            InvalidModelArtifactException("invalid"),
        )

        assertEquals(PipelineFailureKind.MODEL_ARTIFACT, missing)
        assertEquals(PipelineFailureKind.MODEL_ARTIFACT, invalid)
        assertEquals(RecoveryAction.OPEN_SETUP, RecoveryPolicy.directive(missing).action)
    }

    @Test
    fun runtimeModelSttAndCleanupFailuresReloadModelsWithoutDiscardingRawText() {
        listOf(
            PipelineFailureStage.MODEL_LOAD to PipelineFailureKind.MODEL_LOAD,
            PipelineFailureStage.STT to PipelineFailureKind.STT,
            PipelineFailureStage.CLEANUP to PipelineFailureKind.CLEANUP,
        ).forEach { (stage, expectedKind) ->
            val kind = RecoveryPolicy.classify(stage, IllegalStateException("runtime"))
            val directive = RecoveryPolicy.directive(kind)
            assertEquals(expectedKind, kind)
            assertEquals(RecoveryAction.LOAD_MODELS, directive.action)
            assertTrue(directive.preserveRawTranscript)
        }
    }

    @Test
    fun rejectedEditorCommitCanOnlyBeDismissedAndIsNeverRetried() {
        val kind = RecoveryPolicy.classify(
            PipelineFailureStage.EDITOR_COMMIT,
            IllegalStateException("editor rejected commit"),
        )
        val directive = RecoveryPolicy.directive(kind)

        assertEquals(PipelineFailureKind.EDITOR_COMMIT, kind)
        assertEquals(RecoveryAction.DISMISS, directive.action)
        assertTrue(directive.preserveRawTranscript)
        assertFalse(directive.mayRetryEditorCommit)
    }
}
