#include <jni.h>

#include <android/log.h>
#include <dlfcn.h>
#include <sys/stat.h>
#include <time.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <exception>
#include <limits>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include "chat.h"
#include "common.h"
#include "ggml-backend.h"
#include "llama.h"
#include "nlohmann/json.hpp"

namespace {

using json = nlohmann::ordered_json;

constexpr const char * LOG_TAG = "S1LlamaBenchmark";
constexpr const char * SYSTEM_PROMPT =
    "You are a text normalizer for speech-to-text transcripts. The input begins with a control "
    "line specifying the styling, structure, and context settings; clean the transcript to match "
    "those settings and output only the cleaned text.";
constexpr const char * CONTROL_LINE =
    "[Styling: semi-formal] [Structure: prose] [Context: general]";
constexpr int32_t EXPECTED_FIXED_PROMPT_TOKENS = 78;
constexpr int32_t MAX_RAW_TOKENS = 1'000;
constexpr int32_t MAX_OUTPUT_TOKENS = 2'048;
std::string selected_cpu_backend_library;

#ifndef S1_NATIVE_BUILD_TYPE
#define S1_NATIVE_BUILD_TYPE "unknown"
#endif
#ifndef S1_NATIVE_COMPILER
#define S1_NATIVE_COMPILER "unknown"
#endif
#ifndef S1_NATIVE_COMPILE_FLAGS
#define S1_NATIVE_COMPILE_FLAGS "unknown"
#endif

void android_log_callback(enum ggml_log_level level, const char * text, void *) {
    int priority = ANDROID_LOG_DEBUG;
    switch (level) {
        case GGML_LOG_LEVEL_ERROR: priority = ANDROID_LOG_ERROR; break;
        case GGML_LOG_LEVEL_WARN:  priority = ANDROID_LOG_WARN;  break;
        case GGML_LOG_LEVEL_INFO:  priority = ANDROID_LOG_INFO;  break;
        case GGML_LOG_LEVEL_DEBUG:
        case GGML_LOG_LEVEL_CONT:
        case GGML_LOG_LEVEL_NONE:
        default:                   priority = ANDROID_LOG_DEBUG; break;
    }
    __android_log_write(priority, LOG_TAG, text == nullptr ? "" : text);
}

int64_t monotonic_ns() {
    timespec value{};
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) {
        throw std::runtime_error("clock_gettime(CLOCK_MONOTONIC) failed");
    }
    return static_cast<int64_t>(value.tv_sec) * 1'000'000'000LL + value.tv_nsec;
}

std::string utf8_from_jstring(JNIEnv * env, jstring value, const char * name) {
    if (value == nullptr) {
        throw std::invalid_argument(std::string(name) + " must not be null");
    }
    const jsize length = env->GetStringLength(value);
    const jchar * chars = env->GetStringChars(value, nullptr);
    if (chars == nullptr) {
        throw std::runtime_error(std::string("Could not read ") + name);
    }

    std::string result;
    result.reserve(static_cast<size_t>(length) * 3U);
    for (jsize index = 0; index < length; ++index) {
        uint32_t code_point = chars[index];
        if (code_point >= 0xD800U && code_point <= 0xDBFFU) {
            if (index + 1 >= length) {
                env->ReleaseStringChars(value, chars);
                throw std::invalid_argument(std::string(name) + " contains an unpaired surrogate");
            }
            const uint32_t low = chars[++index];
            if (low < 0xDC00U || low > 0xDFFFU) {
                env->ReleaseStringChars(value, chars);
                throw std::invalid_argument(std::string(name) + " contains an unpaired surrogate");
            }
            code_point = 0x10000U + ((code_point - 0xD800U) << 10U) + (low - 0xDC00U);
        } else if (code_point >= 0xDC00U && code_point <= 0xDFFFU) {
            env->ReleaseStringChars(value, chars);
            throw std::invalid_argument(std::string(name) + " contains an unpaired surrogate");
        }

        if (code_point <= 0x7FU) {
            result.push_back(static_cast<char>(code_point));
        } else if (code_point <= 0x7FFU) {
            result.push_back(static_cast<char>(0xC0U | (code_point >> 6U)));
            result.push_back(static_cast<char>(0x80U | (code_point & 0x3FU)));
        } else if (code_point <= 0xFFFFU) {
            result.push_back(static_cast<char>(0xE0U | (code_point >> 12U)));
            result.push_back(static_cast<char>(0x80U | ((code_point >> 6U) & 0x3FU)));
            result.push_back(static_cast<char>(0x80U | (code_point & 0x3FU)));
        } else {
            result.push_back(static_cast<char>(0xF0U | (code_point >> 18U)));
            result.push_back(static_cast<char>(0x80U | ((code_point >> 12U) & 0x3FU)));
            result.push_back(static_cast<char>(0x80U | ((code_point >> 6U) & 0x3FU)));
            result.push_back(static_cast<char>(0x80U | (code_point & 0x3FU)));
        }
    }
    env->ReleaseStringChars(value, chars);
    return result;
}

