package dev.localflow.dictation

import android.app.Application

/** Process owner for the model pipeline shared by the Activity and input method service. */
class LocalFlowApplication : Application() {
    private val pipelineCoordinatorLazy = lazy {
        DictationPipelineCoordinator(applicationContext)
    }
    val pipelineCoordinator: DictationPipelineCoordinator by pipelineCoordinatorLazy

    override fun onTerminate() {
        if (pipelineCoordinatorLazy.isInitialized()) {
            pipelineCoordinatorLazy.value.close()
        }
        super.onTerminate()
    }
}
