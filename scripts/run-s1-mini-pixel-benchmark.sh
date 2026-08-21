#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model_file="${1:-$repo_dir/.cache/integration/s1-mini-v1/s1-mini-q4_k_m.gguf}"
cases_file="${2:-$repo_dir/docs/evaluation/cleanup_personal_conversation_v3.jsonl}"
tokenizer_json="${S1_MINI_TOKENIZER_JSON:-$repo_dir/.cache/integration/s1-mini-v1/bf16/tokenizer.json}"
tokenizer_python="${S1_MINI_TOKENIZER_PYTHON:-$repo_dir/.cache/integration/s1-mini-bf16-venv/bin/python}"
measured_repeats="${S1_MINI_PIXEL_REPEATS:-3}"
warmup_runs="${S1_MINI_PIXEL_WARMUPS:-1}"
timeout_seconds="${S1_MINI_PIXEL_TIMEOUT_SECONDS:-1800}"
power_trace="${S1_MINI_PIXEL_POWER_TRACE:-1}"
leap_cpu_threads="${S1_MINI_LEAP_CPU_THREADS:-implicit}"
leap_context_tokens="${S1_MINI_LEAP_CONTEXT_SIZE:-4096}"
leap_cache_memory_mb="${S1_MINI_LEAP_CACHE_MB:-0}"
expected_model_sha="3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634"

cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

case "$leap_cpu_threads" in
    implicit)
        leap_cpu_threads_extra=0
        ;;
    2|3|4)
        leap_cpu_threads_extra="$leap_cpu_threads"
        ;;
    *)
        echo "S1_MINI_LEAP_CPU_THREADS must be implicit, 2, 3, or 4" >&2
        exit 1
        ;;
esac
case "$leap_context_tokens" in
    4096|3072|2560)
        ;;
    *)
        echo "S1_MINI_LEAP_CONTEXT_SIZE must be 4096, 3072, or 2560" >&2
        exit 1
        ;;
esac
case "$leap_cache_memory_mb" in
    0|32|64)
        ;;
    *)
        echo "S1_MINI_LEAP_CACHE_MB must be 0, 32, or 64" >&2
        exit 1
        ;;
esac

if [[ ! -f "$model_file" || "$(basename "$model_file")" != "s1-mini-q4_k_m.gguf" ]]; then
    echo "Missing pinned S1-mini Q4_K_M model: $model_file" >&2
    exit 1
fi
if [[ ! -f "$cases_file" || "$cases_file" == *[Bb][Ll][Ii][Nn][Dd]* ]]; then
    echo "Cases must be a present, non-blind JSONL file" >&2
    exit 1
fi
if [[ ! -f "$tokenizer_json" || ! -x "$tokenizer_python" ]]; then
    echo "Pinned tokenizer or tokenizer Python is missing" >&2
    exit 1
fi
if [[ ! "$measured_repeats" =~ ^[1-9][0-9]*$ || "$measured_repeats" -gt 10 ]]; then
    echo "S1_MINI_PIXEL_REPEATS must be between 1 and 10" >&2
    exit 1
fi
if [[ ! "$warmup_runs" =~ ^[0-9]+$ || "$warmup_runs" -gt 10 ]]; then
    echo "S1_MINI_PIXEL_WARMUPS must be between 0 and 10" >&2
    exit 1
fi
if [[ "$power_trace" != "0" && "$power_trace" != "1" ]]; then
    echo "S1_MINI_PIXEL_POWER_TRACE must be 0 or 1" >&2
    exit 1
fi

actual_model_sha="$(shasum -a 256 "$model_file" | awk '{print $1}')"
if [[ "$actual_model_sha" != "$expected_model_sha" ]]; then
    echo "S1-mini SHA-256 mismatch: expected $expected_model_sha, found $actual_model_sha" >&2
    exit 1
fi

leap_config_suffix="leap-t${leap_cpu_threads}-ctx${leap_context_tokens}-cache${leap_cache_memory_mb}mb"
run_id="$(date -u +%Y%m%dT%H%M%SZ)-s1-mini-pixel-${leap_config_suffix}"
package_name="dev.localflow.dictation"
model_name="s1-mini-q4_k_m.gguf"
device_temp_model="/data/local/tmp/localflow-s1-mini-q4_k_m.gguf"
device_temp_cases="/data/local/tmp/localflow-s1-mini-cases.jsonl"
device_model="files/models/$model_name"
device_root="files/cleanup-eval"
device_cases="$device_root/cases.jsonl"
device_result="$device_root/results-$run_id.jsonl"
device_error="$device_root/error-$run_id.json"
host_result_dir="$repo_dir/.cache/integration/results"
prepared_cases="$host_result_dir/cases-$run_id.jsonl"
host_result="$host_result_dir/results-$run_id.jsonl"
host_summary="$host_result_dir/summary-$run_id.json"
device_power_trace="/data/misc/perfetto-traces/localflow-$run_id.pftrace"
host_power_trace="$host_result_dir/power-$run_id.pftrace"
host_power_summary="$host_result_dir/power-summary-$run_id.json"
trace_pid=""

