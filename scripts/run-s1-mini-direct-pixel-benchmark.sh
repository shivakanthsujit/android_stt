#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model_file="${1:-$repo_dir/.cache/integration/s1-mini-v1/s1-mini-q4_k_m.gguf}"
cases_file="${2:-}"
apk="${S1_DIRECT_APK:-$repo_dir/llamacpp-benchmark/build/outputs/apk/release/llamacpp-benchmark-release.apk}"
control_file="${S1_DIRECT_LEAP_CONTROL:-}"
context_tokens="${S1_DIRECT_CONTEXT_SIZE:-2560}"
generation_threads="${S1_DIRECT_GENERATION_THREADS:-2}"
batch_threads="${S1_DIRECT_BATCH_THREADS:-2}"
batch_size="${S1_DIRECT_BATCH_SIZE:-512}"
micro_batch_size="${S1_DIRECT_MICRO_BATCH_SIZE:-512}"
use_mmap="${S1_DIRECT_MMAP:-1}"
flash_attention="${S1_DIRECT_FLASH_ATTENTION:-0}"
gpu_layers="${S1_DIRECT_GPU_LAYERS:-0}"
measured_repeats="${S1_DIRECT_REPEATS:-3}"
warmup_runs="${S1_DIRECT_WARMUPS:-1}"
timeout_seconds="${S1_DIRECT_TIMEOUT_SECONDS:-1800}"
power_trace="${S1_DIRECT_POWER_TRACE:-0}"
expected_model_sha="3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634"
expected_model_bytes="484219808"
device_serial="${ANDROID_SERIAL:-}"

if [[ -z "$cases_file" ]]; then
    echo "Pass an explicit non-evaluation transcript JSONL as argument 2" >&2
    exit 1