jstring json_to_jstring(JNIEnv * env, const json & value) {
    // ensure_ascii keeps NewStringUTF on its strictly valid modified-UTF-8 subset.
    const std::string serialized = value.dump(-1, ' ', true, json::error_handler_t::strict);
    jstring result = env->NewStringUTF(serialized.c_str());
    if (result == nullptr) {
        throw std::runtime_error("Could not allocate JSON result string");
    }
    return result;
}

void throw_java(JNIEnv * env, const char * class_name, const std::string & message) {
    if (env->ExceptionCheck()) {
        return;
    }
    jclass type = env->FindClass(class_name);
    if (type != nullptr) {
        env->ThrowNew(type, message.c_str());
        env->DeleteLocalRef(type);
    }
}

template<typename Return, typename Function>
Return jni_call(JNIEnv * env, Return failure, Function && function) {
    try {
        return function();
    } catch (const std::invalid_argument & error) {
        throw_java(env, "java/lang/IllegalArgumentException", error.what());
    } catch (const std::logic_error & error) {
        throw_java(env, "java/lang/IllegalStateException", error.what());
    } catch (const std::exception & error) {
        throw_java(env, "java/lang/RuntimeException", error.what());
    } catch (...) {
        throw_java(env, "java/lang/RuntimeException", "Unknown native llama.cpp failure");
    }
    return failure;
}

template<typename Function>
void jni_call_void(JNIEnv * env, Function && function) {
    (void) jni_call<int>(env, 0, [&]() {
        function();
        return 1;
    });
}

std::string load_best_packaged_cpu_backend() {
    // Modern Android installs native libraries directly from the APK
    // (android:extractNativeLibs=false), so dladdr can produce an APK-internal `!/lib/...` path
    // that std::filesystem cannot enumerate. Resolve the packaged DSOs by soname through the
    // Android linker namespace, while using the pinned backend's own score function to retain the
    // same runtime variant selection policy as ggml_backend_load_best().
    constexpr std::array<const char *, 7> candidates = {
        "libggml-cpu-android_armv8.0_1.so",
        "libggml-cpu-android_armv8.2_1.so",
        "libggml-cpu-android_armv8.2_2.so",
        "libggml-cpu-android_armv8.6_1.so",
        "libggml-cpu-android_armv9.0_1.so",
        "libggml-cpu-android_armv9.2_1.so",
        "libggml-cpu-android_armv9.2_2.so",
    };
    using BackendScore = int (*)();
    int best_score = 0;
    const char * best_library = nullptr;
    for (const char * candidate : candidates) {
        void * library = dlopen(candidate, RTLD_NOW | RTLD_LOCAL);
        if (library == nullptr) {
            continue;
        }
        void * score_symbol = dlsym(library, "ggml_backend_score");
        if (score_symbol != nullptr) {
            const auto score = reinterpret_cast<BackendScore>(score_symbol)();
            if (score > best_score) {
                best_score = score;
                best_library = candidate;
            }
        }
        dlclose(library);
    }
    if (best_library == nullptr) {
        const char * error = dlerror();
        throw std::runtime_error(
            "No packaged ARM CPU backend supports this device" +
            std::string(error == nullptr ? "" : ": ") +
            std::string(error == nullptr ? "" : error));
    }
    if (ggml_backend_load(best_library) == nullptr) {
        throw std::runtime_error(
            "Could not load selected CPU backend: " + std::string(best_library));
    }
    return best_library;
}

