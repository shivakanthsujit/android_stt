#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
model_file="${1:-}"
cases_file="${2:-$repo_dir/docs/evaluation/cleanup_personal_conversation_v3.jsonl}"
measured_repeats="${CLEANUP_EVAL_REPEATS:-3}"
warmup_runs="${CLEANUP_EVAL_WARMUPS:-1}"
timeout_seconds="${CLEANUP_EVAL_TIMEOUT_SECONDS:-1800}"
power_trace="${CLEANUP_EVAL_POWER_TRACE:-0}"
expected_model_sha="${CLEANUP_EVAL_MODEL_SHA256:-}"

cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

if [[ ! -f "$model_file" || "$(basename "$model_file")" != *.gguf ]]; then
    echo "Usage: $0 <cleanup-model.gguf> [cases.jsonl]" >&2
    exit 1
fi
if [[ ! -f "$cases_file" || "$cases_file" == *[Bb][Ll][Ii][Nn][Dd]* ]]; then
    echo "Cases must be a present, non-blind JSONL file" >&2
    exit 1
fi
if [[ ! "$measured_repeats" =~ ^[1-9][0-9]*$ || "$measured_repeats" -gt 10 ]]; then
    echo "CLEANUP_EVAL_REPEATS must be between 1 and 10" >&2
    exit 1
fi
if [[ ! "$warmup_runs" =~ ^[0-9]+$ || "$warmup_runs" -gt 10 ]]; then
    echo "CLEANUP_EVAL_WARMUPS must be between 0 and 10" >&2
    exit 1
fi
if [[ "$power_trace" != "0" && "$power_trace" != "1" ]]; then
    echo "CLEANUP_EVAL_POWER_TRACE must be 0 or 1" >&2
    exit 1
fi

model_name="$(basename "$model_file")"
if [[ ! "$model_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.gguf$ ]]; then
    echo "Cleanup model filename is not safe for device transfer" >&2
    exit 1
fi
actual_model_sha="$(shasum -a 256 "$model_file" | awk '{print $1}')"
if [[ -n "$expected_model_sha" && "$actual_model_sha" != "$expected_model_sha" ]]; then
    echo "Model SHA-256 mismatch: expected $expected_model_sha, found $actual_model_sha" >&2
    exit 1
fi
expected_model_sha="$actual_model_sha"

run_id="$(date -u +%Y%m%dT%H%M%SZ)-cleanup-pixel"
package_name="dev.localflow.dictation"
device_model_dir="/sdcard/Android/data/$package_name/files/models"
device_root="/sdcard/Android/data/$package_name/files/cleanup-eval"
device_result="$device_root/results-$run_id.jsonl"
device_error="$device_root/error-$run_id.json"
host_result_dir="$repo_dir/.cache/integration/results"
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
trap stop_power_trace EXIT INT TERM

"$repo_dir/scripts/install-debug.sh"
adb shell mkdir -p "$device_model_dir" "$device_root"
adb push "$model_file" "$device_model_dir/$model_name"
adb push "$cases_file" "$device_root/cases.jsonl"
adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard
adb shell am force-stop "$package_name"

if [[ "$power_trace" == "1" ]]; then
    trace_processor="${CLEANUP_EVAL_TRACE_PROCESSOR:-$repo_dir/.cache/stt-eval/tools/trace_processor_shell}"
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
    --ei measured_repeats "$measured_repeats" \
    --ei warmup_runs "$warmup_runs"

echo "Waiting for Pixel cleanup benchmark result: $run_id"
started_at="$(date +%s)"
while true; do
    if adb shell test -f "$device_result"; then
        break
    fi
    if adb shell test -f "$device_error"; then
        adb shell cat "$device_error" >&2
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
mkdir -p "$host_result_dir"
adb pull "$device_result" "$host_result"
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
echo "Raw result: $host_result"
echo "Summary: $host_summary"
if [[ "$power_trace" == "1" ]]; then
    echo "Power trace: $host_power_trace"
    echo "Power summary: $host_power_summary"
fi
