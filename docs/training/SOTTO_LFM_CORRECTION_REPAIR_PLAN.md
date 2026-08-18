# Sotto LFM2.5-350M correction-repair experiment

Status: approved next experiment; implementation and runs not started

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

The user explicitly does not treat the other 17 strict mismatches as blockers for this use case.
They cover disposable conversational lead-ins, punctuation and contractions, word-to-digit time
normalization, inferred list formatting, redundant-but-correct final-version wording, currency or
non-Latin-name normalization, and technical/code-literal transformations that do not occur in the
target ordinary-conversation workload. Keep reporting the strict metrics, but do not optimize this
experiment to those dismissed cases.

## Reproducibility boundary

The publisher's main SFT stage is reproducible in design, not bit-for-bit. The clearest disclosed
recipe is full-parameter SFT of `LiquidAI/LFM2.5-350M-Base` for three epochs at learning rate
`3e-5`, microbatch 1, gradient accumulation 8, cosine decay, 50 warmup steps, AdamW beta2 0.95,
weight decay 0.01, BF16+TF32, packed 4,096-token sequences, and seed 42. Use the publisher-native
`### Input:\n...\n\n### Output:\n` format.

The final public model cannot be reproduced exactly: its evolving SFT data do not match the
project's pinned Sotto snapshot, and the complete GRPO rewards/data, intermediate v51/v55
checkpoints, refinement chain, exact environment, and model-soup inputs are not all public. Do not
claim an exact reproduction and do not add an improvised GRPO stage to this experiment.

## Data mixture

Build a deterministic source-balanced sampler rather than concatenating source rows. Start with
these example-level sampling proportions:

| Source | Share | Role |
|---|---:|---|
| Pinned Sotto train | 55% | broad cleanup, no-op replay, punctuation, fillers, corrections |
| Pinned Disfl-QA train | 25% | human-authored contextual corrections and restarts |
| DISCO English train | 10% | human-annotated corrections, repetitions, false starts, fillers |
| Pinned Nyra/DisfluencySpeech train | 10% | speech-backed repetitions and conversational disfluency |

Before using DISCO, locate its authoritative released dataset, record an immutable revision and
payload hashes, verify its CC BY 4.0 lineage/attribution, map only the English pairs, and keep its
native holdout isolated. If that cannot be established, stop or redistribute its 10% share across
the other approved sources explicitly; do not use an unverified mirror.

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
   50-step warmup, AdamW beta2 0.95, weight decay 0.01, BF16+TF32, packed 4,096 context, seed 42,
   and the native prompt format.
4. Evaluate the starting checkpoint and both new epochs through one fixed sequential Transformers
   backend and decoder before selecting an epoch. Do not compare these counts with the earlier
   Qwen vLLM profile.

## Experiment B: clean base-model replication

Run this only after Experiment A is fully evaluated and preserved.

1. Pin an immutable revision of `LiquidAI/LFM2.5-350M-Base` and record all model/tokenizer hashes.
2. Train the identical ordered mixture from the base for three epochs using the disclosed SFT
   recipe: full parameters, `3e-5`, microbatch 1, accumulation 8, cosine, 50 warmup steps, AdamW
   beta2 0.95, weight decay 0.01, BF16+TF32, packed 4,096 context, and seed 42.
3. Save and evaluate every epoch. Treat this as a project reproduction of the public SFT design,
   not the unpublished GRPO/refinement/soup lineage.

## Preflight and monitoring

Before either full run:

1. Extend the training code/config/tests for LFM full-parameter SFT and native prompt masking.
2. Audit every formatted row and prove no truncation under the packed 4,096-token policy.
3. Run a 32-row overfit, a two-step longest-row memory smoke, checkpoint resume, and direct
   inference from the saved checkpoint.
4. Record exact optimizer-step expectations from the deterministic sampled stream.
5. Commit and push code/config/manifests before launch.
6. Use an immutable run directory, persistent supervisor, telemetry, resumable checkpoints,
   terminal status, and the repository's normal failure-reporting rules.

## Selection

Evaluate raw model output before guardrails. The primary comparison is the ten user-relevant
retired failures plus a separately built non-evaluation correction/repetition dev set. Report
strict exact and all legacy safety metrics for continuity, but rank checkpoints by:

1. fewer retained superseded corrections;
2. fewer retained direct repetitions;
3. zero new statement/question intent changes or answered dictated content;
4. no regression on the other user-accepted everyday outputs; and
5. latency only after quality.

Do not use blind-v2 for data, hyperparameter, prompt, epoch, or checkpoint selection. Do not merge,
quantize, or integrate into Android until one frozen raw checkpoint is selected and the applicable
quality review passes. A later blind evaluation still controls any generalization claim.
