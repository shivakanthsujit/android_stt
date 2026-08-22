#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
artifact_root=/data/rise/android_stt/litert-conversion
environment_path=${artifact_root}/env

if [[ $(uname -s) != Linux || $(uname -m) != x86_64 ]]; then
  echo "LiteRT conversion requires a Linux x86_64 host." >&2
  exit 1
fi
if [[ ! -d /data/rise/android_stt || ! -w /data/rise/android_stt ]]; then
  echo "Artifact root parent is absent or not writable: /data/rise/android_stt" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required." >&2
  exit 1
fi

available_kib=$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)
if [[ -z ${available_kib} || ${available_kib} -lt 30000000 ]]; then
  echo "At least 30,000,000 KiB of available RAM is required for the full export." >&2
  exit 1
fi
available_bytes=$(df --output=avail -B1 /data/rise/android_stt | tail -n 1 | tr -d ' ')
if [[ -z ${available_bytes} || ${available_bytes} -lt 50000000000 ]]; then
  echo "At least 50 GB free under /data/rise/android_stt is required." >&2
  exit 1
fi

mkdir -p "${artifact_root}/cache/uv" "${artifact_root}/runs"
export UV_PROJECT_ENVIRONMENT="${environment_path}"
export UV_CACHE_DIR="${artifact_root}/cache/uv"
uv sync --project "${repo_root}/conversion" --locked --no-dev
uv pip check --python "${environment_path}/bin/python"
