#!/usr/bin/env bash
set -euo pipefail

artifact_root=/data/rise/android_stt
environment_path=${artifact_root}/env

if [[ ! -x "${environment_path}/bin/python" ]]; then
  echo "Locked environment is missing; run scripts/training/setup_training_env.sh first." >&2
  exit 1
fi

export HF_HOME="${artifact_root}/cache/huggingface"
export HF_HUB_CACHE="${artifact_root}/cache/huggingface/hub"
export HF_DATASETS_CACHE="${artifact_root}/cache/huggingface/datasets"
export TRANSFORMERS_CACHE="${artifact_root}/cache/huggingface/transformers"
export TORCH_HOME="${artifact_root}/cache/torch"
export PYTHONUNBUFFERED=1

exec "${environment_path}/bin/python" "$@"
