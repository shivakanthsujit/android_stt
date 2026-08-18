#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
input_path="${1:-}"
timeout_seconds="${JOINED_EVAL_TIMEOUT_SECONDS:-1800}"

if [[ -z "$input_path" ]]; then
    echo "Usage: $0 <corpus-directory|audio.wav|audio.mp3>" >&2
    exit 1
fi
if [[ ! "$timeout_seconds" =~ ^[1-9][0-9]*$ ]]; then
    echo "JOINED_EVAL_TIMEOUT_SECONDS must be a positive integer" >&2
    exit 1
fi

cd "$repo_dir"
. "$repo_dir/scripts/android-env.sh"

temporary_dir=""
cleanup() {
    if [[ -n "$temporary_dir" && -d "$temporary_dir" && ! -L "$temporary_dir" && \
          "$temporary_dir" == /private/tmp/localflow-joined.* ]]; then
        rm -rf -- "$temporary_dir"
    fi
}
trap cleanup EXIT INT TERM

if [[ -d "$input_path" ]]; then
    corpus_dir="$(cd "$input_path" && pwd -P)"
    if [[ ! -f "$corpus_dir/manifest.jsonl" || ! -d "$corpus_dir/audio" ]]; then
        echo "Corpus must contain manifest.jsonl and audio/: $corpus_dir" >&2
        exit 1
    fi
elif [[ -f "$input_path" ]]; then
    if ! command -v ffmpeg >/dev/null 2>&1; then
        echo "ffmpeg is required for single WAV/MP3 input" >&2
        exit 1
    fi
    temporary_dir="$(mktemp -d /private/tmp/localflow-joined.XXXXXX)"
    if [[ -z "$temporary_dir" || ! -d "$temporary_dir" || -L "$temporary_dir" || \
          "$temporary_dir" != /private/tmp/localflow-joined.* ]]; then
        echo "Could not create a validated temporary directory" >&2
        exit 1
    fi
    corpus_dir="$temporary_dir/corpus"
    mkdir -p "$corpus_dir/audio"
    source_name="$(basename "$input_path")"
    case_id="$(printf '%s' "${source_name%.*}" | tr -cs 'A-Za-z0-9._-' '-' | cut -c1-96)"
    case_id="${case_id#-}"
    case_id="${case_id%-}"
    if [[ ! "$case_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]]; then
        case_id="single-audio"
    fi
    canonical_audio="$corpus_dir/audio/$case_id.wav"
    ffmpeg -nostdin -hide_banner -loglevel error -y \
        -i "$input_path" -map_metadata -1 -ac 1 -ar 16000 -c:a pcm_s16le "$canonical_audio"
    audio_sha="$(shasum -a 256 "$canonical_audio" | awk '{print $1}')"
    python3 -c \
        'import json, pathlib, sys; pathlib.Path(sys.argv[1]).write_text(json.dumps({"case_id":sys.argv[2],"audio_file":"audio/"+sys.argv[2]+".wav","audio_sha256":sys.argv[3],"reference":sys.argv[4]},ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")' \
        "$corpus_dir/manifest.jsonl" "$case_id" "$audio_sha" "${JOINED_EVAL_REFERENCE:-}"
else
    echo "Input does not exist: $input_path" >&2
    exit 1
fi

if [[ "${JOINED_EVAL_INSTALL:-1}" == "1" ]]; then
    ./gradlew --offline assembleDebug
    adb install -r "$repo_dir/app/build/outputs/apk/debug/app-debug.apk"
elif [[ "${JOINED_EVAL_INSTALL:-1}" != "0" ]]; then
    echo "JOINED_EVAL_INSTALL must be 0 or 1" >&2
    exit 1
fi

run_id="$(date -u +%Y%m%dT%H%M%SZ)-joined-file"
device_root="/sdcard/Android/data/dev.localflow.dictation/files/joined-eval"
device_result="$device_root/results-$run_id.jsonl"
device_error="$device_root/error-$run_id.json"
host_result_dir="$repo_dir/.cache/integration/results"
host_result="$host_result_dir/results-$run_id.jsonl"
host_summary="$host_result_dir/summary-$run_id.json"
expected_cases="${JOINED_EVAL_EXPECTED_CASES:-}"
if [[ -z "$expected_cases" && -d "$input_path" ]]; then
    manifest_source="$(python3 -c 'import json, pathlib, sys; rows=[json.loads(line) for line in pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if line]; sources={row.get("source_path", "") for row in rows}; print(next(iter(sources)) if len(sources)==1 else "")' "$corpus_dir/manifest.jsonl")"
    case "$manifest_source" in
        docs/evaluation/stt_personal_conversation_tts_cases_v2.jsonl|\
        docs/evaluation/stt_personal_conversation_tts_cases_v3.jsonl)
            expected_cases="$repo_dir/$manifest_source"
            ;;
    esac
fi
if [[ -n "$expected_cases" && ! -f "$expected_cases" ]]; then
    echo "Expected-case file does not exist: $expected_cases" >&2
    exit 1
fi

adb shell mkdir -p "$device_root/audio"
adb push "$corpus_dir/manifest.jsonl" "$device_root/manifest.jsonl"
adb push "$corpus_dir/audio/." "$device_root/audio"
adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard
adb shell am force-stop dev.localflow.dictation
adb shell am start -W \
    -n dev.localflow.dictation/.stt.benchmark.JoinedPipelineBenchmarkActivity \
    --es run_id "$run_id"

echo "Waiting for joined file result: $run_id"
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

mkdir -p "$host_result_dir"
adb pull "$device_result" "$host_result"
score_args=("$host_result" --json-out "$host_summary")
if [[ -n "$expected_cases" ]]; then
    score_args+=(--expected-cases "$expected_cases")
fi
python3 "$repo_dir/scripts/score-joined-results.py" "${score_args[@]}"
echo "Raw result: $host_result"
echo "Summary: $host_summary"
