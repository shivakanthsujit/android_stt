package dev.localflow.llamacppbenchmark

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class NativeResultContractTest {
    @Test
    fun validatesResolvedReleaseModelConfiguration() {
        val config = BenchmarkConfig()
        for (library in NativeResultContract.PINNED_CPU_BACKEND_LIBRARIES) {
            NativeResultContract.validateModelInfo(validModelInfo(config, library), config)
        }
    }

    @Test
    fun rejectsBackendListThatIsNotExactlyCpu() {
        val config = BenchmarkConfig()
        assertThrows(IllegalArgumentException::class.java) {
            NativeResultContract.validateModelInfo(
                validModelInfo(config).put(
                    "backend_names",
                    JSONArray(listOf("CPU", "OpenCL")),
                ),
                config,
            )
        }
    }

    @Test
    fun rejectsCpuBackendLibraryOutsidePackagedVariants() {
        val config = BenchmarkConfig()
        assertThrows(IllegalArgumentException::class.java) {
            NativeResultContract.validateModelInfo(
                validModelInfo(config, "libggml-cpu.so"),
                config,
            )
        }
    }

    @Test
    fun rejectsNativeBuildProvenanceDrift() {
        val config = BenchmarkConfig()
        assertThrows(IllegalArgumentException::class.java) {
            NativeResultContract.validateModelInfo(
                validModelInfo(config).put("llama_build_number", 10_451),
                config,
            )
        }
    }

    @Test
    fun validatesCompleteEogGeneration() {
        val generation = validGeneration()
        val preflight = NativeResultContract.validateTokenization(validTokenization(), "hello")

        NativeResultContract.validateGeneration(
            generation,
            preflight,
            rawText = "hello",
            maxOutputTokens = 40,
        )
        assertEquals(2, preflight.rawTokenCount)
        assertEquals(80, preflight.promptTokenCount)
    }

    @Test
    fun rejectsCapAndTimestampContradictions() {
        val preflight = NativeResultContract.validateTokenization(validTokenization(), "hello")
        assertThrows(IllegalArgumentException::class.java) {
            NativeResultContract.validateGeneration(
                validGeneration()
                    .put("finish_reason", "token_cap")
                    .put("hit_token_cap", true),
                preflight,
                rawText = "hello",
                maxOutputTokens = 40,
            )
        }
        assertThrows(IllegalArgumentException::class.java) {
            NativeResultContract.validateGeneration(
                validGeneration().put("first_token_at_ns", 15),
                preflight,
                rawText = "hello",
                maxOutputTokens = 40,
            )
        }
    }

    @Test
    fun generationCannotOwnHostSchemaVersion() {
        val preflight = NativeResultContract.validateTokenization(validTokenization(), "hello")
        assertThrows(IllegalArgumentException::class.java) {
            NativeResultContract.validateGeneration(
                validGeneration().put("schema_version", 1),
                preflight,
                rawText = "hello",
                maxOutputTokens = 40,
            )
        }
    }

    private fun validTokenization(): JSONObject =
        JSONObject(validGeneration().toString()).put("schema_version", 1)

    private fun validModelInfo(
        config: BenchmarkConfig,
        selectedCpuBackendLibrary: String = "libggml-cpu-android_armv8.2_2.so",
    ): JSONObject =
        JSONObject()
            .put("schema_version", 1)
            .put("model_description", "S1-mini by Superwhisper")
            .put("model_size_bytes", S1Contract.MODEL_SIZE_BYTES)
            .put("model_parameter_count", 600_000_000L)
            .put("chat_template", "embedded-template")
            .put("context_size", config.contextTokens)
            .put("batch_size", config.batchSize)
            .put("micro_batch_size", config.microBatchSize)
            .put("threads", config.generationThreads)
            .put("threads_batch", config.batchThreads)
            .put("use_mmap", config.useMmap)
            .put("flash_attention", config.flashAttention)
            .put("gpu_layers", config.gpuLayers)
            .put("backend_names", JSONArray(listOf("CPU")))
            .put("selected_cpu_backend_library", selectedCpuBackendLibrary)
            .put("system_info", "ARM64")
            .put("supports_mmap", true)
            .put("supports_gpu_offload", false)
            .put("supports_enable_thinking", true)
            .put("fixed_prompt_tokens", S1Contract.EXPECTED_FIXED_PROMPT_TOKENS)
            .put("llama_version", "0.1.0-dev")
            .put("llama_build_number", 10_450)
            .put("llama_commit", "ece963f41")
            .put("llama_build_target", "Android aarch64")
            .put("native_build_type", "Release")
            .put("native_compiler", "Clang")
            .put("native_compile_flags", "-O3 -DNDEBUG")

    private fun validGeneration(): JSONObject {
        val promptIds = List(80) { it + 100 }
        return JSONObject()
            .put("raw_token_ids", JSONArray(listOf(10, 11)))
            .put("raw_token_count", 2)
            .put("rendered_prompt", S1Contract.renderPrompt("hello"))
            .put("prompt_token_ids", JSONArray(promptIds))
            .put("prompt_token_count", promptIds.size)
            .put("raw_output", "Hello.")
            .put("completion_token_ids", JSONArray(listOf(20, 21)))
            .put("completion_tokens", 2)
            .put("finish_reason", "eog")
            .put("hit_token_cap", false)
            .put("eog_token_id", 151645)
            .put("started_at_ns", 10)
            .put("prompt_started_at_ns", 20)
            .put("prompt_completed_at_ns", 30)
            .put("first_token_at_ns", 40)
            .put("completed_at_ns", 50)
            .put("prompt_eval_ms", 1.0)
            .put("decode_ms", 2.0)
            .put("total_ms", 3.0)
            .put("prompt_tokens_per_second", 80.0)
            .put("decode_tokens_per_second", 10.0)
            .put("perf_prompt_eval_ms", 1.0)
            .put("perf_decode_ms", 2.0)
            .put("perf_prompt_tokens", 80)
            .put("perf_decode_tokens", 2)
            .put("perf_reused_graphs", 0)
    }
}
