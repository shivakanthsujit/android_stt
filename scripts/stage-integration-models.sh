#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$repo_dir/scripts/android-env.sh"

parakeet_model="${1:-$repo_dir/.cache/stt-eval/models/realtime_eou_120m-v1-q4_k.gguf}"
cleanup_model="${2:-$repo_dir/.cache/integration/s1-mini-v1/s1-mini-q4_k_m.gguf}"
package_name="dev.localflow.dictation"
device_temp_parakeet="/data/local/tmp/localflow-stage-parakeet.gguf"
device_temp_cleanup="/data/local/tmp/localflow-stage-s1-mini.gguf"
device_dir="files/models"
expected_parakeet_sha="ac9109d0e422bd8aafa899c0f58e1938f4a2846838797a29c04f6a8729033c3c"
expected_cleanup_sha="3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634"

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
require_hash "$expected_cleanup_sha" "$cleanup_model"

cleanup_temporary_files() {
    adb shell rm -f "/data/local/tmp/localflow-stage-parakeet.gguf" >/dev/null 2>&1 || true
    adb shell rm -f "/data/local/tmp/localflow-stage-s1-mini.gguf" >/dev/null 2>&1 || true
}
trap cleanup_temporary_files EXIT INT TERM

adb get-state >/dev/null
adb shell run-as "$package_name" mkdir -p "$device_dir"
adb push "$parakeet_model" "$device_temp_parakeet"
adb push "$cleanup_model" "$device_temp_cleanup"
adb shell chmod 0644 "$device_temp_parakeet" "$device_temp_cleanup"
adb shell run-as "$package_name" cp "$device_temp_parakeet" \
    "$device_dir/realtime_eou_120m-v1-q4_k.gguf"
adb shell run-as "$package_name" cp "$device_temp_cleanup" \
    "$device_dir/s1-mini-q4_k_m.gguf"

device_parakeet_sha="$(adb exec-out run-as "$package_name" sha256sum \
    "$device_dir/realtime_eou_120m-v1-q4_k.gguf" | tr -d '\r' | awk '{print $1}')"
device_cleanup_sha="$(adb exec-out run-as "$package_name" sha256sum \
    "$device_dir/s1-mini-q4_k_m.gguf" | tr -d '\r' | awk '{print $1}')"
if [[ "$device_parakeet_sha" != "$expected_parakeet_sha" ||
      "$device_cleanup_sha" != "$expected_cleanup_sha" ]]; then
    echo "Device model verification failed after staging" >&2
    exit 1
fi

echo "Staged verified Parakeet and S1-mini models in app-private $device_dir"