void initialize_backends() {
    static std::once_flag initialized;
    std::call_once(initialized, [] {
        llama_log_set(android_log_callback, nullptr);
        selected_cpu_backend_library = load_best_packaged_cpu_backend();
        llama_backend_init();
        if (ggml_backend_reg_count() != 1 || ggml_backend_reg_by_name("CPU") == nullptr) {
            throw std::runtime_error("Expected exactly one selected CPU backend");
        }
    });
}

struct ModelDeleter {
    void operator()(llama_model * value) const {
        if (value != nullptr) llama_model_free(value);
    }
};

struct ContextDeleter {
    void operator()(llama_context * value) const {
        if (value != nullptr) llama_free(value);
    }
};

struct SamplerDeleter {
    void operator()(llama_sampler * value) const {
        if (value != nullptr) llama_sampler_free(value);
    }
};

using ModelPtr = std::unique_ptr<llama_model, ModelDeleter>;
using ContextPtr = std::unique_ptr<llama_context, ContextDeleter>;
using SamplerPtr = std::unique_ptr<llama_sampler, SamplerDeleter>;

struct RuntimeConfig {
    int32_t context_size;
    int32_t threads;
    int32_t threads_batch;
    int32_t batch_size;
    int32_t micro_batch_size;
    bool use_mmap;
    bool flash_attention;
    int32_t gpu_layers;
};

struct NativeRuntime {
    std::mutex mutex;
    ModelPtr model;
    ContextPtr context;
    common_chat_templates_ptr templates;
    RuntimeConfig config{};
    std::string chat_template;
    std::string model_description;
    uint64_t artifact_size_bytes = 0;
    uint64_t model_tensor_size_bytes = 0;
    uint64_t model_parameter_count = 0;
};

std::mutex registry_mutex;
std::unordered_map<int64_t, std::shared_ptr<NativeRuntime>> runtimes;
std::atomic<int64_t> next_handle{1};

std::shared_ptr<NativeRuntime> require_runtime(jlong handle) {
    if (handle <= 0) {
        throw std::logic_error("Native llama.cpp handle is closed or invalid");
    }
    std::lock_guard<std::mutex> lock(registry_mutex);
    const auto found = runtimes.find(handle);
    if (found == runtimes.end()) {
        throw std::logic_error("Native llama.cpp handle is closed or unknown");
    }
    return found->second;
}

uint64_t validate_model_file(const std::string & path) {
    if (path.empty() || path.front() != '/') {
        throw std::invalid_argument("modelPath must be a non-empty absolute path");
    }
    struct stat status{};
    if (stat(path.c_str(), &status) != 0 || !S_ISREG(status.st_mode) || status.st_size <= 0) {
        throw std::invalid_argument("modelPath must identify a present, non-empty regular file");
    }
    return static_cast<uint64_t>(status.st_size);
}

RuntimeConfig validate_config(
    jint context_size,
    jint threads,
    jint threads_batch,
    jint batch_size,
    jint micro_batch_size,
    jboolean use_mmap,
    jboolean flash_attention,
    jint gpu_layers) {
    if (context_size < 256 || context_size > 32'768) {
        throw std::invalid_argument("contextSize must be between 256 and 32768");
    }
    if (threads < 1 || threads > 16 || threads_batch < 1 || threads_batch > 16) {
        throw std::invalid_argument("threads and threadsBatch must be between 1 and 16");
    }
    if (batch_size < 1 || batch_size > context_size) {
        throw std::invalid_argument("batchSize must be positive and no larger than contextSize");
    }
    if (micro_batch_size < 1 || micro_batch_size > batch_size) {
        throw std::invalid_argument("microBatchSize must be positive and no larger than batchSize");
    }
    if (gpu_layers != 0) {
        throw std::invalid_argument("This benchmark build is CPU-only; gpuLayers must be zero");
    }
    return RuntimeConfig{
        context_size,
        threads,
        threads_batch,
        batch_size,
        micro_batch_size,
        use_mmap == JNI_TRUE,
        flash_attention == JNI_TRUE,
        gpu_layers,
    };
}

