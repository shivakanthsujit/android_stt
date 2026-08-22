#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend="${1:-cpu}"
model_file="${S1_LITERT_MODEL:-$repo_dir/.cache/integration/s1-mini-litert-v1/20260822T062056Z/model.litertlm}"
cases_file="${S1_LITERT_CASES:-$repo_dir/scripts/fixtures/s1-mini-litert-smoke-v1.jsonl}"
profile="${S1_LITERT_PROFILE:-smoke}"
apk="$repo_dir/litertlm-android-benchmark/build/outputs/apk/release/litertlm-android-benchmark-release.apk"
device_serial="${ANDROID_SERIAL:-}"
expected_sha="8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403"
expected_bytes="436596864"
package_name="dev.localflow.litertlmbenchmark"
component="$package_name/.LiteRtLmBenchmarkActivity"
model_name="s1-mini-block32-ctx4096.litertlm"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-s1-litert-${backend}-${profile}"
results_root="$repo_dir/.cache/integration/results"
host_result="$results_root/results-$run_id.jsonl"
host_summary="$results_root/summary-$run_id.json"
host_error="$results_root/error-$run_id.json"
host_log="$results_root/logcat-$run_id.txt"
device_result="files/benchmark/results-$run_id.jsonl"
device_error="files/benchmark/error-$run_id.json"
device_model="files/models/$model_name"
device_cases="files/benchmark/cases.jsonl"
device_temp_model="/data/local/tmp/s1-litert-$run_id.litertlm"
device_temp_cases="/data/local/tmp/s1-litert-$run_id.jsonl"

case "$backend" in cpu|gpu) ;; *) echo "backend must be cpu or gpu" >&2; exit 1 ;; esac
[[ "$profile" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || {
    echo "S1_LITERT_PROFILE is not a safe name" >&2
    exit 1
}
case "$cases_file" in
    docs/evaluation/*|*/docs/evaluation/*|*[Bb][Ll][Ii][Nn][Dd]*)
        echo "evaluation and blind cases are prohibited" >&2
        exit 1
        ;;
esac
if [[ -z "$device_serial" || "$device_serial" == *[[:space:]]* ]]; then
    echo "Set ANDROID_SERIAL to the intended Pixel" >&2
    exit 1
fi
export ANDROID_SERIAL="$device_serial"

cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"
for file in "$model_file" "$cases_file" "$apk"; do
    [[ -f "$file" ]] || { echo "missing required file: $file" >&2; exit 1; }
done
model_bytes="$(wc -c < "$model_file" | tr -d ' ')"
model_sha="$(shasum -a 256 "$model_file" | awk '{print $1}')"
if [[ "$model_bytes" != "$expected_bytes" || "$model_sha" != "$expected_sha" ]]; then
    echo "LiteRT-LM artifact identity mismatch" >&2
    exit 1
fi
authorized="$(adb devices | awk '$2 == "device" {print $1}')"
authorized_count="$(printf '%s\n' "$authorized" | awk 'NF {count++} END {print count+0}')"
if [[ "$authorized_count" != "1" || "$authorized" != "$device_serial" ]]; then
    echo "Expected exactly one authorized device matching ANDROID_SERIAL" >&2
    exit 1
fi
product="$(adb shell getprop ro.product.device | tr -d '\r')"
abi="$(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
[[ "$product" == "panther" && "$abi" == "arm64-v8a" ]] || {
    echo "Expected Pixel 7 panther/arm64-v8a; found $product/$abi" >&2
    exit 1
}
available_kb="$(adb shell df -k /data | tr -d '\r' | awk 'NR==2 {print $4}')"
if [[ ! "$available_kb" =~ ^[0-9]+$ || "$available_kb" -lt 1200000 ]]; then
    echo "Insufficient /data headroom: ${available_kb:-unknown} KiB" >&2
    exit 1
fi

mkdir -p "$results_root"
for target in "$host_result" "$host_summary" "$host_error" "$host_log"; do
    [[ ! -e "$target" ]] || { echo "refusing to overwrite $target" >&2; exit 1; }
done

cleanup_temp() {
    if [[ "$device_temp_model" == /data/local/tmp/s1-litert-*.litertlm &&
          "$device_temp_cases" == /data/local/tmp/s1-litert-*.jsonl ]]; then
        adb shell rm -f "$device_temp_model" "$device_temp_cases" >/dev/null 2>&1 || true
    fi
}
trap cleanup_temp EXIT INT TERM

adb install -r "$apk"
adb shell run-as "$package_name" mkdir -p files/models files/benchmark
existing_sha="$(adb exec-out run-as "$package_name" sha256sum "$device_model" 2>/dev/null | tr -d '\r' | awk '{print $1}' || true)"
if [[ "$existing_sha" != "$expected_sha" ]]; then
    adb push "$model_file" "$device_temp_model"
    adb shell chmod 0644 "$device_temp_model"
    adb shell run-as "$package_name" cp "$device_temp_model" "$device_model"
    adb shell rm -f "$device_temp_model"
fi
adb push "$cases_file" "$device_temp_cases"
adb shell chmod 0644 "$device_temp_cases"
adb shell run-as "$package_name" cp "$device_temp_cases" "$device_cases"
adb shell rm -f "$device_temp_cases"

device_sha="$(adb exec-out run-as "$package_name" sha256sum "$device_model" | tr -d '\r' | awk '{print $1}')"
[[ "$device_sha" == "$expected_sha" ]] || { echo "device model SHA-256 mismatch" >&2; exit 1; }
adb shell am force-stop "$package_name"
thermal="$(adb shell dumpsys thermalservice | tr -d '\r' | awk -F': ' '/Thermal Status:/ {print $2; exit}')"
[[ "$thermal" == "0" ]] || { echo "Pixel thermal status must be 0; found ${thermal:-unknown}" >&2; exit 1; }

start_output="$(adb shell am start -W -n "$component" \
    --es run_id "$run_id" \
    --es model_file_name "$model_name" \
    --es model_sha256 "$expected_sha" \
    --es backend "$backend" \
    --ei cpu_threads 2 \
    --ei measured_repeats 1 \
    --ei warmup_runs 1)"
grep -q 'Status: ok' <<< "$start_output" || { echo "$start_output" >&2; exit 1; }

echo "Waiting for LiteRT-LM $backend smoke: $run_id"
started_at="$(date +%s)"
pid=""
while true; do
    pid="$(adb shell pidof "$package_name" | tr -d '\r' || true)"
    if adb shell run-as "$package_name" test -f "$device_result"; then break; fi
    if adb shell run-as "$package_name" test -f "$device_error"; then
        adb exec-out run-as "$package_name" cat "$device_error" > "$host_error"
        [[ -n "$pid" ]] && adb logcat -d --pid "$pid" > "$host_log" || true
        sed -n '1,160p' "$host_error" >&2
        exit 1
    fi
    if (( $(date +%s) - started_at >= 600 )); then
        [[ -n "$pid" ]] && adb logcat -d --pid "$pid" > "$host_log" || true
        echo "timed out waiting for LiteRT-LM smoke" >&2
        exit 1
    fi
    sleep 2
done
[[ -n "$pid" ]] && adb logcat -d --pid "$pid" > "$host_log" || true
adb exec-out run-as "$package_name" cat "$device_result" > "$host_result"
python3 "$repo_dir/scripts/validate-s1-mini-litert-pixel-results.py" \
    "$host_result" --cases "$cases_file" --backend "$backend" --json-out "$host_summary"
echo "Result: $host_result"
echo "Summary: $host_summary"
echo "Logcat: $host_log"
