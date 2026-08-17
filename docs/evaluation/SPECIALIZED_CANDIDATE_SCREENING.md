# Specialized cleanup candidate screening

Use this runbook for a downloaded task-specific GGUF before doing any Android runtime work. The
orchestrator starts a local `llama-server`, runs the frozen seed and held-out-v1 corpora, scores both,
records exact commands and hashes, and then stops only the server process it started. It never
downloads a model.

## VoiceInk Qwen3.5-2B probe

The current public lead is `hourliert/voiceink-qwen3.5-2b`. The published artifact is a
1,274,396,352-byte Q4_K_M GGUF with SHA-256
`343721d889adcec76725373f51be207e6a980eec8411e4e6c553dd6c8329d175`. Verify a separately
downloaded file before running it:

```bash
shasum -a 256 /absolute/path/to/voiceink-qwen3.5-2b.gguf
```

The fine-tune repository and artifact do not declare a license. Internal evaluation is reasonable;
do not redistribute or bundle the weights unless the author clarifies the license.

Run the qualification screen from the repository root:

```bash
python3 scripts/screen-cleanup-candidate.py \
  --model-path /absolute/path/to/voiceink-qwen3.5-2b.gguf \
  --model-name voiceink-qwen3.5-2b \
  --quantization Q4_K_M \
  --run-name YYYY-MM-DD-voiceink-qwen35-2b-q4km-native \
  --prompt-variant voiceink_task_tuned \
  --request-extra docs/evaluation/request_extras/voiceink-qwen35-2b.json \
  --server-arg=--ctx-size \
  --server-arg=16384 \
  --server-arg=--gpu-layers \
  --server-arg=all \
  --server-arg=--flash-attn \
  --server-arg=on \
  --server-arg=--jinja \
  --server-arg=--reasoning \
  --server-arg=off
```

`voiceink_task_tuned` sends the author's exact training system prompt and wraps each raw transcript
as `<TRANSCRIPT>...</TRANSCRIPT>`. The prompt is pinned from repository commit
`95bbf17b228b7ee03aec02d82de2f03a30ae3694`; the checked-in text is stripped in the same way as the
training script. Do not append `/no_think`: Qwen3.5 does not officially support the older Qwen3 soft
switch. The server disables reasoning explicitly, while the request extra stops the rare leaked
`</think>` reported by the fine-tune author.

The fixed comparison settings remain temperature 0.1, seed 23, streaming, and the input-derived
16–96 output-token cap. Runtime extras cannot override those fields.

## Outputs and review gate

The default output directory is `build/evaluation-results/`. A run produces:

- seed and heldout-v1 result JSONL, including raw model text and guarded selected text;
- a JSON score report for each corpus;
- the complete `llama-server` log;
- one provenance JSON containing the model size/hash, corpus hashes, runtime version, host details,
  prompt file/hash, runner/scorer hashes, request-extra hash, exact commands, timestamps, and
  completion status.

Use a new `--run-name` for every artifact or settings change. `--overwrite` is available only for an
intentional replacement.

Automated exact-match and preservation scores are only the first gate. Before a candidate advances,
manually inspect every non-exact output and all `must_not_answer`, `adversarial`, and
`self_correction` cases. The required gate remains zero meaning changes, zero answered/followed
instructions, strong explicit corrections, and no changed names, numbers, negation, uncertainty, or
technical identifiers. Guardrail fallback is safety behavior, not a successful cleanup.

Do not tune against `cleanup_cases_heldout_v1.jsonl`; it has already informed guardrail work. If this
candidate leads to prompt, adapter, or training changes, make the final go/no-go claim on a new blind,
versioned corpus.
