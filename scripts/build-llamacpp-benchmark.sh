#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="${LLAMACPP_SOURCE_DIR:-$repo_dir/.cache/llama.cpp-ece963f41}"
model_file="${S1_DIRECT_MODEL_FILE:-$repo_dir/.cache/integration/s1-mini-v1/s1-mini-q4_k_m.gguf}"
result_root="${S1_DIRECT_BUILD_RESULT_DIR:-$repo_dir/.cache/integration/llamacpp-builds}"
expected_model_sha="3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634"
expected_model_bytes="484219808"
expected_ndk="28.0.13004108"
expected_cmake="3.31.6"
expected_cmake_binary="3.31.6-g38307f9"

cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

if [[ ! -f "$model_file" || "$(basename "$model_file")" != "s1-mini-q4_k_m.gguf" ]]; then
    echo "Missing pinned S1-mini Q4_K_M model: $model_file" >&2
    exit 1
fi
actual_model_bytes="$(wc -c < "$model_file" | tr -d ' ')"
actual_model_sha="$(shasum -a 256 "$model_file" | awk '{print $1}')"
if [[ "$actual_model_bytes" != "$expected_model_bytes" ||
      "$actual_model_sha" != "$expected_model_sha" ]]; then
    echo "Pinned S1-mini model identity mismatch" >&2
    exit 1
fi

source_evidence="$($repo_dir/scripts/prepare-llamacpp-android-source.sh)"
if [[ "$source_evidence" != *"commit=ece963f41b0b02d7a0d61436ae365762c073a4c8"* ||
      "$source_evidence" != *"build=b10450"* ]]; then
    echo "Pinned llama.cpp source verification did not return the expected identity" >&2
    exit 1
fi

ndk_dir="$ANDROID_HOME/ndk/$expected_ndk"
cmake_dir="$ANDROID_HOME/cmake/$expected_cmake"
if [[ ! -d "$ndk_dir" || ! -f "$ndk_dir/source.properties" ]]; then
    echo "Pinned Android NDK is missing: $ndk_dir" >&2
    exit 1
fi
if ! grep -Eq "^Pkg.Revision[[:space:]]*=[[:space:]]*$expected_ndk([[:space:]]*)$" \
    "$ndk_dir/source.properties"; then
    echo "Android NDK source.properties does not match $expected_ndk" >&2
    exit 1
fi
if [[ ! -x "$cmake_dir/bin/cmake" || ! -x "$cmake_dir/bin/ninja" ||
      ! -f "$cmake_dir/source.properties" ]]; then
    echo "Pinned Android CMake/Ninja is missing: $cmake_dir" >&2
    exit 1
fi
if ! grep -Eq "^Pkg.Revision[[:space:]]*=[[:space:]]*$expected_cmake([[:space:]]*)$" \
    "$cmake_dir/source.properties"; then
    echo "Android CMake source.properties does not match $expected_cmake" >&2
    exit 1
fi
cmake_version="$($cmake_dir/bin/cmake --version | awk 'NR == 1 {print $3}')"
if [[ "$cmake_version" != "$expected_cmake_binary" ]]; then
    echo "Android CMake binary mismatch: expected $expected_cmake_binary, found $cmake_version" >&2
    exit 1
fi
javac_version="$($JAVA_HOME/bin/javac -version 2>&1 | awk '{print $2}')"
if [[ "$javac_version" != 17.* ]]; then
    echo "JDK 17 is required; found javac $javac_version" >&2
    exit 1
fi

build_id="$(date -u +%Y%m%dT%H%M%SZ)-llamacpp-b10450-android-release"
result_dir="$result_root/$build_id"
if [[ -e "$result_dir" ]]; then
    echo "Build evidence directory already exists: $result_dir" >&2
    exit 1
fi
mkdir -p "$result_dir"
printf '%s\n' "$source_evidence" > "$result_dir/source-identity.txt"

gradle_tasks=(
    :llamacpp-benchmark:testReleaseUnitTest
    :llamacpp-benchmark:assembleRelease
)
./gradlew --no-daemon \
    -PllamaCppSourceDir="$source_dir" \
    "${gradle_tasks[@]}" 2>&1 | tee "$result_dir/gradle.log"

apk="$repo_dir/llamacpp-benchmark/build/outputs/apk/release/llamacpp-benchmark-release.apk"
if [[ ! -f "$apk" ]]; then
    echo "Release APK was not produced: $apk" >&2
    exit 1