std::vector<llama_token> tokenize(
    const llama_vocab * vocab,
    const std::string & text,
    bool add_special,
    bool parse_special) {
    const int32_t required = llama_tokenize(
        vocab,
        text.data(),
        static_cast<int32_t>(text.size()),
        nullptr,
        0,
        add_special,
        parse_special);
    if (required == 0) {
        return {};
    }
    if (required != std::numeric_limits<int32_t>::min() && required > 0) {
        throw std::runtime_error("llama_tokenize unexpectedly succeeded without an output buffer");
    }
    if (required == std::numeric_limits<int32_t>::min()) {
        throw std::runtime_error("llama_tokenize token count overflow");
    }
    std::vector<llama_token> result(static_cast<size_t>(-required));
    const int32_t written = llama_tokenize(
        vocab,
        text.data(),
        static_cast<int32_t>(text.size()),
        result.data(),
        static_cast<int32_t>(result.size()),
        add_special,
        parse_special);
    if (written < 0 || written != static_cast<int32_t>(result.size())) {
        throw std::runtime_error("llama_tokenize failed to produce the expected token count");
    }
    return result;
}

std::string render_prompt(NativeRuntime & runtime, const std::string & raw_text) {
    common_chat_msg system_message;
    system_message.role = "system";
    system_message.content = SYSTEM_PROMPT;
    common_chat_msg user_message;
    user_message.role = "user";
    user_message.content = std::string(CONTROL_LINE) + "\n" + raw_text;
    common_chat_templates_inputs inputs;
    inputs.messages = {std::move(system_message), std::move(user_message)};
    inputs.add_generation_prompt = true;
    inputs.use_jinja = true;
    inputs.enable_thinking = false;
    return common_chat_templates_apply(runtime.templates.get(), inputs).prompt;
}

struct TokenizationEvidence {
    std::vector<llama_token> raw_tokens;
    std::string rendered_prompt;
    std::vector<llama_token> prompt_tokens;
};

TokenizationEvidence prepare_prompt(NativeRuntime & runtime, const std::string & raw_text) {
    if (raw_text.empty()) {
        throw std::invalid_argument("rawText must not be empty");
    }
    if (raw_text.size() > static_cast<size_t>(std::numeric_limits<int32_t>::max())) {
        throw std::invalid_argument("rawText is too large to tokenize");
    }
    const llama_vocab * vocab = llama_model_get_vocab(runtime.model.get());
    TokenizationEvidence result;
    // This exactly matches llama-server's /tokenize request used for the host golden:
    // add_special=false with its default parse_special=true.
    result.raw_tokens = tokenize(vocab, raw_text, false, true);
    if (result.raw_tokens.empty() || result.raw_tokens.size() > MAX_RAW_TOKENS) {
        throw std::invalid_argument("rawText must tokenize to between 1 and 1000 raw tokens");
    }
    result.rendered_prompt = render_prompt(runtime, raw_text);
    result.prompt_tokens = tokenize(vocab, result.rendered_prompt, true, true);
    if (result.prompt_tokens.empty()) {
        throw std::runtime_error("Rendered prompt produced no tokens");
    }
    return result;
}

json tokenization_json(const TokenizationEvidence & evidence) {
    return json{
        {"schema_version", 1},
        {"raw_token_ids", evidence.raw_tokens},
        {"raw_token_count", evidence.raw_tokens.size()},
        {"rendered_prompt", evidence.rendered_prompt},
        {"prompt_token_ids", evidence.prompt_tokens},
        {"prompt_token_count", evidence.prompt_tokens.size()},
    };
}

