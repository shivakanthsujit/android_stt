#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hf_dir="${1:-$repo_dir/.cache/integration/models/sotto-hf}"
output_dir="${2:-$repo_dir/.cache/integration/models/sotto-gguf-mapped}"
export_repo="${3:-$repo_dir/.cache/integration/leap-finetune}"
converter="$export_repo/src/leap_finetune/quantization/gguf/convert_hf_to_gguf.py"
mapping_patch="$repo_dir/scripts/patches/leap-finetune-sotto-lfm25-tensor-mapping.patch"
f16_model="$output_dir/sotto-cleanup-lfm25-350m-f16.gguf"
q4_model="$output_dir/sotto-cleanup-lfm25-350m-q4_k_m.gguf"
expected_export_commit="ee010f850a6f9e810aebbbc8e5d072675fcaece7"
expected_llama_version="10450"

require_hash() {
    local expected="$1"
    local file="$2"
    if [[ ! -f "$file" ]]; then
        echo "Missing pinned Sotto source file: $file" >&2
        exit 1
    fi
    local actual
    actual="$(shasum -a 256 "$file" | awk '{print $1}')"
    if [[ "$actual" != "$expected" ]]; then
        echo "SHA-256 mismatch for $file: expected $expected, found $actual" >&2
        exit 1
    fi
}

if [[ ! -f "$converter" ]]; then
    echo "Missing leap-finetune export checkout at $export_repo" >&2
    echo "Clone https://github.com/Liquid4All/leap-finetune.git at $expected_export_commit." >&2
    exit 1
fi
actual_export_commit="$(git -C "$export_repo" rev-parse HEAD)"
if [[ "$actual_export_commit" != "$expected_export_commit" ]]; then
    echo "Unexpected leap-finetune commit: $actual_export_commit" >&2
    exit 1
fi
if git -C "$export_repo" apply --reverse --check "$mapping_patch" >/dev/null 2>&1; then
    echo "Sotto LFM2.5 tensor mapping patch is already applied."
elif git -C "$export_repo" apply --check "$mapping_patch" >/dev/null 2>&1; then
    git -C "$export_repo" apply "$mapping_patch"
    echo "Applied the project-pinned Sotto LFM2.5 tensor mapping patch."
else
    echo "Sotto tensor mapping patch does not apply cleanly to $actual_export_commit" >&2
    exit 1
fi

installed_llama_version="$(brew list --versions llama.cpp | awk '{print $2}')"
if [[ "$installed_llama_version" != "$expected_llama_version" ]]; then
    echo "Expected Homebrew llama.cpp $expected_llama_version, found $installed_llama_version" >&2
    exit 1
fi

require_hash \
    "6e96eeffdcdd60f881e13eb2019b339b39d1a74951446f062e7e641a82f6422e" \
    "$hf_dir/model.safetensors"
require_hash \
    "37b433e53d0f903cc274563a8a9c5f53c69eeafe60fcadac19ac272d6e0a5387" \
    "$hf_dir/config.json"
require_hash \
    "4905ab82b2cfc25e0c88adc8f4eeffe759c57c5626312b30b0aaeaf8ad3379bc" \
    "$hf_dir/tokenizer.json"
require_hash \
    "c0b2d752962d5b61909aba69cbd2b5bca826a31354e777d6d2e8d5e6b4678fa6" \
    "$hf_dir/tokenizer_config.json"
require_hash \
    "89e790f027916b5a2bca145a6a8454e06ffc7a5043bf3b6d97829aff86bb543f" \
    "$hf_dir/chat_template.jinja"
require_hash \
    "14f2335f0fd2010db80e256ef955b79c0ad2c03d243a98d48317346870f9fe00" \
    "$hf_dir/generation_config.json"

mkdir -p "$output_dir"
if [[ -e "$f16_model" || -e "$q4_model" ]]; then
    echo "Refusing to overwrite an existing Sotto GGUF in $output_dir" >&2
    exit 1
fi

uv run \
    --isolated \
    --no-project \
    --python 3.12 \
    --with 'numpy<2.5' \
    --with torch \
    --with 'transformers>=5.3,<5.4' \
    --with safetensors \
    python "$converter" \
    "$hf_dir" \
    --outfile "$f16_model" \
    --outtype f16

llama-quantize "$f16_model" "$q4_model" Q4_K_M

require_hash \
    "277dc6fd933b189f2d264ea13ba94c16993c48410271667e0e0b1510358dec78" \
    "$f16_model"
require_hash \
    "05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570" \
    "$q4_model"

echo "Created pinned Sotto integration artifacts:"
shasum -a 256 "$f16_model" "$q4_model"
