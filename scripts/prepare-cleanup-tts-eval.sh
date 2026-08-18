#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment="$repo_dir/.cache/tts-eval/uv-env"
cache="$repo_dir/.cache/tts-eval/uv-cache"
hub_cache="$repo_dir/.cache/tts-eval/huggingface"

export HF_HUB_DISABLE_TELEMETRY=1
if [[ "${TTS_OFFLINE:-0}" == "1" ]]; then
    export HF_HUB_OFFLINE=1
    export TRANSFORMERS_OFFLINE=1
    export UV_OFFLINE=1
fi

UV_PROJECT_ENVIRONMENT="$environment" \
UV_CACHE_DIR="$cache" \
HF_HOME="$hub_cache" \
    uv run --project "$repo_dir/tts" --frozen \
    python "$repo_dir/scripts/prepare-cleanup-tts-eval.py" "$@"
