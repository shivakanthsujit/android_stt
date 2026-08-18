#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

parakeet_version="0.5.0"
parakeet_commit="1bfbebfaaf493866f49597cd3b7901959d395c60"
ggml_commit="e705c5fed490514458bdd2eaddc43bd098fcce9b"
ndk_version="28.0.13004108"
cmake_version="3.31.6"
source_dir="${PARAKEET_SOURCE_DIR:-$repo_dir/.cache/stt-eval/parakeet-src-v$parakeet_version}"
build_root="$repo_dir/.cache/stt-eval/parakeet-android-v$parakeet_version"
parakeet_build="$build_root/parakeet"
jni_build="$build_root/jni"
package_dir="$repo_dir/app/src/debug/jniLibs/arm64-v8a"
ndk_dir="$ANDROID_HOME/ndk/$ndk_version"
cmake_dir="$ANDROID_HOME/cmake/$cmake_version"
openmp_library="$ndk_dir/toolchains/llvm/prebuilt/darwin-x86_64/lib/clang/19/lib/linux/aarch64/libomp.so"

if [[ ! -f "$ndk_dir/source.properties" ]]; then
    echo "Android NDK $ndk_version is not installed completely." >&2
    exit 1
fi
if [[ ! -x "$cmake_dir/bin/cmake" || ! -x "$cmake_dir/bin/ninja" ]]; then
    echo "Android SDK CMake $cmake_version is not installed." >&2
    exit 1
fi
if [[ ! -f "$openmp_library" ]]; then
    echo "Android NDK ARM64 OpenMP runtime was not found: $openmp_library" >&2
    exit 1
fi

if [[ ! -d "$source_dir/.git" ]]; then
    if [[ -e "$source_dir" ]]; then
        echo "Refusing to replace non-git source path: $source_dir" >&2
        exit 1
    fi
    git clone \
        --branch "v$parakeet_version" \
        --depth 1 \
        --recurse-submodules \
        --shallow-submodules \
        https://github.com/mudler/parakeet.cpp.git \
        "$source_dir"
fi

actual_parakeet_commit="$(git -C "$source_dir" rev-parse HEAD)"
actual_ggml_commit="$(git -C "$source_dir/third_party/ggml" rev-parse HEAD)"
if [[ "$actual_parakeet_commit" != "$parakeet_commit" ]]; then
    echo "Unexpected parakeet.cpp commit: $actual_parakeet_commit" >&2
    exit 1
fi
if [[ "$actual_ggml_commit" != "$ggml_commit" ]]; then
    echo "Unexpected ggml commit: $actual_ggml_commit" >&2
    exit 1
fi

"$cmake_dir/bin/cmake" \
    -S "$source_dir" \
    -B "$parakeet_build" \
    -G Ninja \
    -DCMAKE_MAKE_PROGRAM="$cmake_dir/bin/ninja" \
    -DCMAKE_TOOLCHAIN_FILE="$ndk_dir/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-31 \
    -DANDROID_STL=c++_static \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DGGML_NATIVE=OFF \
    -DGGML_LLAMAFILE=OFF \
    -DPARAKEET_SHARED=ON \
    -DPARAKEET_BUILD_CLI=OFF \
    -DPARAKEET_BUILD_SERVER=OFF \
    -DPARAKEET_BUILD_TESTS=OFF \
    -DPARAKEET_VERSION="$parakeet_version"
"$cmake_dir/bin/cmake" --build "$parakeet_build" --target parakeet --parallel

parakeet_library="$parakeet_build/libparakeet.so"
if [[ ! -f "$parakeet_library" ]]; then
    echo "Expected library was not built: $parakeet_library" >&2
    exit 1
fi
"$cmake_dir/bin/cmake" \
    -S "$repo_dir/app/src/debug/cpp" \
    -B "$jni_build" \
    -G Ninja \
    -DCMAKE_MAKE_PROGRAM="$cmake_dir/bin/ninja" \
    -DCMAKE_TOOLCHAIN_FILE="$ndk_dir/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI=arm64-v8a \
    -DANDROID_PLATFORM=android-31 \
    -DANDROID_STL=c++_static \
    -DCMAKE_BUILD_TYPE=Release \
    -DPARAKEET_SOURCE_DIR="$source_dir" \
    -DPARAKEET_LIBRARY="$parakeet_library"
"$cmake_dir/bin/cmake" --build "$jni_build" --target localflow_parakeet_jni --parallel

jni_library="$jni_build/liblocalflow_parakeet_jni.so"
if [[ ! -f "$jni_library" ]]; then
    echo "Expected JNI library was not built: $jni_library" >&2
    exit 1
fi

mkdir -p "$package_dir"
cp "$parakeet_library" "$package_dir/libparakeet.so"
cp "$jni_library" "$package_dir/liblocalflow_parakeet_jni.so"
cp "$openmp_library" "$package_dir/libomp.so"

echo "Packaged Android ARM64 libraries:"
shasum -a 256 \
    "$package_dir/libparakeet.so" \
    "$package_dir/liblocalflow_parakeet_jni.so" \
    "$package_dir/libomp.so"
