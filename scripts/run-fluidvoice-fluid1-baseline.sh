#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "${script_dir}/.." && pwd)"

backend="gguf"
input_text=""
model_path=""
prompt_path=""
helper_path=""
max_tokens=512

usage() {
    cat <<'EOF'
Run a locally installed FluidVoice Fluid-1 cleanup baseline.

Usage:
  scripts/run-fluidvoice-fluid1-baseline.sh --text TEXT [options]

Options:
  --backend gguf|mlx   Runtime to use (default: gguf)
  --text TEXT          Raw dictation text to clean
  --model PATH         GGUF file or MLX model directory
  --prompt PATH        Fluid-1 system-prompt file
  --helper PATH        FluidVoice MLX helper executable
  --max-tokens N       Completion limit (default: 512)
  -h, --help           Show this help

The FluidIntelligence model card restricts these artifacts to personal,
non-commercial use. Do not commit, redistribute, bundle, or fine-tune them.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend)
            backend="${2:?missing value for --backend}"
            shift 2
            ;;
        --text)
            input_text="${2:?missing value for --text}"
            shift 2
            ;;
        --model)
            model_path="${2:?missing value for --model}"
            shift 2
            ;;
        --prompt)
            prompt_path="${2:?missing value for --prompt}"
            shift 2
            ;;
        --helper)
            helper_path="${2:?missing value for --helper}"
            shift 2
            ;;
        --max-tokens)
            max_tokens="${2:?missing value for --max-tokens}"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$input_text" ]]; then
    echo "--text is required" >&2
    exit 2
fi

if [[ ! "$max_tokens" =~ ^[1-9][0-9]*$ ]]; then
    echo "--max-tokens must be a positive integer" >&2
    exit 2
fi

cached_prompt="${project_dir}/.cache/fluidvoice-reverse/v1.6.9/prompt/fluid1_dictation_default.md"
installed_prompt="/Applications/FluidVoice.app/Contents/Resources/FluidIntelligence_FluidIntelligenceCore.bundle/Contents/Resources/Prompts/fluid1_dictation_default.md"
if [[ -z "$prompt_path" ]]; then
    if [[ -f "$cached_prompt" ]]; then
        prompt_path="$cached_prompt"
    else
        prompt_path="$installed_prompt"
    fi
fi

if [[ ! -f "$prompt_path" ]]; then
    echo "Fluid-1 prompt not found: $prompt_path" >&2
    exit 1
fi

case "$backend" in
    gguf)
        if [[ -z "$model_path" ]]; then
            model_path="${project_dir}/.cache/fluidvoice-reverse/weights/fluid-1-v1.6.0-q4_k_m.gguf"
        fi
        if [[ ! -f "$model_path" ]]; then
            echo "Fluid-1 GGUF not found: $model_path" >&2
            exit 1
        fi
        if ! command -v llama-completion >/dev/null 2>&1; then
            echo "llama-completion is required for the GGUF backend" >&2
            exit 1
        fi

        raw_output="$(mktemp "${TMPDIR:-/tmp}/fluid1-output.XXXXXX")"
        trap 'rm -f "$raw_output"' EXIT
        if ! llama-completion \
            --model "$model_path" \
            --system-prompt-file "$prompt_path" \
            --prompt "$input_text" \
            --predict "$max_tokens" \
            --ctx-size 8192 \
            --temp 0 \
            --top-k 1 \
            --top-p 1 \
            --min-p 0 \
            --seed 1 \
            --flash-attn on \
            --no-warmup \
            --jinja \
            --conversation \
            --single-turn \
            --simple-io \
            --no-perf >"$raw_output" 2>&1; then
            echo "Fluid-1 GGUF inference failed" >&2
            exit 1
        fi

        awk '
            $0 == "model" { in_completion = 1; next }
            in_completion {
                if ($0 ~ / \[end of text\]$/) {
                    sub(/ \[end of text\]$/, "")
                    print
                    found_end = 1
                    exit
                }
                print
            }
            END {
                if (!in_completion || !found_end) {
                    exit 1
                }
            }
        ' "$raw_output" || {
            echo "Fluid-1 GGUF output could not be parsed" >&2
            exit 1
        }
        ;;
    mlx)
        if [[ -z "$model_path" ]]; then
            cached_model="${project_dir}/.cache/fluidvoice-reverse/weights/fluid-1-nvfp4-mlx"
            installed_model="${HOME:?}/Library/Application Support/FluidIntelligence/Models/fluid-1-nvfp4-mlx"
            if [[ -d "$cached_model" ]]; then
                model_path="$cached_model"
            else
                model_path="$installed_model"
            fi
        fi
        if [[ ! -d "$model_path" || ! -f "$model_path/model.safetensors" ]]; then
            echo "Complete Fluid-1 MLX model not found: $model_path" >&2
            exit 1
        fi

        if [[ -z "$helper_path" ]]; then
            cached_helper="${project_dir}/.cache/fluidvoice-reverse/v1.6.9/runtime/fluid-intelligence-mlx"
            installed_helper="/Applications/FluidVoice.app/Contents/Helpers/fluid-intelligence-mlx"
            if [[ -x "$cached_helper" ]]; then
                helper_path="$cached_helper"
            else
                helper_path="$installed_helper"
            fi
        fi
        if [[ ! -x "$helper_path" ]]; then
            echo "FluidVoice MLX helper not found or not executable: $helper_path" >&2
            exit 1
        fi

        helper_args=(
            run
            --model-id fluid-1-nvfp4-mlx
            --model-dir "$model_path"
            --local-only
            --system-prompt-file "$prompt_path"
            --text "$input_text"
            --max-tokens "$max_tokens"
        )
        mtp_dir="${model_path}/gemma-4-E2B-it-qat-assistant-bf16-mlx-mtp"
        if [[ -f "${mtp_dir}/model.safetensors" ]]; then
            helper_args+=(--mtp-drafter-dir "$mtp_dir" --draft-block-size 6)
        fi
        exec "$helper_path" "${helper_args[@]}"
        ;;
    *)
        echo "Unsupported backend: $backend (expected gguf or mlx)" >&2
        exit 2
        ;;
esac