std::string token_piece(const llama_vocab * vocab, llama_token token) {
    int32_t size = llama_token_to_piece(vocab, token, nullptr, 0, 0, false);
    if (size == 0) {
        return {};
    }
    if (size != std::numeric_limits<int32_t>::min() && size > 0) {
        throw std::runtime_error("llama_token_to_piece unexpectedly succeeded without a buffer");
    }
    if (size == std::numeric_limits<int32_t>::min()) {
        throw std::runtime_error("llama_token_to_piece size overflow");
    }
    std::string result(static_cast<size_t>(-size), '\0');
    const int32_t written = llama_token_to_piece(
        vocab,
        token,
        result.data(),
        static_cast<int32_t>(result.size()),
        0,
        false);
    if (written < 0 || written != static_cast<int32_t>(result.size())) {
        throw std::runtime_error("llama_token_to_piece failed");
    }
    return result;
}

void clear_context(NativeRuntime & runtime) {
    llama_synchronize(runtime.context.get());
    // Clearing metadata makes the next sequence logically empty. Avoid zero-filling the backing
    // buffers: they are unreachable after the metadata reset and the pinned Android example uses
    // this fresh-request path.
    llama_memory_clear(llama_get_memory(runtime.context.get()), false);
    llama_perf_context_reset(runtime.context.get());
}

void decode_prompt(NativeRuntime & runtime, const std::vector<llama_token> & tokens) {
    size_t offset = 0;
    const size_t batch_size = llama_n_batch(runtime.context.get());
    while (offset < tokens.size()) {
        const size_t count = std::min(batch_size, tokens.size() - offset);
        llama_batch batch = llama_batch_get_one(
            const_cast<llama_token *>(tokens.data() + offset),
            static_cast<int32_t>(count));
        const int32_t result = llama_decode(runtime.context.get(), batch);
        if (result != 0) {
            throw std::runtime_error("llama_decode failed during prompt evaluation: " +
                                     std::to_string(result));
        }
        offset += count;
    }
    llama_synchronize(runtime.context.get());
}

json model_info_json(NativeRuntime & runtime) {
    std::vector<std::string> backends;
    for (size_t index = 0; index < ggml_backend_reg_count(); ++index) {
        ggml_backend_reg_t backend = ggml_backend_reg_get(index);
        const char * name = backend == nullptr ? nullptr : ggml_backend_reg_name(backend);
        if (name != nullptr) backends.emplace_back(name);
    }
    return json{
        {"schema_version", 1},
        {"model_description", runtime.model_description},
        // The Kotlin contract pins the exact GGUF artifact length. Keep llama.cpp's tensor-byte
        // accounting separate because it does not necessarily equal the file length.
        {"model_size_bytes", runtime.artifact_size_bytes},
        {"model_tensor_size_bytes", runtime.model_tensor_size_bytes},
        {"model_parameter_count", runtime.model_parameter_count},
        {"chat_template", runtime.chat_template},
        {"context_size", llama_n_ctx(runtime.context.get())},
        {"batch_size", llama_n_batch(runtime.context.get())},
        {"micro_batch_size", llama_n_ubatch(runtime.context.get())},
        {"threads", llama_n_threads(runtime.context.get())},
        {"threads_batch", llama_n_threads_batch(runtime.context.get())},
        {"use_mmap", runtime.config.use_mmap},
        {"flash_attention", runtime.config.flash_attention},
        {"gpu_layers", runtime.config.gpu_layers},
        {"backend_names", backends},
        {"selected_cpu_backend_library", selected_cpu_backend_library},
        {"system_info", llama_print_system_info()},
        {"supports_mmap", llama_supports_mmap()},
        {"supports_gpu_offload", llama_supports_gpu_offload()},
        {"supports_enable_thinking", true},
        {"fixed_prompt_tokens", EXPECTED_FIXED_PROMPT_TOKENS},
        {"llama_version", llama_version()},
        {"native_build_type", S1_NATIVE_BUILD_TYPE},
        {"native_compiler", S1_NATIVE_COMPILER},
        {"native_compile_flags", S1_NATIVE_COMPILE_FLAGS},
    };
}

}  // namespace