stop_power_trace() {
    if [[ "$trace_pid" =~ ^[0-9]+$ ]]; then
        adb shell kill -TERM "$trace_pid" >/dev/null 2>&1 || true
        for _ in {1..20}; do
            if ! adb shell kill -0 "$trace_pid" >/dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        trace_pid=""
    fi
}
cleanup_device_temp() {
    if [[ "$device_temp_model" == "/data/local/tmp/localflow-s1-mini-q4_k_m.gguf" &&
          "$device_temp_cases" == "/data/local/tmp/localflow-s1-mini-cases.jsonl" ]]; then
        adb shell rm -f "/data/local/tmp/localflow-s1-mini-q4_k_m.gguf" >/dev/null 2>&1 || true
        adb shell rm -f "/data/local/tmp/localflow-s1-mini-cases.jsonl" >/dev/null 2>&1 || true
    fi
}
trap 'stop_power_trace; cleanup_device_temp' EXIT INT TERM

mkdir -p "$host_result_dir"
"$tokenizer_python" "$repo_dir/scripts/prepare-s1-mini-pixel-cases.py" \
    "$cases_file" \
    --tokenizer-json "$tokenizer_json" \
    --output "$prepared_cases"

"$repo_dir/scripts/install-debug.sh"
adb shell run-as "$package_name" mkdir -p files/models files/cleanup-eval
existing_device_model_sha="$(
    adb exec-out run-as "$package_name" sha256sum "$device_model" 2>/dev/null |
        tr -d '\r' | awk '{print $1}' || true
)"
if [[ "$existing_device_model_sha" != "$expected_model_sha" ]]; then
    adb push "$model_file" "$device_temp_model"
    adb shell chmod 0644 "$device_temp_model"
    adb shell run-as "$package_name" cp "$device_temp_model" "$device_model"
fi
adb push "$prepared_cases" "$device_temp_cases"
adb shell chmod 0644 "$device_temp_cases"
adb shell run-as "$package_name" cp "$device_temp_cases" "$device_cases"
cleanup_device_temp

device_model_sha="$(adb exec-out run-as "$package_name" sha256sum "$device_model" | tr -d '\r' | awk '{print $1}')"
if [[ "$device_model_sha" != "$expected_model_sha" ]]; then
    echo "Device S1-mini SHA-256 mismatch: expected $expected_model_sha, found $device_model_sha" >&2
    exit 1
fi

adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard
adb shell am force-stop "$package_name"
thermal_status="$(
    adb shell dumpsys thermalservice | tr -d '\r' |
        awk -F': ' '/Thermal Status:/ {print $2; exit}'
)"
if [[ "$thermal_status" != "0" ]]; then
    echo "Pixel must start at thermal status 0; found ${thermal_status:-unknown}" >&2
    exit 1
fi

if [[ "$power_trace" == "1" ]]; then
    trace_processor="${S1_MINI_PIXEL_TRACE_PROCESSOR:-$repo_dir/.cache/stt-eval/tools/trace_processor_shell}"
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

adb shell am start -W \
    -n "$package_name/.stt.benchmark.CleanupBenchmarkActivity" \
    --es run_id "$run_id" \
    --es model_file_name "$model_name" \
    --es model_sha256 "$expected_model_sha" \
    --es engine_profile "s1-mini-v1-publisher" \
    --ei measured_repeats "$measured_repeats" \
    --ei warmup_runs "$warmup_runs" \
    --ei leap_cpu_threads "$leap_cpu_threads_extra" \
    --ei leap_context_tokens "$leap_context_tokens" \
    --ei leap_cache_memory_mb "$leap_cache_memory_mb"

echo "Waiting for exact-contract S1-mini Pixel result: $run_id"
started_at="$(date +%s)"
while true; do
    if adb shell run-as "$package_name" test -f "$device_result"; then
        break
    fi
    if adb shell run-as "$package_name" test -f "$device_error"; then
        adb exec-out run-as "$package_name" cat "$device_error" >&2
        exit 1
    fi
    now="$(date +%s)"
    if (( now - started_at >= timeout_seconds )); then
        echo "Timed out after ${timeout_seconds}s; the Activity remains available for inspection." >&2
        exit 1
    fi
    sleep 2
done

stop_power_trace
adb exec-out run-as "$package_name" cat "$device_result" > "$host_result"
python3 "$repo_dir/scripts/score-cleanup-pixel-results.py" \
    "$host_result" --cases "$cases_file" --json-out "$host_summary"
if [[ "$power_trace" == "1" ]]; then
    adb pull "$device_power_trace" "$host_power_trace"
    python3 "$repo_dir/scripts/score-stt-power-trace.py" \
        "$host_power_trace" \
        --trace-processor "$trace_processor" \
        --trace-section localflow_cleanup_benchmark \
        --inference-section localflow_cleanup_inference \
        --json-out "$host_power_summary"
fi

echo "Prepared cases: $prepared_cases"
echo "Raw result: $host_result"
echo "Summary: $host_summary"
if [[ "$power_trace" == "1" ]]; then
    echo "Power trace: $host_power_trace"
    echo "Power summary: $host_power_summary"
fi
