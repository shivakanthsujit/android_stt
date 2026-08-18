#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$repo_dir/scripts/android-env.sh"

parakeet_model="${1:-$repo_dir/.cache/stt-eval/models/tdt_ctc-110m-q4_k.gguf}"
sotto_model="${2:-$repo_dir/.cache/integration/models/sotto-gguf-mapped/sotto-cleanup-lfm25-350m-q4_k_m.gguf}"
package_name="dev.localflow.dictation"
device_dir="/sdcard/Android/data/$package_name/files/models"
expected_parakeet_sha="2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf"
expected_sotto_sha="05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570"

require_hash() {
    local expected="$1"
    local file="$2"
    if [[ ! -f "$file" ]]; then
        echo "Missing model artifact: $file" >&2
        exit 1
    fi
    local actual
    actual="$(shasum -a 256 "$file" | awk '{print $1}')"
    if [[ "$actual" != "$expected" ]]; then
        echo "SHA-256 mismatch for $file: expected $expected, found $actual" >&2
        exit 1
    fi
}

require_hash "$expected_parakeet_sha" "$parakeet_model"
require_hash "$expected_sotto_sha" "$sotto_model"

adb get-state >/dev/null
adb shell mkdir -p "$device_dir"
adb push "$parakeet_model" "$device_dir/tdt_ctc-110m-q4_k.gguf"
adb push "$sotto_model" "$device_dir/sotto-cleanup-lfm25-350m-q4_k_m.gguf"

echo "Staged verified integration models under $device_dir"