fi
case "$cases_file" in
    docs/evaluation/*|*/docs/evaluation/*)
        echo "Evaluation corpora are prohibited as direct benchmark inputs" >&2
        exit 1
        ;;
esac

case "$context_tokens" in 2560) ;; *) echo "S1_DIRECT_CONTEXT_SIZE must be 2560" >&2; exit 1 ;; esac
case "$generation_threads" in 2|3|4|6|8) ;; *) echo "Invalid S1_DIRECT_GENERATION_THREADS" >&2; exit 1 ;; esac
case "$batch_threads" in 2|4|6|8) ;; *) echo "Invalid S1_DIRECT_BATCH_THREADS" >&2; exit 1 ;; esac
case "$batch_size" in 128|256|512) ;; *) echo "Invalid S1_DIRECT_BATCH_SIZE" >&2; exit 1 ;; esac
case "$micro_batch_size" in 128|256|512) ;; *) echo "Invalid S1_DIRECT_MICRO_BATCH_SIZE" >&2; exit 1 ;; esac
if (( micro_batch_size > batch_size )); then
    echo "S1_DIRECT_MICRO_BATCH_SIZE must not exceed S1_DIRECT_BATCH_SIZE" >&2
    exit 1
fi
case "$use_mmap" in 1) ;; *) echo "S1_DIRECT_MMAP must be 1" >&2; exit 1 ;; esac
case "$flash_attention" in 0|1) ;; *) echo "S1_DIRECT_FLASH_ATTENTION must be 0 or 1" >&2; exit 1 ;; esac
case "$gpu_layers" in 0) ;; *) echo "S1_DIRECT_GPU_LAYERS must be 0" >&2; exit 1 ;; esac
if [[ ! "$measured_repeats" =~ ^[1-9][0-9]*$ || "$measured_repeats" -gt 10 ]]; then
    echo "S1_DIRECT_REPEATS must be between 1 and 10" >&2
    exit 1
fi
if [[ ! "$warmup_runs" =~ ^[0-9]+$ || "$warmup_runs" -gt 10 ]]; then
    echo "S1_DIRECT_WARMUPS must be between 0 and 10" >&2
    exit 1
fi
if [[ ! "$timeout_seconds" =~ ^[1-9][0-9]*$ || "$timeout_seconds" -gt 7200 ]]; then
    echo "S1_DIRECT_TIMEOUT_SECONDS must be between 1 and 7200" >&2
    exit 1
fi
case "$power_trace" in 0|1) ;; *) echo "S1_DIRECT_POWER_TRACE must be 0 or 1" >&2; exit 1 ;; esac
if [[ -z "$device_serial" || "$device_serial" == *[[:space:]]* ]]; then
    echo "Set ANDROID_SERIAL to the one intended Pixel" >&2
    exit 1
fi
export ANDROID_SERIAL="$device_serial"

cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

if [[ ! -f "$model_file" || "$(basename "$model_file")" != "s1-mini-q4_k_m.gguf" ]]; then
    echo "Missing pinned S1-mini Q4_K_M model: $model_file" >&2
    exit 1
fi
model_bytes="$(wc -c < "$model_file" | tr -d ' ')"
model_sha="$(shasum -a 256 "$model_file" | awk '{print $1}')"
if [[ "$model_bytes" != "$expected_model_bytes" || "$model_sha" != "$expected_model_sha" ]]; then
    echo "Pinned S1-mini model identity mismatch" >&2
    exit 1
fi
if [[ ! -f "$cases_file" || "$cases_file" == *[Bb][Ll][Ii][Nn][Dd]* ]]; then
    echo "Cases must be a present, non-blind JSONL file" >&2
    exit 1
fi
if [[ ! -f "$apk" ]]; then
    echo "Missing llama.cpp release APK: $apk" >&2
    exit 1
fi
if [[ -n "$control_file" && ! -f "$control_file" ]]; then
    echo "Matched LEAP control is missing: $control_file" >&2
    exit 1
fi

config_suffix="c${context_tokens}-gt${generation_threads}-bt${batch_threads}-b${batch_size}-u${micro_batch_size}-mm${use_mmap}-fa${flash_attention}-g${gpu_layers}"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-s1-direct-${config_suffix}"
package_name="dev.localflow.llamacppbenchmark"
component="$package_name/.LlamaCppBenchmarkActivity"
model_name="s1-mini-q4_k_m.gguf"
device_temp_model="/data/local/tmp/s1-direct-model-$run_id.gguf"
device_temp_cases="/data/local/tmp/s1-direct-cases-$run_id.jsonl"
device_model="files/models/$model_name"
device_cases="files/benchmark/cases.jsonl"
device_result="files/benchmark/results-$run_id.jsonl"
device_partial="$device_result.partial"
device_error="files/benchmark/error-$run_id.json"
host_result_dir="$repo_dir/.cache/integration/results"
prepared_cases="$host_result_dir/cases-$run_id.jsonl"
host_result="$host_result_dir/results-$run_id.jsonl"
host_result_download="$host_result.download"
host_partial="$host_result_dir/partial-$run_id.jsonl"
host_error="$host_result_dir/error-$run_id.json"
host_summary="$host_result_dir/summary-$run_id.json"
host_run_manifest="$host_result_dir/run-manifest-$run_id.json"
device_power_trace="/data/misc/perfetto-traces/localflow-$run_id.pftrace"
host_power_trace="$host_result_dir/power-$run_id.pftrace"
host_power_summary="$host_result_dir/power-summary-$run_id.json"
trace_pid=""

stop_power_trace() {
    if [[ "$trace_pid" =~ ^[0-9]+$ ]]; then
        adb shell kill -TERM "$trace_pid" >/dev/null 2>&1 || true
        for _ in {1..20}; do
            if ! adb shell kill -0 "$trace_pid" >/dev/null 2>&1; then break; fi
            sleep 1
        done
        trace_pid=""
    fi
}
cleanup_device_temp() {
    if [[ "$device_temp_model" == /data/local/tmp/s1-direct-model-*.gguf &&
          "$device_temp_cases" == /data/local/tmp/s1-direct-cases-*.jsonl ]]; then
        adb shell rm -f "$device_temp_model" >/dev/null 2>&1 || true
        adb shell rm -f "$device_temp_cases" >/dev/null 2>&1 || true
    fi
}
retain_failure_artifacts() {
    if adb shell run-as "$package_name" test -f "$device_error" >/dev/null 2>&1; then
        adb exec-out run-as "$package_name" cat "$device_error" > "$host_error" || true
    fi
    if adb shell run-as "$package_name" test -f "$device_partial" >/dev/null 2>&1; then
        adb exec-out run-as "$package_name" cat "$device_partial" > "$host_partial" || true
    fi
}
trap 'stop_power_trace; cleanup_device_temp' EXIT INT TERM

mkdir -p "$host_result_dir"
for target in "$prepared_cases" "$host_result" "$host_partial" "$host_error" \
    "$host_summary" "$host_run_manifest" "$host_power_trace" "$host_power_summary" \
    "$host_result_download"; do
    if [[ -e "$target" ]]; then
        echo "Refusing to overwrite run artifact: $target" >&2
        exit 1
    fi
done
python3 "$repo_dir/scripts/prepare-s1-mini-direct-cases.py" \
    "$cases_file" --output "$prepared_cases"
prepared_sha="$(shasum -a 256 "$prepared_cases" | awk '{print $1}')"
apk_sha="$(shasum -a 256 "$apk" | awk '{print $1}')"
python3 - "$host_run_manifest" "$run_id" "$apk" "$apk_sha" "$model_file" \
    "$model_sha" "$cases_file" "$prepared_cases" "$prepared_sha" "$control_file" \
    "$context_tokens" "$generation_threads" "$batch_threads" "$batch_size" \
    "$micro_batch_size" "$use_mmap" "$flash_attention" "$gpu_layers" <<'PY'
import json
import sys
from pathlib import Path

(output, run_id, apk, apk_sha, model, model_sha, source_cases, prepared_cases,
 prepared_sha, control, context, gen_threads, batch_threads, batch, ubatch,
 mmap, flash, gpu) = sys.argv[1:]
manifest = {
    "schema_version": 1,
    "run_id": run_id,
    "application_id": "dev.localflow.llamacppbenchmark",
    "apk": {"path": apk, "sha256": apk_sha},
    "model": {"path": model, "bytes": 484219808, "sha256": model_sha},
    "source_cases": source_cases,
    "prepared_cases": {"path": prepared_cases, "sha256": prepared_sha},
    "matched_leap_control": control or None,
    "requested_config": {
        "context_tokens": int(context), "generation_threads": int(gen_threads),
        "batch_threads": int(batch_threads), "batch_size": int(batch),
        "micro_batch_size": int(ubatch), "use_mmap": mmap == "1",
        "flash_attention": flash == "1", "gpu_layers": int(gpu),
    },
}
Path(output).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

authorized_serials="$(adb devices | awk '$2 == "device" {print $1}')"
authorized_count="$(printf '%s\n' "$authorized_serials" | awk 'NF {count++} END {print count+0}')"
if [[ "$authorized_count" != "1" || "$authorized_serials" != "$device_serial" ]]; then
    echo "Expected exactly one authorized device matching ANDROID_SERIAL=$device_serial" >&2
    exit 1
fi
device_brand="$(adb shell getprop ro.product.brand | tr -d '\r')"
device_model_name="$(adb shell getprop ro.product.model | tr -d '\r')"
device_abi="$(adb shell getprop ro.product.cpu.abi | tr -d '\r')"
if [[ "$device_brand" != "google" || "$device_model_name" != Pixel* ||
      "$device_abi" != "arm64-v8a" ]]; then
    echo "Target must be a Google Pixel with arm64-v8a ABI; found $device_brand/$device_model_name/$device_abi" >&2
    exit 1
fi

adb install -r "$apk"
if ! adb shell pm path "$package_name" | tr -d '\r' | grep -q '^package:'; then
    echo "Installed package identity could not be verified: $package_name" >&2
    exit 1
fi
adb shell run-as "$package_name" mkdir -p files/models files/benchmark
existing_model_sha="$(
    adb exec-out run-as "$package_name" sha256sum "$device_model" 2>/dev/null |
        tr -d '\r' | awk '{print $1}' || true
)"
if [[ "$existing_model_sha" != "$expected_model_sha" ]]; then
    adb push "$model_file" "$device_temp_model"
    adb shell chmod 0644 "$device_temp_model"
    adb shell run-as "$package_name" cp "$device_temp_model" "$device_model"
fi
adb push "$prepared_cases" "$device_temp_cases"
adb shell chmod 0644 "$device_temp_cases"
adb shell run-as "$package_name" cp "$device_temp_cases" "$device_cases"
cleanup_device_temp

device_model_sha="$(adb exec-out run-as "$package_name" sha256sum "$device_model" | tr -d '\r' | awk '{print $1}')"
device_cases_sha="$(adb exec-out run-as "$package_name" sha256sum "$device_cases" | tr -d '\r' | awk '{print $1}')"
if [[ "$device_model_sha" != "$expected_model_sha" || "$device_cases_sha" != "$prepared_sha" ]]; then
    echo "Device model or transcript-only cases identity mismatch" >&2
    exit 1
fi

adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard
adb shell am force-stop "$package_name"
thermal_status="$(adb shell dumpsys thermalservice | tr -d '\r' | awk -F': ' '/Thermal Status:/ {print $2; exit}')"
if [[ "$thermal_status" != "0" ]]; then
    echo "Pixel must start at thermal status 0; found ${thermal_status:-unknown}" >&2
    exit 1
fi
python3 - "$host_run_manifest" "$thermal_status" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
manifest = json.loads(path.read_text(encoding="utf-8"))
manifest["start_thermal_status"] = int(sys.argv[2])
path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

if [[ "$power_trace" == "1" ]]; then
    trace_processor="${S1_DIRECT_TRACE_PROCESSOR:-$repo_dir/.cache/stt-eval/tools/trace_processor_shell}"
    if [[ ! -x "$trace_processor" ]]; then
        echo "Trace processor is missing or not executable: $trace_processor" >&2
        exit 1
    fi
    trace_pid="$(
        adb shell perfetto --background-wait --txt -c - -o "$device_power_trace" \
            < "$repo_dir/scripts/perfetto-stt-power.pbtxt" | tr -d '\r'
    )"
    if [[ ! "$trace_pid" =~ ^[0-9]+$ ]]; then
        echo "Perfetto did not return a valid PID: $trace_pid" >&2
        exit 1
    fi
fi

start_output="$(adb shell am start -W \
    -n "$component" \
    --es run_id "$run_id" \
    --es model_file_name "$model_name" \
    --es model_sha256 "$expected_model_sha" \
    --ei measured_repeats "$measured_repeats" \
    --ei warmup_runs "$warmup_runs" \
    --ei context_tokens "$context_tokens" \
    --ei generation_threads "$generation_threads" \
    --ei batch_threads "$batch_threads" \
    --ei batch_size "$batch_size" \
    --ei micro_batch_size "$micro_batch_size" \
    --ez use_mmap true \
    --ez flash_attention "$([[ "$flash_attention" == "1" ]] && echo true || echo false)" \
    --ei gpu_layers "$gpu_layers")"
if ! grep -q 'Status: ok' <<< "$start_output"; then
    echo "$start_output" >&2
    echo "Benchmark Activity did not start successfully" >&2
    exit 1
fi

echo "Waiting for isolated S1 llama.cpp result: $run_id"
started_at="$(date +%s)"
while true; do
    if adb shell run-as "$package_name" test -f "$device_result"; then break; fi
    if adb shell run-as "$package_name" test -f "$device_error"; then
        retain_failure_artifacts
        [[ -f "$host_error" ]] && sed -n '1,120p' "$host_error" >&2
        exit 1
    fi
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
        retain_failure_artifacts
        echo "Timed out after ${timeout_seconds}s; partial/error artifacts were retained when present" >&2
        exit 1
    fi
    sleep 2
done

stop_power_trace
adb exec-out run-as "$package_name" cat "$device_result" > "$host_result_download"
if [[ ! -s "$host_result_download" ]]; then
    echo "Retrieved direct result is empty" >&2
    exit 1
fi
mv "$host_result_download" "$host_result"
score_args=("$host_result" --json-out "$host_summary")
if [[ -n "$control_file" ]]; then score_args+=(--control "$control_file"); fi
python3 "$repo_dir/scripts/score-s1-mini-direct-results.py" "${score_args[@]}"

if [[ "$power_trace" == "1" ]]; then
    adb pull "$device_power_trace" "$host_power_trace"
    python3 "$repo_dir/scripts/score-stt-power-trace.py" \
        "$host_power_trace" \
        --trace-processor "$trace_processor" \
        --trace-section localflow_llamacpp_benchmark \
        --inference-section localflow_llamacpp_inference \
        --json-out "$host_power_summary"
fi

echo "Run manifest: $host_run_manifest"
echo "Prepared transcript-only cases: $prepared_cases"
echo "Raw result: $host_result"
echo "Summary: $host_summary"
if [[ "$power_trace" == "1" ]]; then
    echo "Power trace: $host_power_trace"
    echo "Power summary: $host_power_summary"
fi
