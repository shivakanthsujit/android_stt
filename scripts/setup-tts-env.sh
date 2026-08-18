#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
project="$repo_dir/tts"
environment="$repo_dir/.cache/tts-eval/uv-env"
cache="$repo_dir/.cache/tts-eval/uv-cache"

mkdir -p "$repo_dir/.cache/tts-eval"
UV_PROJECT_ENVIRONMENT="$environment" UV_CACHE_DIR="$cache" \
    uv sync --project "$project" --frozen
UV_PROJECT_ENVIRONMENT="$environment" UV_CACHE_DIR="$cache" \
    uv run --project "$project" --frozen python -c \
    'import importlib.metadata; print("mlx-audio", importlib.metadata.version("mlx-audio"))'
