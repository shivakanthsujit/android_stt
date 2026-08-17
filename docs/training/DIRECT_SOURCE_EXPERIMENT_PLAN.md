# Direct-source cleanup experiments

Status: implemented; full Sotto run active and monitored

This is the new-session handoff for the fast experimental track. The purpose is to train real
models quickly, evaluate their raw behavior, and use evidence to improve the data and recipe. It
does not replace the stricter reviewed-corpus path required before a model can become a deployment
candidate.

## Decision

Train four adapters using the public datasets directly:

1. Sotto only.
2. Disfl-QA only.
3. Nyra Disfluency Speech English only.
4. Sotto + Disfl-QA + Nyra combined.

Use the same base model, prompt, optimizer, decoding, and evaluation harness for all four. The only
intended difference is the training dataset. Start with Sotto and get it through raw-output
evaluation before spending time on the other three.

“Direct” means using the publisher's paired text fields as the training pair. Do not apply the
project's category balancing, quarantine policy, supplemental generation, target rewriting, or
row-level human approval to these exploratory adapters. We still verify immutable source hashes,
required columns, nonempty pairs, split identity, and absence of the project's frozen evaluation
cases. These are exploratory models, not automatically safe or deployable models.

## Exact datasets

All source payloads are already pinned and verified under
`/data/rise/android_stt/raw/sources-v1/`. Their manifest is
`/data/rise/android_stt/manifests/source-manifest-v1.json`.

| Experiment | Training pairs | In-training validation | Direct field mapping |
|---|---:|---:|---|
| Sotto | 135,503 | 6,921 | `input` → raw transcript; `output` → target |
| Disfl-QA | 7,181 usable (7,182 publisher rows; one empty pair) | 1,000 | `disfluent` → raw transcript; `original` → target |
| Nyra | 4,458 | 250 | `verbatim_transcript` → raw transcript; `intended_transcript` → target |
| Combined | 147,142 usable | 8,171 | Concatenate the three publisher train splits; concatenate their validation splits |

Do not train on Disfl-QA test (3,643 rows) or Nyra test (249 rows). Sotto's legacy JSONL overlaps
its canonical Parquet and must not be added a second time. Nyra audio is not loaded; only its two
published transcript columns are used. Direct-source extraction should retain the source text as
stored rather than silently repairing or relabeling targets.

## First base model

Use **Qwen3-0.6B** for all four first-pass adapters:

- model: `Qwen/Qwen3-0.6B`
- pinned revision: `61641f84fa567ab7b58e216b4930d2fe28bfd045`
- mode: text-only, non-thinking chat template
- method: BF16 base with LoRA adapters

Why this base first:

- It is small enough to produce results quickly and remains plausible for later mobile export.
- The repository already has its pinned revision, tokenizer/template path, LoRA module list, and
  generic zero-shot baseline.
- Its standard causal architecture is a lower-risk first training target than the Qwen3.5 hybrid
  architecture.
- Holding the base fixed makes the four experiments a useful dataset comparison.

Do not mix Qwen, Gemma, and LFM bases in the initial four-way data experiment. After the source
comparison, train the best-performing data recipe on one stronger alternative—Qwen3.5-0.8B or
Gemma 3 1B—if Qwen3-0.6B appears capacity-limited. Liquid LFM is not the first training base:
the repository currently has an Android inference integration for LFM, while the pinned,
reproducible training path is already built around Qwen, and the evaluated generic LFM checkpoints
were cleanup no-go results.

## Initial training recipe

Use this recipe unchanged across the four adapters unless a run fails mechanically:

| Setting | Value |
|---|---:|
| Epochs | 1 |
| Seed / data seed | 23 / 23 |
| Maximum formatted sequence | 2,112 tokens, no silent truncation |
| Microbatch | 4 |
| Gradient accumulation | 8 |
| Effective batch | 32 |
| Precision | BF16; TF32 enabled |
| Optimizer | fused AdamW |
| Learning rate | 2e-4 |
| Weight decay | 0.01 |
| Schedule | cosine with 3% warmup |
| Gradient clipping | 1.0 |
| LoRA | rank 16, alpha 32, dropout 0.05, no bias |
| LoRA targets | Qwen attention and MLP projection modules already pinned in `pilot-training-v1.json` |
| Loss | assistant target tokens only |
| Packing | disabled |

Expected optimizer steps are 4,235 for Sotto, 225 for Disfl-QA, 140 for Nyra, and
4,599 for the combined run. Derive evaluation/checkpoint intervals from each run length so each
run records roughly four intermediate checkpoints plus the final adapter. Log training metrics at
least every ten optimizer steps.

One epoch is intentional: it gets a complete comparable result quickly. If Sotto is promising and
still improving, extend the recipe in a new, explicitly named 3-epoch experiment rather than
quietly changing the four-way comparison.

### Sotto publisher-recipe reference

Sotto does not publish a formal paper recipe. Its evolving official model card describes an
LFM2.5-350M full-fine-tuning lineage, not this Qwen LoRA experiment. The clearest v23 SFT settings
are three epochs, learning rate 3e-5, microbatch 1 / accumulation 8, AdamW beta2 0.95, weight decay
0.01, cosine decay with 50 warmup steps, packed 4,096-token context, BF16+TF32, and seed 42. Later
production releases add GRPO, targeted data, and checkpoint averaging. See
`docs/research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md` for immutable primary-source links,
the full comparison, and source caveats.

