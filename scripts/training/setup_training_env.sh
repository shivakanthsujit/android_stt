#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
artifact_root=/data/rise/android_stt
environment_path=${artifact_root}/env
lock_path=${repo_root}/training/uv.lock

if [[ ! -f "${lock_path}" ]]; then
  echo "Missing ${lock_path}; generate and review the lock before environment setup." >&2
  exit 1
fi
if [[ ! -d "${artifact_root}" || ! -w "${artifact_root}" ]]; then
  echo "Artifact root is absent or not writable: ${artifact_root}" >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required." >&2
  exit 1
fi
if ! nvidia-smi >/dev/null; then
  echo "nvidia-smi preflight failed." >&2
  exit 1
fi

export UV_PROJECT_ENVIRONMENT="${environment_path}"
export UV_CACHE_DIR="${artifact_root}/cache/uv"
uv sync --project "${repo_root}/training" --locked --no-dev

export HF_HOME="${artifact_root}/cache/huggingface"
"${environment_path}/bin/python" "${repo_root}/scripts/training/check_training_environment.py" \
  --report "${artifact_root}/manifests/environment-report.json"
