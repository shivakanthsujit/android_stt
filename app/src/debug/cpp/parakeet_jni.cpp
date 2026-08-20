#include <jni.h>

#include <cstdint>
#include <string>

#include "parakeet_capi.h"

namespace {

parakeet_ctx* from_handle(jlong handle) {
    return reinterpret_cast<parakeet_ctx*>(static_cast<intptr_t>(handle));
}

parakeet_stream* stream_from_handle(jlong handle) {
    return reinterpret_cast<parakeet_stream*>(static_cast<intptr_t>(handle));
}

jlong to_handle(parakeet_ctx* context) {
    return static_cast<jlong>(reinterpret_cast<intptr_t>(context));
}

jlong stream_to_handle(parakeet_stream* stream) {
    return static_cast<jlong>(reinterpret_cast<intptr_t>(stream));
}

void throw_runtime_exception(JNIEnv* env, const std::string& message) {
    jclass exception = env->FindClass("java/lang/RuntimeException");
    if (exception != nullptr) {
        env->ThrowNew(exception, message.c_str());
    }
}

}  // namespace

extern "C" JNIEXPORT jint JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeAbiVersion(
    JNIEnv*, jobject) {
    return parakeet_capi_abi_version();
}

extern "C" JNIEXPORT jlong JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeLoad(
    JNIEnv* env, jobject, jstring model_path) {
    if (model_path == nullptr) {
        throw_runtime_exception(env, "Parakeet model path is null");
        return 0;
    }
    const char* path = env->GetStringUTFChars(model_path, nullptr);
    if (path == nullptr) {
        return 0;
    }
    parakeet_ctx* context = parakeet_capi_load(path);
    env->ReleaseStringUTFChars(model_path, path);
    if (context == nullptr) {
        throw_runtime_exception(env, "parakeet_capi_load failed");
        return 0;
    }
    return to_handle(context);
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeTranscribePcm(
    JNIEnv* env,
    jobject,
    jlong handle,
    jfloatArray samples,
    jint sample_rate,
    jint decoder) {
    parakeet_ctx* context = from_handle(handle);
    if (context == nullptr || samples == nullptr) {
        throw_runtime_exception(env, "Invalid Parakeet context or PCM buffer");
        return nullptr;
    }
    const jsize sample_count = env->GetArrayLength(samples);
    jfloat* pcm = env->GetFloatArrayElements(samples, nullptr);
    if (pcm == nullptr) {
        return nullptr;
    }
    char* transcript = parakeet_capi_transcribe_pcm(
        context,
        pcm,
        static_cast<int>(sample_count),
        static_cast<int>(sample_rate),
        static_cast<int>(decoder));
    env->ReleaseFloatArrayElements(samples, pcm, JNI_ABORT);
    if (transcript == nullptr) {
        const char* detail = parakeet_capi_last_error(context);
        throw_runtime_exception(
            env,
            std::string("Parakeet transcription failed: ") + (detail ? detail : ""));
        return nullptr;
    }
    jstring result = env->NewStringUTF(transcript);
    parakeet_capi_free_string(transcript);
    return result;
}

extern "C" JNIEXPORT jlong JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeStreamBegin(
    JNIEnv* env, jobject, jlong handle) {
    parakeet_ctx* context = from_handle(handle);
    if (context == nullptr) {
        throw_runtime_exception(env, "Invalid Parakeet context");
        return 0;
    }
    parakeet_stream* stream = parakeet_capi_stream_begin(context);
    if (stream == nullptr) {
        const char* detail = parakeet_capi_last_error(context);
        throw_runtime_exception(
            env,
            std::string("Parakeet streaming session failed: ") + (detail ? detail : ""));
        return 0;
    }
    return stream_to_handle(stream);
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeStreamFeedJson(
    JNIEnv* env, jobject, jlong stream_handle, jfloatArray samples) {
    parakeet_stream* stream = stream_from_handle(stream_handle);
    if (stream == nullptr || samples == nullptr) {
        throw_runtime_exception(env, "Invalid Parakeet stream or PCM buffer");
        return nullptr;
    }
    const jsize sample_count = env->GetArrayLength(samples);
    jfloat* pcm = env->GetFloatArrayElements(samples, nullptr);
    if (pcm == nullptr) {
        return nullptr;
    }
    char* json = parakeet_capi_stream_feed_json(
        stream,
        pcm,
        static_cast<int>(sample_count));
    env->ReleaseFloatArrayElements(samples, pcm, JNI_ABORT);
    if (json == nullptr) {
        throw_runtime_exception(env, "Parakeet streaming feed failed");
        return nullptr;
    }
    jstring result = env->NewStringUTF(json);
    parakeet_capi_free_string(json);
    return result;
}

extern "C" JNIEXPORT jstring JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeStreamFinalizeJson(
    JNIEnv* env, jobject, jlong stream_handle) {
    parakeet_stream* stream = stream_from_handle(stream_handle);
    if (stream == nullptr) {
        throw_runtime_exception(env, "Invalid Parakeet stream");
        return nullptr;
    }
    char* json = parakeet_capi_stream_finalize_json(stream);
    if (json == nullptr) {
        throw_runtime_exception(env, "Parakeet streaming finalization failed");
        return nullptr;
    }
    jstring result = env->NewStringUTF(json);
    parakeet_capi_free_string(json);
    return result;
}

extern "C" JNIEXPORT void JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeStreamFree(
    JNIEnv*, jobject, jlong stream_handle) {
    parakeet_capi_stream_free(stream_from_handle(stream_handle));
}

extern "C" JNIEXPORT void JNICALL
Java_dev_localflow_dictation_stt_ParakeetNative_nativeFree(
    JNIEnv*, jobject, jlong handle) {
    parakeet_capi_free(from_handle(handle));
}