fi

cmake_matches="$(
    find "$repo_dir/llamacpp-benchmark/.cxx/RelWithDebInfo" \
        -type f -path '*/arm64-v8a/CMakeCache.txt' -print 2>/dev/null |
        while IFS= read -r candidate; do
            if grep -Fqx "LLAMA_CPP_SOURCE_DIR:UNINITIALIZED=$source_dir" "$candidate" &&
               grep -Fqx "CMAKE_BUILD_TYPE:STRING=Release" "$candidate" &&
               grep -Fqx "CMAKE_ANDROID_NDK:UNINITIALIZED=$ndk_dir" "$candidate"; then
                printf '%s\n' "$candidate"
            fi
        done
)"
cmake_match_count="$(printf '%s\n' "$cmake_matches" | awk 'NF {count++} END {print count+0}')"
if [[ "$cmake_match_count" != "1" ]]; then
    echo "Expected exactly one resolved pinned CMake cache; found $cmake_match_count" >&2
    exit 1
fi
cmake_cache="$cmake_matches"
cmake_hash_dir="$(basename "$(dirname "$(dirname "$cmake_cache")")")"
configure_command="$repo_dir/llamacpp-benchmark/build/intermediates/cxx/RelWithDebInfo/$cmake_hash_dir/logs/arm64-v8a/configure_command"
build_model="$repo_dir/llamacpp-benchmark/build/intermediates/cxx/RelWithDebInfo/$cmake_hash_dir/logs/arm64-v8a/build_model.json"
if [[ ! -f "$configure_command" || ! -f "$build_model" ]]; then
    echo "Resolved CMake command/model evidence is missing for $cmake_hash_dir" >&2
    exit 1
fi
cp "$cmake_cache" "$result_dir/CMakeCache.txt"
cp "$configure_command" "$result_dir/configure-command.txt"
cp "$build_model" "$result_dir/build-model.json"

python3 - "$apk" "$result_dir/build-manifest.json" "$build_id" "$model_file" \
    "$source_dir" "$JAVA_HOME" "$ANDROID_HOME" "$cmake_hash_dir" <<'PY'
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

apk, output, build_id, model, source, java_home, android_home, cmake_hash = map(Path, sys.argv[1:])

def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}

with zipfile.ZipFile(apk) as archive:
    names = sorted(name for name in archive.namelist() if name.endswith(".so"))
    if not names or any(not name.startswith("lib/arm64-v8a/") for name in names):
        raise SystemExit("APK native libraries are missing or contain a non-arm64 ABI")
    required = {
        "libllama.so", "libggml.so", "libggml-base.so", "libllama-common.so",
        "libs1_llama_benchmark.so",
    }
    basenames = {Path(name).name for name in names}
    if not required <= basenames:
        raise SystemExit(f"APK is missing native libraries: {sorted(required - basenames)}")
    native = []
    for name in names:
        data = archive.read(name)
        native.append({"apk_path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

root = output.parent
manifest = {
    "schema_version": 1,
    "build_id": str(build_id),
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "gradle_tasks": [
        ":llamacpp-benchmark:testReleaseUnitTest",
        ":llamacpp-benchmark:assembleRelease",
    ],
    "application_id": "dev.localflow.llamacppbenchmark",
    "build_type": "release",
    "llama_cpp": {
        "source_dir": str(source),
        "commit": "ece963f41b0b02d7a0d61436ae365762c073a4c8",
        "tree": "f59cbdf04f233655507cc98ee9f704b71bfd1403",
        "build": "b10450",
    },
    "toolchain": {
        "java_home": str(java_home),
        "android_home": str(android_home),
        "ndk_version": "28.0.13004108",
        "cmake_version": "3.31.6",
        "cmake_binary_version": "3.31.6-g38307f9",
    },
    "model": identity(model),
    "apk": identity(apk),
    "native_libraries": native,
    "resolved_cmake": {
        "hash_directory": str(cmake_hash),
        "cache": identity(root / "CMakeCache.txt"),
        "configure_command": identity(root / "configure-command.txt"),
        "build_model": identity(root / "build-model.json"),
    },
}
output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

printf 'Release APK: %s\n' "$apk"
printf 'Build evidence: %s\n' "$result_dir"
