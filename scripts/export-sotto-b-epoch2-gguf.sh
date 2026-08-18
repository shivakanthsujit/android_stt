#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
checkpoint_dir="${1:-$repo_dir/.cache/integration/models/sotto-b-epoch2-hf}"
tokenizer_dir="${2:-$repo_dir/.cache/integration/models/sotto-hf}"
output_dir="${3:-$repo_dir/.cache/integration/models/sotto-b-epoch2-gguf}"
export_repo="${4:-$repo_dir/.cache/integration/leap-finetune}"
converter="$export_repo/src/leap_finetune/quantization/gguf/convert_hf_to_gguf.py"
mapping_patch="$repo_dir/scripts/patches/leap-finetune-sotto-lfm25-tensor-mapping.patch"
export_input="$output_dir/hf-export-input"
f16_model="$output_dir/sotto-b-epoch2-lfm25-350m-f16.gguf"
q4_model="$output_dir/sotto-b-epoch2-lfm25-350m-q4_k_m.gguf"
expected_export_commit="ee010f850a6f9e810aebbbc8e5d072675fcaece7"
expected_llama_version="10450"

require_hash() {
    local expected="$1"
    local file="$2"
    if [[ ! -f "$file" ]]; then
        echo "Missing export input: $file" >&2
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
    echo "Missing leap-finetune exporter at $export_repo" >&2
    exit 1
fi
actual_export_commit="$(git -C "$export_repo" rev-parse HEAD)"
if [[ "$actual_export_commit" != "$expected_export_commit" ]]; then
    echo "Unexpected leap-finetune commit: $actual_export_commit" >&2
    exit 1
fi
if git -C "$export_repo" apply --reverse --check "$mapping_patch" >/dev/null 2>&1; then
    :
elif git -C "$export_repo" apply --check "$mapping_patch" >/dev/null 2>&1; then
    git -C "$export_repo" apply "$mapping_patch"
else
    echo "Sotto tensor mapping patch does not apply cleanly" >&2
    exit 1
fi

installed_llama_version="$(brew list --versions llama.cpp | awk '{print $2}')"
if [[ "$installed_llama_version" != "$expected_llama_version" ]]; then
    echo "Expected Homebrew llama.cpp $expected_llama_version, found $installed_llama_version" >&2
    exit 1
fi

require_hash "5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6" \
    "$checkpoint_dir/model.safetensors"
require_hash "38d4af02e45d38213cdf5f6d37ea0a0acff5e418c448657f2f44bf2e53b053be" \
    "$checkpoint_dir/config.json"
require_hash "4385af151613351f372f25416860a24c8179a9dda2cf6d29429fce2d5eda8a9a" \
    "$checkpoint_dir/generation_config.json"
require_hash "4905ab82b2cfc25e0c88adc8f4eeffe759c57c5626312b30b0aaeaf8ad3379bc" \
    "$tokenizer_dir/tokenizer.json"
require_hash "c0b2d752962d5b61909aba69cbd2b5bca826a31354e777d6d2e8d5e6b4678fa6" \
    "$tokenizer_dir/tokenizer_config.json"
require_hash "89e790f027916b5a2bca145a6a8454e06ffc7a5043bf3b6d97829aff86bb543f" \
    "$tokenizer_dir/chat_template.jinja"

if [[ -L "$output_dir" ]]; then
    echo "Refusing symlinked export directory: $output_dir" >&2
    exit 1
fi
if [[ -e "$f16_model" || -e "$q4_model" ]]; then
    echo "Refusing to overwrite an existing B epoch-2 GGUF in $output_dir" >&2
    exit 1
fi
mkdir -p "$export_input"
cp "$checkpoint_dir/model.safetensors" "$export_input/model.safetensors"
cp "$checkpoint_dir/config.json" "$export_input/config.json"
cp "$checkpoint_dir/generation_config.json" "$export_input/generation_config.json"
cp "$tokenizer_dir/tokenizer.json" "$export_input/tokenizer.json"
cp "$tokenizer_dir/tokenizer_config.json" "$export_input/tokenizer_config.json"
cp "$tokenizer_dir/chat_template.jinja" "$export_input/chat_template.jinja"

# Transformers 5.14 omits two redundant legacy aliases that the pinned 2026-era
# converter still reads. Add them only to the ignored export copy; the checkpoint
# config and its recorded hash remain unchanged.
if ! jq -e \
    '.intermediate_size == 6656 and .rope_parameters.rope_theta == 1000000.0' \
    "$export_input/config.json" >/dev/null; then
    echo "Checkpoint config does not match the reviewed LFM2.5 compatibility aliases" >&2
    exit 1
fi
jq '.block_ff_dim = .intermediate_size | .rope_theta = .rope_parameters.rope_theta' \
    "$export_input/config.json" > "$export_input/config.json.tmp"
mv "$export_input/config.json.tmp" "$export_input/config.json"

uv run \
    --isolated \
    --no-project \
    --python 3.12 \
    --with 'numpy<2.5' \
    --with torch \
    --with 'transformers>=5.3,<5.4' \
    --with safetensors \
    python "$converter" \
    "$export_input" \
    --outfile "$f16_model" \
    --outtype f16

llama-quantize "$f16_model" "$q4_model" Q4_K_M

require_hash "20843b2d838cc2b911c2f19d435af02869ca9e78e1cb5e7753b68bd7c9ccec43" \
    "$f16_model"
require_hash "02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0" \
    "$q4_model"

echo "Created experimental B epoch-2 artifacts:"
shasum -a 256 "$f16_model" "$q4_model"