These settings are a follow-up basis, not a reason to mutate the active run. Its Qwen base, LoRA
adaptation, effective batch 32, one epoch, and 2e-4 adapter learning rate are intentionally held
fixed for the first dataset comparison. If this run learns useful behavior but remains
undertrained or adapter-limited, evaluate separately named three-epoch and/or full-tuning studies.

Before Sotto, run only one bounded mechanical smoke: the 32 longest formatted train/validation
examples and two optimizer steps. Its job
is to catch tokenizer/template, CUDA, LoRA-target, or memory failures. Do not run the old long
overfit/resume-smoke sequence before this exploratory launch. If 1,024 tokens does not cover every
source pair, report the count and maximum before deciding whether to raise the limit; never
silently truncate or drop rows while calling the run “full dataset.”

## Prompt and target format

Use the fixed instruction in `training/config/cleanup-instruction-v2.txt`. Model input is:

- system: the fixed cleanup instruction;
- user: `Transcript:\n` followed by the direct source input; and
- assistant target: the direct source target.

Metadata and source names are not exposed to the model. Qwen thinking output is disabled through
the official chat-template option. Training loss applies only to the assistant target tokens.

## Evaluation plan

Publisher validation loss is useful for detecting optimization problems, but it is not the
product-quality decision. Evaluate every final adapter in this order:

1. **Publisher validation generation:** generate direct outputs for that source's validation split
   and report exact match, empty/capped outputs, and source-specific failure examples outside Git.
2. **Retired project diagnostics:** run raw inference on the frozen 24-case and 45-case corpora
   (69 total). These are evaluation-only and must never enter training, prompts, or retrieval.
3. **Automated project metrics:** raw exact match, preservation-anchor recall, removal of
   superseded content, explicit-correction success, clean/no-op exactness, must-not-answer
   exactness, per-category exactness, empty output, cap hits, and guardrail fallback rate.
4. **Semantic review:** manually inspect every non-exact output and every correction,
   protected-literal, negation/uncertainty, and must-not-answer case. Report meaning changes,
   invented facts, retained superseded text, and answered/obeyed dictation separately.
5. **Host latency:** record TTFT, total generation latency, tokens/second, output tokens, peak GPU
   memory, and model/adapter size on the A6000.

Raw model output decides whether an experiment is promising. Guardrail-selected text is a
separate defense-in-depth metric and cannot convert an unsafe raw model into a pass. The retired
69 cases support iteration but are not blind evidence. Do not create or open blind-v2 for these
first source-comparison runs; author and seal it only after the data/base/recipe stabilizes.

The four-way comparison report should contain one row per adapter with dataset, row count, wall
time, final train/validation loss, raw 69-case exact score, correction score, anchor recall,
semantic failures, median/p95 TTFT and total latency, peak VRAM, and adapter bytes.

## Run and monitoring contract

Each run lives under a unique directory such as:

`/data/rise/android_stt/runs/direct-sotto-qwen3-0.6b-e1-seed23-<timestamp>`

Each directory must contain resolved configuration, repository commit and dirty-state report,
source/model hashes, console log, structured metrics, GPU telemetry, checkpoints, final adapter,
and terminal status. Keep all datasets, model caches, checkpoints, results containing source text,
and weights outside Git.

Launch the run in a managed session and monitor every three minutes with
`monitor_cleanup_run.py`. Attach it only after the trainer has written its initial `status.json`,
so the monitor cannot race the new-run directory audit. Track process/session identity, latest step, train/eval loss, learning
rate, gradient norm, throughput, newest checkpoint, GPU utilization/memory/temperature/power,
disk space, and terminal status. Monitoring is read-only. Do not silently restart, change batch
size, or alter hyperparameters. Stop and diagnose NaNs, repeated OOMs, missing checkpoints, disk
pressure, or a stalled process; ask before changing the recipe.

Success for the first run means the Sotto adapter and trainer state exist, the process exits zero,
raw publisher/project evaluations complete, and a text-free comparison report is written. It does
not mean the model is deployment-safe.

## Current execution state

The authorized full Sotto run completed successfully at
`/data/rise/android_stt/runs/direct-sotto-qwen3-0.6b-e1-seed23-20260817T124158Z`. It used all
135,503 pinned train rows without truncation, reached 4,235/4,235 steps, and exited zero. Final
train loss is 0.09389 and final validation loss is 0.07938. Resumable checkpoints are
`checkpoint-1059`, `checkpoint-2118`, `checkpoint-3177`, and `checkpoint-4235`; the terminal
adapter is `final-adapter/` and matches checkpoint 4,235 exactly.

Retired diagnostics and cross-dataset evaluations are complete. Raw semantic safety failed on
eight substantive cases, and Sotto-to-Disfl-QA/Nyra transfer was not sufficient to skip either
standalone training run. Full generation over the 6,921-row Sotto publisher validation split is
still active under `evaluation/publisher-validation-results.jsonl`. Sanitized interim evidence and
artifact hashes are in
`docs/evaluation/results/2026-08-18-direct-sotto-qwen3-interim-evaluation.json`.

## What the next session should do

1. Read `AGENTS.md`, `TRAINING_MACHINE_HANDOFF.md`, and this file completely.
2. Preserve the completed Sotto run and do not disturb its active publisher evaluator.
3. Monitor publisher generation to 6,921/6,921, verify exit status and hashes, then score it.
4. Launch the standalone Disfl-QA and Nyra source adapters with the identical recipe; cross-transfer
   evidence does not justify skipping them.
5. Compare the three source adapters before deciding whether to pay for the combined run or instead
   test three epochs/full fine-tuning on the best source recipe.

The stricter reviewed 5,000/500 pilot remains available later for safety-focused iteration. It is
not the immediate next action for this exploratory track.
