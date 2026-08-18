# Sotto LFM2.5-350M correction-repair experiment

Status: campaign complete; clean-base epoch 1 selected for research, no checkpoint qualified for
deployment. See `docs/evaluation/results/2026-08-18-sotto-lfm-ab-comparison.json`.

## Objective

Improve the public Sotto LFM2.5-350M checkpoint on the failures that matter for ordinary on-device
conversation: applying explicit self-corrections, removing direct repetitions, and preserving
whether an utterance is a statement or a question. Keep its strong filler/punctuation cleanup and
its measured behavior of transcribing dictated questions and commands rather than answering them.

The public checkpoint's immutable strict score remains 42/69 for historical comparison. After
user review of every non-exact output, 59/69 are acceptable for the intended everyday use. The ten
relevant failures are:

- seven retained superseded corrections: `cleanup-003`, `cleanup-004`, `cleanup-021`,
  `heldout-006`, `heldout-007`, `heldout-038`, and `heldout-039`;
- two retained direct repetitions: `heldout-004` and `heldout-037`; and
- one statement changed into a question: `cleanup-007`.

Do not train on these cases or their expected outputs. They are retired evaluation-only
diagnostics. Use them only after training as allowed regression evidence.

The original 69-case user review remains historical calibration, but it is no longer the complete
product-facing regression definition. Technical/code-literal transformations remain outside the
ordinary-conversation workload. Word-to-digit/time normalization, inferred list/paragraph
formatting, disposable discourse lead-ins, journal false starts, and longer ordinary messages are
now represented explicitly in personal-conversation v3 below. Keep reporting the immutable 69-case
metrics while also evaluating every checkpoint on the new fixed personal suite.

## Personal-v3 checkpoint evaluation

The active direct-text checkpoint corpus is
`docs/evaluation/cleanup_personal_conversation_v3.jsonl`. It contains 20 ordinary personal cases
and is scorer-compatible without audio or Parakeet. It removes the unwanted phone-number example
and includes four long-form utterances of three to five sentences for cleanup quality and latency:

- `personal-v3-015`: four-sentence journal entry;
- `personal-v3-018`: three-sentence movie message with intentional repetition;
- `personal-v3-019`: five-sentence journal entry with an explicit paragraph break; and
- `personal-v3-020`: four-sentence planning note with names, uncertainty, and a time correction.

Run the public starting checkpoint and every saved Experiment A/B epoch against this exact file
with the native prompt and fixed greedy decoder. This is evaluation-only regression material: do
not put its raw text, expected output, anchors, errors, or phrasings into the training mixture,
prompt demonstrations, retrieval, preference data, or repair generation. Do not edit v3 after a
checkpoint result is recorded; create v4 for later product changes.

The evaluator now accepts any single-file BF16 Sotto checkpoint only when its exact
`model.safetensors` SHA-256 is supplied. Example:

```bash
checkpoint_dir=/data/rise/android_stt/runs/REPLACE_RUN/checkpoint-REPLACE_STEP
checkpoint_sha="$(sha256sum "${checkpoint_dir:?}/model.safetensors" | awk '{print $1}')"

python3 scripts/training/infer_sotto_lfm.py \
  --model-dir "$checkpoint_dir" \
  --model-id local/sotto-lfm-correction-repair \
  --model-revision experiment-a-epoch-1 \
  --expected-model-sha256 "$checkpoint_sha" \
  --cases docs/evaluation/cleanup_personal_conversation_v3.jsonl \
  --output /data/rise/android_stt/evaluations/experiment-a-epoch-1-personal-v3.jsonl

python3 scripts/score-cleanup-results.py \
  --cases docs/evaluation/cleanup_personal_conversation_v3.jsonl \
  experiment-a-epoch-1=/data/rise/android_stt/evaluations/experiment-a-epoch-1-personal-v3.jsonl
```

Use a unique output/provenance pair for every checkpoint; the runner refuses overwrite. Record the
case-file hash, checkpoint hash, repository commit, environment, raw model output, guardrail
decision, strict/category scores, TTFT, and total latency. Report the four `long_form` cases
individually as well as overall median/p90/max. Manually review every non-exact raw output and every
self-correction, uncertainty, negation, name, number, and formatting case. Guardrail-selected text
remains parallel evidence and cannot change raw semantic-safety status.

## Reproducibility boundary

The publisher's main SFT stage is reproducible in design, not bit-for-bit. The clearest disclosed
recipe is full-parameter SFT of `LiquidAI/LFM2.5-350M-Base` for three epochs at learning rate
`3e-5`, microbatch 1, gradient accumulation 8, cosine decay, 50 warmup steps, AdamW beta2 0.95,
weight decay 0.01, BF16+TF32, packed 4,096-token sequences, and a generated-and-recorded run seed.
Use the publisher-native
`### Input:\n...\n\n### Output:\n` format.

The final public model cannot be reproduced exactly: its evolving SFT data do not match the
project's pinned Sotto snapshot, and the complete GRPO rewards/data, intermediate v51/v55
checkpoints, refinement chain, exact environment, and model-soup inputs are not all public. Do not
claim an exact reproduction and do not add an improvised GRPO stage to this experiment.

