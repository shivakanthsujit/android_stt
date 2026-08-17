#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
config_path=${repo_root}/training/config/vllm-serving-v1.json
project_path=${repo_root}/training/vllm
lock_path=${project_path}/uv.lock
source_path=/home/shiva/vllm
expected_revision=ba41cc90e8ef7f236347b2f1599eec2cbb9e1f0d
artifact_root=/data/rise/android_stt/vllm
environment_path=${artifact_root}/env

if [[ ! -f "${config_path}" || ! -f "${lock_path}" ]]; then
  echo "Missing serving config or locked vLLM environment definition." >&2
  exit 1
fi
if [[ ! -d "${source_path}/.git" ]]; then
  echo "Missing vLLM clone at ${source_path}." >&2
  exit 1
fi
actual_revision=$(git -C "${source_path}" rev-parse HEAD)
if [[ "${actual_revision}" != "${expected_revision}" ]]; then
  echo "vLLM revision mismatch: ${actual_revision}; expected ${expected_revision}." >&2
  exit 1
fi
if [[ -n "$(git -C "${source_path}" status --short)" ]]; then
  echo "Refusing to install from a dirty vLLM source tree." >&2
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

mkdir -p "${artifact_root}/cache/uv" "${artifact_root}/cache/huggingface" \
  "${artifact_root}/manifests" "${artifact_root}/python"
export UV_CACHE_DIR=${artifact_root}/cache/uv
export UV_PYTHON_INSTALL_DIR=${artifact_root}/python
export UV_LINK_MODE=copy
export UV_PROJECT_ENVIRONMENT=${environment_path}

if [[ ! -x "${environment_path}/bin/python" ]]; then
  uv venv --python 3.10 --seed --managed-python "${environment_path}"
fi

# v0.8.5 is the last reviewed release matching the host's verified
# Torch 2.6/CUDA 12.4 stack. uv.lock fixes every transitive package and the
# PyTorch CUDA index; the source checkout independently pins the implementation.
uv sync --project "${project_path}" --locked --no-dev

export HF_HOME=${artifact_root}/cache/huggingface
export HF_HUB_CACHE=${artifact_root}/cache/huggingface/hub
"${environment_path}/bin/python" \
  "${repo_root}/scripts/training/check_vllm_environment.py" \
  --config "${config_path}" \
  --report "${artifact_root}/manifests/environment-report.json"