extern "C" JNIEXPORT jlong JNICALL
Java_dev_localflow_llamacppbenchmark_NativeLlama_nativeLoadModel(
    JNIEnv * env,
    jobject,
    jstring model_path,
    jint context_size,
    jint threads,
    jint threads_batch,
    jint batch_size,
    jint micro_batch_size,
    jboolean use_mmap,
    jboolean flash_attention,
    jint gpu_layers) {
    return jni_call<jlong>(env, 0, [&]() -> jlong {
        initialize_backends();
        const std::string path = utf8_from_jstring(env, model_path, "modelPath");
        const uint64_t artifact_size_bytes = validate_model_file(path);
        const RuntimeConfig config = validate_config(
            context_size,
            threads,
            threads_batch,
            batch_size,
            micro_batch_size,
            use_mmap,
            flash_attention,
            gpu_layers);

        llama_model_params model_params = llama_model_default_params();
        model_params.n_gpu_layers = config.gpu_layers;
        model_params.load_mode = config.use_mmap ? LLAMA_LOAD_MODE_MMAP : LLAMA_LOAD_MODE_NONE;
        ModelPtr model(llama_model_load_from_file(path.c_str(), model_params));
        if (!model) {
            throw std::runtime_error("llama_model_load_from_file failed");
        }

        const char * embedded_template = llama_model_chat_template(model.get(), nullptr);
        if (embedded_template == nullptr || embedded_template[0] == '\0') {
            throw std::runtime_error("GGUF has no embedded default chat template");
        }
        common_chat_templates_ptr templates = common_chat_templates_init(model.get(), "");
        if (!templates || !common_chat_templates_was_explicit(templates.get())) {
            throw std::runtime_error("Could not initialize the GGUF embedded chat template");
        }
        if (!common_chat_templates_support_enable_thinking(templates.get())) {
            throw std::runtime_error("GGUF chat template does not support enable_thinking");
        }

        llama_context_params context_params = llama_context_default_params();
        context_params.n_ctx = static_cast<uint32_t>(config.context_size);
        context_params.n_batch = static_cast<uint32_t>(config.batch_size);
        context_params.n_ubatch = static_cast<uint32_t>(config.micro_batch_size);
        context_params.n_seq_max = 1;
        context_params.n_threads = config.threads;
        context_params.n_threads_batch = config.threads_batch;
        context_params.flash_attn_type = config.flash_attention
            ? LLAMA_FLASH_ATTN_TYPE_ENABLED
            : LLAMA_FLASH_ATTN_TYPE_DISABLED;
        context_params.no_perf = false;
        ContextPtr context(llama_init_from_model(model.get(), context_params));
        if (!context) {
            throw std::runtime_error("llama_init_from_model failed");
        }

        auto runtime = std::make_shared<NativeRuntime>();
        runtime->model = std::move(model);
        runtime->context = std::move(context);
        runtime->templates = std::move(templates);
        runtime->config = config;
        runtime->chat_template = common_chat_templates_source(runtime->templates.get());
        runtime->artifact_size_bytes = artifact_size_bytes;
        runtime->model_tensor_size_bytes = llama_model_size(runtime->model.get());
        runtime->model_parameter_count = llama_model_n_params(runtime->model.get());
        std::vector<char> description(512, '\0');
        const int32_t description_size = llama_model_desc(
            runtime->model.get(), description.data(), description.size());
        if (description_size < 0) {
            throw std::runtime_error("llama_model_desc failed");
        }
        runtime->model_description = description.data();

        const llama_vocab * vocab = llama_model_get_vocab(runtime->model.get());
        const std::string empty_prompt = render_prompt(*runtime, "");
        const auto empty_prompt_tokens = tokenize(vocab, empty_prompt, true, true);
        if (empty_prompt_tokens.size() != EXPECTED_FIXED_PROMPT_TOKENS) {
            throw std::runtime_error(
                "Fixed prompt-token drift: expected 78, got " +
                std::to_string(empty_prompt_tokens.size()));
        }
        clear_context(*runtime);

        int64_t handle = next_handle.fetch_add(1);
        if (handle <= 0) {
            throw std::runtime_error("Native handle space exhausted");
        }
        {
            std::lock_guard<std::mutex> lock(registry_mutex);
            if (!runtimes.emplace(handle, runtime).second) {
                throw std::runtime_error("Native handle collision");
            }
        }
        return static_cast<jlong>(handle);
    });
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_localflow_llamacppbenchmark_NativeLlama_nativeModelInfo(
    JNIEnv * env,
    jobject,
    jlong handle) {
    return jni_call<jstring>(env, nullptr, [&]() {
        auto runtime = require_runtime(handle);
        std::lock_guard<std::mutex> lock(runtime->mutex);
        return json_to_jstring(env, model_info_json(*runtime));
    });
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_localflow_llamacppbenchmark_NativeLlama_nativeTokenize(
    JNIEnv * env,
    jobject,
    jlong handle,
    jstring raw_text) {
    return jni_call<jstring>(env, nullptr, [&]() {
        auto runtime = require_runtime(handle);
        const std::string raw = utf8_from_jstring(env, raw_text, "rawText");
        std::lock_guard<std::mutex> lock(runtime->mutex);
        return json_to_jstring(env, tokenization_json(prepare_prompt(*runtime, raw)));
    });
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_localflow_llamacppbenchmark_NativeLlama_nativeGenerate(
    JNIEnv * env,
    jobject,
    jlong handle,
    jstring raw_text,
    jint max_output_tokens) {
    return jni_call<jstring>(env, nullptr, [&]() {
        auto runtime = require_runtime(handle);
        const std::string raw = utf8_from_jstring(env, raw_text, "rawText");
        std::lock_guard<std::mutex> lock(runtime->mutex);
        if (max_output_tokens < 1 || max_output_tokens > MAX_OUTPUT_TOKENS) {
            throw std::invalid_argument("maxOutputTokens must be between 1 and 2048");
        }

        const int64_t started_at_ns = monotonic_ns();
        TokenizationEvidence evidence = prepare_prompt(*runtime, raw);
        const int32_t expected_cap = std::min(
            MAX_OUTPUT_TOKENS,
            (13 * static_cast<int32_t>(evidence.raw_tokens.size()) + 9) / 10 + 32);
        if (max_output_tokens != expected_cap) {
            throw std::invalid_argument(
                "maxOutputTokens does not match the publisher cap: expected " +
                std::to_string(expected_cap));
        }
        if (evidence.prompt_tokens.size() + static_cast<size_t>(max_output_tokens) >
            llama_n_ctx(runtime->context.get())) {
            throw std::invalid_argument("prompt tokens plus output cap exceed the context size");
        }

        clear_context(*runtime);
        llama_sampler_chain_params sampler_params = llama_sampler_chain_default_params();
        sampler_params.no_perf = false;
        SamplerPtr sampler(llama_sampler_chain_init(sampler_params));
        if (!sampler) {
            throw std::runtime_error("llama_sampler_chain_init failed");
        }
        llama_sampler * greedy = llama_sampler_init_greedy();
        if (greedy == nullptr) {
            throw std::runtime_error("llama_sampler_init_greedy failed");
        }
        llama_sampler_chain_add(sampler.get(), greedy);

        const int64_t prompt_started_at_ns = monotonic_ns();
        decode_prompt(*runtime, evidence.prompt_tokens);
        const int64_t prompt_completed_at_ns = monotonic_ns();

        const llama_vocab * vocab = llama_model_get_vocab(runtime->model.get());
        std::vector<llama_token> completion_tokens;
        completion_tokens.reserve(static_cast<size_t>(max_output_tokens));
        std::string output;
        int64_t first_token_at_ns = 0;
        llama_token eog_token = LLAMA_TOKEN_NULL;
        bool hit_token_cap = false;

        for (int32_t index = 0; index < max_output_tokens; ++index) {
            const llama_token token = llama_sampler_sample(sampler.get(), runtime->context.get(), -1);
            if (llama_vocab_is_eog(vocab, token)) {
                eog_token = token;
                break;
            }
            if (first_token_at_ns == 0) {
                first_token_at_ns = monotonic_ns();
            }
            completion_tokens.push_back(token);
            output += token_piece(vocab, token);

            if (index + 1 == max_output_tokens) {
                hit_token_cap = true;
                break;
            }
            llama_batch batch = llama_batch_get_one(
                &completion_tokens.back(), 1);
            const int32_t decode_result = llama_decode(runtime->context.get(), batch);
            if (decode_result != 0) {
                throw std::runtime_error(
                    "llama_decode failed during generation: " + std::to_string(decode_result));
            }
        }
        llama_synchronize(runtime->context.get());
        const int64_t completed_at_ns = monotonic_ns();
        const llama_perf_context_data perf = llama_perf_context(runtime->context.get());

        json result = tokenization_json(evidence);
        result.erase("schema_version");
        result["raw_output"] = output;
        result["completion_token_ids"] = completion_tokens;
        result["completion_tokens"] = completion_tokens.size();
        result["finish_reason"] = hit_token_cap ? "token_cap" : "eog";
        result["hit_token_cap"] = hit_token_cap;
        result["eog_token_id"] = eog_token == LLAMA_TOKEN_NULL ? json(nullptr) : json(eog_token);
        result["started_at_ns"] = started_at_ns;
        result["prompt_started_at_ns"] = prompt_started_at_ns;
        result["prompt_completed_at_ns"] = prompt_completed_at_ns;
        result["first_token_at_ns"] = first_token_at_ns == 0 ? json(nullptr) : json(first_token_at_ns);
        result["completed_at_ns"] = completed_at_ns;
        result["prompt_eval_ms"] = (prompt_completed_at_ns - prompt_started_at_ns) / 1'000'000.0;
        result["decode_ms"] = (completed_at_ns - prompt_completed_at_ns) / 1'000'000.0;
        result["total_ms"] = (completed_at_ns - started_at_ns) / 1'000'000.0;
        const double prompt_seconds = (prompt_completed_at_ns - prompt_started_at_ns) / 1.0e9;
        const double decode_seconds = (completed_at_ns - prompt_completed_at_ns) / 1.0e9;
        result["prompt_tokens_per_second"] = prompt_seconds > 0.0
            ? evidence.prompt_tokens.size() / prompt_seconds
            : 0.0;
        result["decode_tokens_per_second"] = decode_seconds > 0.0
            ? completion_tokens.size() / decode_seconds
            : 0.0;
        result["perf_prompt_eval_ms"] = perf.t_p_eval_ms;
        result["perf_decode_ms"] = perf.t_eval_ms;
        result["perf_prompt_tokens"] = perf.n_p_eval;
        result["perf_decode_tokens"] = perf.n_eval;
        result["perf_reused_graphs"] = perf.n_reused;
        return json_to_jstring(env, result);
    });
}

extern "C" JNIEXPORT void JNICALL
Java_dev_localflow_llamacppbenchmark_NativeLlama_nativeResetContext(
    JNIEnv * env,
    jobject,
    jlong handle) {
    jni_call_void(env, [&]() {
        auto runtime = require_runtime(handle);
        std::lock_guard<std::mutex> lock(runtime->mutex);
        clear_context(*runtime);
    });
}

extern "C" JNIEXPORT void JNICALL
Java_dev_localflow_llamacppbenchmark_NativeLlama_nativeClose(
    JNIEnv * env,
    jobject,
    jlong handle) {
    jni_call_void(env, [&]() {
        std::shared_ptr<NativeRuntime> runtime;
        {
            std::lock_guard<std::mutex> lock(registry_mutex);
            const auto found = runtimes.find(handle);
            if (found == runtimes.end()) {
                throw std::logic_error("Native llama.cpp handle is already closed or unknown");
            }
            runtime = found->second;
            runtimes.erase(found);
        }
        std::lock_guard<std::mutex> lock(runtime->mutex);
        runtime->templates.reset();
        runtime->context.reset();
        runtime->model.reset();
    });
}