## Data mixture

Use every eligible source row exactly once per epoch. Globally shuffle the combined stream with a
generated-and-recorded preparation seed; bit-for-bit replay is optional. Do not replay smaller
sources to enforce artificial proportions. The prepared natural composition is:

| Source | Rows | Share | Role |
|---|---:|---:|---|
| Pinned Sotto train | 135,501 | 90.38% | broad cleanup, no-op replay, punctuation, fillers, corrections |
| Pinned Disfl-QA train | 7,181 | 4.79% | human-authored contextual corrections and restarts |
| DISCO English train | 2,782 | 1.86% | human-annotated corrections, repetitions, false starts, fillers |
| Pinned Nyra/DisfluencySpeech train | 4,458 | 2.97% | speech-backed repetitions and conversational disfluency |

This choice is supported by the earlier Qwen comparison. Its natural combined data were about
92.1% Sotto, 4.9% Disfl-QA, and 3.0% Nyra. At epoch 2 the combined checkpoint scored 769/1,000 on
Disfl-QA and 147/250 on Nyra, essentially matching the one-epoch source-specific adapters at
765/1,000 and 150/250. The untouched Qwen base was not measured on these publisher splits, so do
not invent a base row or overstate transfer of this trend to LFM.

Use DISCO directly from the pinned official repository workbook and record its immutable revision
and payload hashes. Map only the authoritative English worksheet and keep the project-defined test
partition isolated. Per explicit user direction, licensing review is not a campaign gate.

Use only the already approved source-training surfaces. Keep Sotto validation, Disfl-QA dev/test,
Nyra validation/test, project dev, blind-v2, and both committed diagnostic corpora out of training.
Run the existing exact/fuzzy frozen-overlap and source-identity checks. Record sampling counts and
hash the ordered training stream so the same mixture can be replayed.

## Experiment A: repair the public checkpoint

This is the first and cheapest test.

1. Pin the public starting checkpoint at
   `juanquivilla/sotto-cleanup-lfm25-350m@6df6f019170b8b55333c047b901886a51750a965` and verify the
   existing weight SHA-256
   `6e96eeffdcdd60f881e13eb2019b339b39d1a74951446f062e7e641a82f6422e`.
2. Full-parameter SFT the balanced mixture for two epochs at learning rate `2e-6`, saving complete
   resumable checkpoints at the end of each epoch. This matches the disclosed learning rate and
   duration of the publisher's late refinement stage without claiming to recreate that stage.
3. Hold the disclosed settings fixed where applicable: microbatch 1, accumulation 8, cosine,
   50-step warmup, AdamW beta2 0.95, weight decay 0.01, BF16+TF32, packed 4,096 context, a recorded
   runtime seed,
   and the native prompt format.
4. Evaluate the starting checkpoint and both new epochs through one fixed sequential Transformers
   backend and decoder on project dev, the retired 69 diagnostics, and personal v3 before selecting
   an epoch. Do not compare these counts with the earlier Qwen vLLM profile.

## Experiment B: clean base-model replication

Run this only after Experiment A is fully evaluated and preserved.

1. Pin an immutable revision of `LiquidAI/LFM2.5-350M-Base` and record all model/tokenizer hashes.
2. Train the identical ordered mixture from the base for three epochs using the disclosed SFT
   recipe: full parameters, `3e-5`, microbatch 1, accumulation 8, cosine, 50 warmup steps, AdamW
   beta2 0.95, weight decay 0.01, BF16+TF32, packed 4,096 context, and a recorded runtime seed.
3. Save and evaluate every epoch. Treat this as a project reproduction of the public SFT design,
   not the unpublished GRPO/refinement/soup lineage.

## Preflight and monitoring

Before either full run:

1. Extend the training code/config/tests for LFM full-parameter SFT and native prompt masking.
2. Audit every formatted row and prove no truncation under the packed 4,096-token policy.
3. Run a 32-row overfit, a two-step longest-row memory smoke, checkpoint resume, and direct
   inference from the saved checkpoint.
4. Record exact optimizer-step expectations from the prepared sampled stream.
5. Record the current commit, dirty paths, and hashes of the exact trainer/config/data/mixture
   inputs. A dirty or unpushed repository is allowed and is not a launch gate.
6. Use an immutable run directory, persistent supervisor, telemetry, resumable checkpoints,
   terminal status, and the repository's normal failure-reporting rules.

## Selection

Evaluate raw model output before guardrails. The primary comparison is the ten user-relevant
retired failures, personal v3, and a separately built non-evaluation correction/repetition dev set.
Report strict exact and all legacy safety metrics for continuity, but rank checkpoints by:

1. fewer retained superseded corrections;
2. fewer retained direct repetitions;
3. zero new statement/question intent changes or answered dictated content;
4. no regression on the other user-accepted everyday outputs; and
5. latency only after quality.

Do not use blind-v2 for data, hyperparameter, prompt, epoch, or checkpoint selection. Do not merge,
quantize, or integrate into Android until one frozen raw checkpoint is selected and the applicable
quality review passes. A later blind evaluation still controls any generalization claim.
