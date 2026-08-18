#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
corpus_dir="${1:-$repo_dir/.cache/stt-eval/librispeech-test-clean-24}"
measured_repeats="${STT_EVAL_REPEATS:-3}"
warmup_runs="${STT_EVAL_WARMUPS:-1}"
timeout_seconds="${STT_EVAL_TIMEOUT_SECONDS:-1800}"
engine="${STT_EVAL_ENGINE:-moonshine}"
power_trace="${STT_EVAL_POWER_TRACE:-0}"

cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

if [[ ! -f "$corpus_dir/manifest.jsonl" || ! -d "$corpus_dir/audio" ]]; then
    echo "Corpus is missing. Run: ./scripts/prepare-librispeech-stt-eval.py" >&2
    exit 1
fi
if [[ ! "$measured_repeats" =~ ^[1-9][0-9]*$ || "$measured_repeats" -gt 10 ]]; then
    echo "STT_EVAL_REPEATS must be between 1 and 10" >&2
    exit 1
fi
if [[ ! "$warmup_runs" =~ ^[0-9]+$ || "$warmup_runs" -gt 10 ]]; then
    echo "STT_EVAL_WARMUPS must be between 0 and 10" >&2
    exit 1
fi
if [[ "$power_trace" != "0" && "$power_trace" != "1" ]]; then
    echo "STT_EVAL_POWER_TRACE must be 0 or 1" >&2
    exit 1
fi

engine_args=(--es engine "$engine")
model_file=""
model_variant=""
case "$engine" in
    moonshine)
        run_label="moonshine"
        ;;
    parakeet)
        model_file="${STT_EVAL_MODEL:-}"
        model_variant="${STT_EVAL_MODEL_VARIANT:-}"
        if [[ ! -f "$model_file" ]]; then
            echo "STT_EVAL_MODEL must name a Parakeet GGUF file" >&2
            exit 1
        fi
        if [[ ! "$model_variant" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
            echo "STT_EVAL_MODEL_VARIANT is required and must be a safe identifier" >&2
            exit 1
        fi
        if [[ ! -f "$repo_dir/app/src/debug/jniLibs/arm64-v8a/libparakeet.so" || \
              ! -f "$repo_dir/app/src/debug/jniLibs/arm64-v8a/liblocalflow_parakeet_jni.so" ]]; then
            echo "Parakeet Android libraries are missing. Run ./scripts/build-parakeet-android.sh" >&2
            exit 1
        fi
        run_label="parakeet-$model_variant"
        device_model_name="$(basename "$model_file")"
        if [[ ! "$device_model_name" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.gguf$ ]]; then
            echo "Parakeet model filename is not safe for device transfer" >&2
            exit 1
        fi
        engine_args+=(
            --es model_file "models/$device_model_name"
            --es model_variant "$model_variant"
        )
        ;;
    *)
        echo "STT_EVAL_ENGINE must be moonshine or parakeet" >&2
        exit 1
        ;;
esac

run_id="$(date -u +%Y%m%dT%H%M%SZ)-$run_label"
device_root="/sdcard/Android/data/dev.localflow.dictation/files/stt-eval"
device_result="$device_root/results-$run_id.jsonl"
device_error="$device_root/error-$run_id.json"
host_result_dir="$repo_dir/.cache/stt-eval/results"
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
adb shell mkdir -p "$device_root/audio"
adb push "$corpus_dir/manifest.jsonl" "$device_root/manifest.jsonl"
adb push "$corpus_dir/audio/." "$device_root/audio"
if [[ "$engine" == "parakeet" ]]; then
    adb shell mkdir -p "$device_root/models"
    adb push "$model_file" "$device_root/models/$device_model_name"
fi
adb shell am force-stop dev.localflow.dictation
if [[ "$power_trace" == "1" ]]; then
    trace_processor="${STT_EVAL_TRACE_PROCESSOR:-$repo_dir/.cache/stt-eval/tools/trace_processor_shell}"
    if [[ ! -x "$trace_processor" ]]; then
        echo "Trace processor is missing or not executable: $trace_processor" >&2
        exit 1
    fi
    trace_pid="$(
        adb shell perfetto \
            --background-wait \
            --txt \
            -c - \
            -o "$device_power_trace" \
            < "$repo_dir/scripts/perfetto-stt-power.pbtxt" \
            | tr -d '\r'
    )"
    if [[ ! "$trace_pid" =~ ^[0-9]+$ ]]; then
        echo "Perfetto did not return a valid PID: $trace_pid" >&2
        exit 1
    fi
fi
adb shell am start -W \
    -n dev.localflow.dictation/.stt.benchmark.SttBenchmarkActivity \
    --es run_id "$run_id" \
    --ei measured_repeats "$measured_repeats" \
    --ei warmup_runs "$warmup_runs" \
    "${engine_args[@]}"

echo "Waiting for Pixel benchmark result: $run_id"
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
python3 "$repo_dir/scripts/score-stt-results.py" "$host_result" --json-out "$host_summary"
if [[ "$power_trace" == "1" ]]; then
    adb pull "$device_power_trace" "$host_power_trace"
    python3 "$repo_dir/scripts/score-stt-power-trace.py" \
        "$host_power_trace" \
        --trace-processor "$trace_processor" \
        --json-out "$host_power_summary"
fi
echo "Raw result: $host_result"
echo "Summary: $host_summary"
if [[ "$power_trace" == "1" ]]; then
    echo "Power trace: $host_power_trace"
    echo "Power summary: $host_power_summary"
fi
