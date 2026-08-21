cmake_minimum_required(VERSION 3.31.6)

project(s1_llama_benchmark LANGUAGES C CXX)

if(NOT ANDROID)
    message(FATAL_ERROR "s1_llama_benchmark is an Android-only native target")
endif()
if(NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "s1_llama_benchmark supports only arm64-v8a")
endif()

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_BUILD_TYPE Release CACHE STRING "Android benchmark native build type" FORCE)

if(NOT DEFINED LLAMA_CPP_SOURCE_DIR OR LLAMA_CPP_SOURCE_DIR STREQUAL "")
    set(LLAMA_CPP_SOURCE_DIR
        "${CMAKE_CURRENT_LIST_DIR}/../../../../.cache/llama.cpp-ece963f41")
endif()
get_filename_component(LLAMA_CPP_SOURCE "${LLAMA_CPP_SOURCE_DIR}" REALPATH)
if(NOT EXISTS "${LLAMA_CPP_SOURCE}/include/llama.h")
    message(FATAL_ERROR "Pinned llama.cpp source is missing: ${LLAMA_CPP_SOURCE}")
endif()

# This is a collision-isolated APK. Build llama/ggml as their ordinary shared libraries so the
# pinned runtime can select the best packaged ARM CPU backend at runtime.
set(BUILD_SHARED_LIBS ON CACHE BOOL "" FORCE)
set(LLAMA_BUILD_COMMON ON CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_SERVER OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_APP OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_UI OFF CACHE BOOL "" FORCE)
set(LLAMA_USE_PREBUILT_UI OFF CACHE BOOL "" FORCE)
set(LLAMA_BUILD_MTMD OFF CACHE BOOL "" FORCE)
set(LLAMA_OPENSSL OFF CACHE BOOL "" FORCE)
set(LLAMA_SUBPROCESS OFF CACHE BOOL "" FORCE)
set(LLAMA_LLGUIDANCE OFF CACHE BOOL "" FORCE)

set(GGML_NATIVE OFF CACHE BOOL "" FORCE)
set(GGML_BACKEND_DL ON CACHE BOOL "" FORCE)
set(GGML_CPU_ALL_VARIANTS ON CACHE BOOL "" FORCE)
set(GGML_CPU_ARM_ARCH "" CACHE STRING "" FORCE)
set(GGML_CPU ON CACHE BOOL "" FORCE)
set(GGML_CPU_KLEIDIAI OFF CACHE BOOL "" FORCE)
set(GGML_OPENMP OFF CACHE BOOL "" FORCE)
set(GGML_LLAMAFILE OFF CACHE BOOL "" FORCE)
set(GGML_BLAS OFF CACHE BOOL "" FORCE)
set(GGML_STATIC OFF CACHE BOOL "" FORCE)
set(GGML_LTO OFF CACHE BOOL "" FORCE)
set(GGML_CCACHE OFF CACHE BOOL "" FORCE)
set(GGML_ALL_WARNINGS OFF CACHE BOOL "" FORCE)
set(GGML_FATAL_WARNINGS OFF CACHE BOOL "" FORCE)
set(GGML_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(GGML_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(GGML_CUDA OFF CACHE BOOL "" FORCE)
set(GGML_HIP OFF CACHE BOOL "" FORCE)
set(GGML_METAL OFF CACHE BOOL "" FORCE)
set(GGML_VULKAN OFF CACHE BOOL "" FORCE)
set(GGML_OPENCL OFF CACHE BOOL "" FORCE)
set(GGML_RPC OFF CACHE BOOL "" FORCE)
set(GGML_SYCL OFF CACHE BOOL "" FORCE)
set(GGML_WEBGPU OFF CACHE BOOL "" FORCE)
set(GGML_HEXAGON OFF CACHE BOOL "" FORCE)

add_subdirectory("${LLAMA_CPP_SOURCE}" llama.cpp-build EXCLUDE_FROM_ALL)

add_library(s1_llama_benchmark SHARED native_llama.cpp)
set_target_properties(s1_llama_benchmark PROPERTIES
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON
)
target_compile_options(s1_llama_benchmark PRIVATE
    -Wall
    -Wextra
    -Wpedantic
    -Werror=return-type
)
string(STRIP
    "${CMAKE_CXX_FLAGS} ${CMAKE_CXX_FLAGS_RELEASE} -Wall -Wextra -Wpedantic -Werror=return-type"
    S1_NATIVE_COMPILE_FLAGS)
target_compile_definitions(s1_llama_benchmark PRIVATE
    S1_NATIVE_BUILD_TYPE="${CMAKE_BUILD_TYPE}"
    S1_NATIVE_COMPILER="${CMAKE_CXX_COMPILER_ID}-${CMAKE_CXX_COMPILER_VERSION}"
    S1_NATIVE_COMPILE_FLAGS="${S1_NATIVE_COMPILE_FLAGS}"
)
target_include_directories(s1_llama_benchmark PRIVATE
    "${LLAMA_CPP_SOURCE}/common"
    "${LLAMA_CPP_SOURCE}/include"
    "${LLAMA_CPP_SOURCE}/ggml/include"
    "${LLAMA_CPP_SOURCE}/vendor"
)
target_link_libraries(s1_llama_benchmark PRIVATE
    llama-common
    llama
    ggml
    android
    log
    dl
)
