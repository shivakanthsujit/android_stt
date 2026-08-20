package dev.localflow.dictation.stt

/** JNI boundary shared by the live integration engine and the debug file benchmark. */
object ParakeetNative {
    external fun nativeAbiVersion(): Int
    external fun nativeLoad(modelPath: String): Long
    external fun nativeTranscribePcm(
        handle: Long,
        samples: FloatArray,
        sampleRate: Int,
        decoder: Int,
    ): String
    external fun nativeStreamBegin(handle: Long): Long
    external fun nativeStreamFeedJson(streamHandle: Long, samples: FloatArray): String
    external fun nativeStreamFinalizeJson(streamHandle: Long): String
    external fun nativeStreamFree(streamHandle: Long)
    external fun nativeFree(handle: Long)

    init {
        System.loadLibrary("localflow_parakeet_jni")
    }
}
