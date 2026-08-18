cmake_minimum_required(VERSION 3.18)
project(localflow_parakeet_jni LANGUAGES CXX)

if(NOT DEFINED PARAKEET_SOURCE_DIR OR NOT EXISTS "${PARAKEET_SOURCE_DIR}/include/parakeet_capi.h")
    message(FATAL_ERROR "PARAKEET_SOURCE_DIR must point to pinned parakeet.cpp source")
endif()
if(NOT DEFINED PARAKEET_LIBRARY OR NOT EXISTS "${PARAKEET_LIBRARY}")
    message(FATAL_ERROR "PARAKEET_LIBRARY must point to the Android libparakeet.so")
endif()

add_library(parakeet SHARED IMPORTED)
set_target_properties(parakeet PROPERTIES IMPORTED_LOCATION "${PARAKEET_LIBRARY}")

add_library(localflow_parakeet_jni SHARED parakeet_jni.cpp)
target_compile_features(localflow_parakeet_jni PRIVATE cxx_std_17)
target_include_directories(localflow_parakeet_jni PRIVATE "${PARAKEET_SOURCE_DIR}/include")
target_link_libraries(localflow_parakeet_jni PRIVATE parakeet log)
