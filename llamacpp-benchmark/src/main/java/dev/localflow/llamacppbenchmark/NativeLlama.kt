package dev.localflow.llamacppbenchmark

import org.json.JSONObject

internal class NativeLlama : AutoCloseable {
    private var handle = 0L

    @Synchronized
    fun loadModel(modelPath: String, config: BenchmarkConfig): JSONObject {
        check(handle == 0L) { "model is already loaded" }
        val loadedHandle = nativeLoadModel(
            modelPath,
            config.contextTokens,
            config.generationThreads,
            config.batchThreads,
            config.batchSize,
            config.microBatchSize,
            config.useMmap,
            config.flashAttention,
            config.gpuLayers,
        )
        check(loadedHandle != 0L) { "native model load returned a null handle" }
        handle = loadedHandle
        return runCatching { parseJson(nativeModelInfo(loadedHandle), "model info") }
            .getOrElse { error ->
                close()
                throw error
            }
    }

    @Synchronized
    fun tokenize(rawText: String): JSONObject =
        parseJson(nativeTokenize(requireHandle(), rawText), "tokenization")

    @Synchronized
    fun resetContext() {
        nativeResetContext(requireHandle())
    }

    @Synchronized
    fun generate(rawText: String, maxOutputTokens: Int): JSONObject =
        parseJson(
            nativeGenerate(requireHandle(), rawText, maxOutputTokens),
            "generation",
        )

    @Synchronized
    override fun close() {
        val closingHandle = handle
        if (closingHandle == 0L) return
        handle = 0L
        nativeClose(closingHandle)
    }

    private fun requireHandle(): Long = handle.also { check(it != 0L) { "model is not loaded" } }

    private fun parseJson(value: String, label: String): JSONObject =
        runCatching { JSONObject(value) }.getOrElse {
            throw IllegalStateException("native $label returned invalid JSON", it)
        }

    private external fun nativeLoadModel(
        modelPath: String,
        contextSize: Int,
        threads: Int,
        threadsBatch: Int,
        batchSize: Int,
        microBatchSize: Int,
        useMmap: Boolean,
        flashAttention: Boolean,
        gpuLayers: Int,
    ): Long

    private external fun nativeModelInfo(handle: Long): String

    private external fun nativeTokenize(handle: Long, rawText: String): String

    private external fun nativeGenerate(
        handle: Long,
        rawText: String,
        maxOutputTokens: Int,
    ): String

    private external fun nativeResetContext(handle: Long)

    private external fun nativeClose(handle: Long)

    private companion object {
        init {
            System.loadLibrary("s1_llama_benchmark")
        }
    }
}
