# Session log

## 2026-08-17 — Direct-source experiment handoff

- Changed the immediate training strategy from completing the balanced 5,000/500 human-reviewed
  pilot first to obtaining model evidence through four exploratory direct-source adapters: Sotto,
  Disfl-QA, Nyra, and all three combined.
- Chose Qwen3-0.6B as the fixed first base and a one-epoch BF16 LoRA recipe so dataset effects are
  comparable. Sotto is first; later bases remain an evidence-driven decision.
- Added `docs/training/DIRECT_SOURCE_EXPERIMENT_PLAN.md` with exact source splits/counts, field
  mappings, hyperparameters, minimal two-step smoke, managed monitoring contract, raw-output
  evaluation/latency plan, artifact policy, and new-session execution order.
- Verified that the pinned source snapshot and environment exist. No direct-source trainer, model
  download, adapter, checkpoint, or GPU training run was created in this session.

## 2026-08-17 — RTX A6000 Phase 0 and data-pipeline checkpoint

- Read the complete root agent rules, training-machine handoff, all handoff-required research,
  schema, evaluation, and prior-result documents, plus the long-run monitoring procedure.
- Verified a clean `main` at `2ae244c`, aligned with `origin/main` before changes.
- Recorded host `dante`: Ubuntu 22.04.5, Xeon Silver 4316 (20 cores exposed), 125 GiB RAM,
  PCI-visible RTX A6000, and loaded NVIDIA driver module 550.144.03.
- Found only about 11 GiB free on the 99%-used home/repository volume and about 9.6 TiB free on
  `/data`; the user created and verified writable `/data/rise/android_stt/` artifact directories.
- Recorded the user's direct host NVIDIA-SMI result: driver 550.144.03, CUDA compatibility 12.4,
  idle RTX A6000 with 49,140 MiB. Generated and reviewed a 77-package Python 3.10 lock using the
  PyTorch 2.6.0 CUDA 12.4 build; synchronized it under `/data/rise/android_stt/env` and passed exact
  package, CUDA, GPU-capacity, and BF16 matmul checks.
- Added immutable source and pilot configs, a fail-closed pinned fetcher, conservative public-data
  importer/quarantine pipeline, family/near-duplicate grouping before splits, and exact pilot
  bucket/cross-cutting quota checks.
- Added V2 explicit transcript-formatting, reviewed grammar/ASR repair, declared lexical-addition
  controls, source-native holdout enforcement, direct
  training/inference/scoring, Gate A source/license/review/frozen-overlap checks, and read-only
  three-minute managed-run monitoring.
- Full verification is 93/93 script tests and 10/10 deterministic-baseline tests, with an
  end-to-end sanitized Gate A CLI fixture and `git diff --check` passing.
- Fetched and reverified all 14 pinned source files (1,112,420,288 bytes) under `/data`; the source
  manifest is bound to the current pin/subset config and has SHA-256
  `500a62d09fb48e8e287cd01c46aa7e708cc3a3acd6c8079651a444e850645702`. No blind-v2 reference,
  model weight, adapter, checkpoint, or training run was created. No public row was marked
  approved.
- Profiled and temporarily imported the real pinned candidate subsets without source-native
  holdouts: 147,142 mapped rows, yielding 63,990 candidate, 81,325 quarantine, and 1,827 rejected
  rows. The sanitized profile proves public upper-bound shortages of 326 adversarial-primary, 53
  paragraph-primary, 402 adversarial cross-cutting, and 524 Unicode/multilingual rows.
- Added a deterministic 2,800-row pending-only supplement generator and configuration. Its dry run
  passes all 2,800 V2 records, supplies every measured gap, and remains outside Git. The combined
  148,115-row non-rejected candidate-pool audit reports no global primary or cross-cutting
  shortage; all selected rows still require explicit human approval.
- Detailed evidence: `docs/training/2026-08-17-RTX-A6000-PHASE0.md`.

## 2026-08-17 — Project bootstrap and Moonshine milestone

- Researched current Android, Moonshine, and Liquid LEAP integrations using official sources.
- Installed and verified the Android/macOS toolchain and connected Pixel 7.
- Created the Kotlin/View Android project and reproducible build/install/log scripts.
- Integrated Moonshine Small Streaming, model downloading/caching, raw transcript UI, and metrics.
- Fixed a first-load callback threading crash.
- Verified warm model loading and full airplane-mode transcription after cache warm-up.
- Replaced Moonshine `MicTranscriber` capture with project-owned `AudioRecord` because its Stop path
  kept microphone infrastructure open.
- Verified the required OS-level microphone lifecycle before, during, and after dictation.
- Fixed the Stop button shifting position during recording.
- Committed Milestone 1 as `3273684 Build local Moonshine dictation benchmark`.
- User evaluated a roughly one-minute dictation: capture lifecycle was correct, but Small Streaming
  accuracy and line segmentation were not good enough to assume it will be the final STT engine.
- Began Milestone 2: Liquid LFM2.5-230M cleanup smoke test and local evaluation corpus.
- Added LEAP 0.10.9, manual cleanup UI, raw pre-guard output, deterministic guardrails, a 24-case
  three-prompt on-device batch runner, and a host-side JSONL scorer.
- Ran 230M fully offline. Runtime/latency passed, but cleanup quality did not: safest prompt 3/24
  exact with 96.7% anchor preservation. Advanced to the planned 350M comparison.
- Ran the identical matrix on 350M. It was slower, only 1/24 exact, and changed negation/meaning;
  rejected both small models and began researching a stronger LEAP-compatible cleanup model.
- Downloaded and evaluated 1.2B-Instruct on the same 24 cases. The A/B/C matrix produced a best
  13/24 exact score, but that prompt changed meaning and failed all explicit self-corrections.
- Ran a focused strict/few-shot D/E iteration; quality regressed and median latency reached about
  4.9–7.0 seconds. Rejected the 1.2B model for automatic cleanup.
- Verified the 1.2B cache with a 1,928 ms airplane-mode load, then restored airplane mode. Measured
  about 901 MiB PSS (922,265 KiB) after the matrix with no overall Android thermal throttling.
- Added stricter lexical/intent guardrails and tests, preserved both raw result matrices, and parked
  cleanup before starting the independent STT evaluation phase.
- Removed the temporary app/device stay-awake overrides after the evals and restored the Pixel's
  original screen-timeout behavior.
- Committed the complete Milestone 2 cleanup harness, results, guardrails, and no-go decision as
  `8dce7ab Evaluate local cleanup models`.
- Researched current local-dictation projects and small on-device models. No audited open Android
  project was found with the exact local-STT + local-small-LLM + inline-IME pipeline. The strongest
  public patterns were task-specific Qwen fine-tuning and deterministic/hybrid cleanup.
- Selected a bounded cross-family screen: Granite 4.0 H 350M, Qwen3-0.6B no-think, and Gemma 3
  270M first; Qwen3.5-0.8B and Gemma 3 1B second. Chose LiteRT-LM for the first Qwen Android run and
  llama.cpp for GGUF/Granite portability, subject to the fixed quality gate.
- Added a 45-case held-out cleanup suite with no normalized-raw overlap with the original 24 cases,
  plus stronger corpus validation and a runtime-neutral OpenAI-compatible streaming runner.
- Added and tested a deterministic cleanup baseline. It reached 27/45 exact on held-out text in
  0.061 ms median host time, but failed all seven explicit self-corrections.
- Installed llama.cpp build 10450 and screened Granite 4.0 H 350M, Qwen3 0.6B, Gemma 3 270M,
  Qwen3.5 0.8B, and Gemma 3 1B on the fixed held-out set. The first four were clear no-go results.
- Gemma 3 1B reached 32/45 raw exact and 96/102 anchors, but an independent semantic audit found
  one conflicting retained correction and two obeyed embedded instructions. Rejected it as well.
- Ported Android's full cleanup guardrails to the host with parity tests and re-scored the captured
  raw outputs. Guard fallback improved preservation but could not repair failed corrections and
  initially missed two of Gemma's unsafe outputs. Added matched Kotlin/Python regressions for a
  dictated `output` command and a narrow imperative-to-imperative bare-`actually` correction; the
  guarded result now falls back on all three unsafe Gemma outputs.
- Stopped before Android runtime integration because no candidate earned Pixel performance work.
  Cleanup remains unjoined; the next active milestone is repeatable STT-only evaluation.
- Reprioritized after product review: cleanup is the actual blocker, while the current offline STT
  path is provisionally adequate. Moved formal STT evaluation behind task-specific cleanup.
- Started Milestone 4 with three parallel tracks: verify and screen the public VoiceInk
  Qwen3.5-2B fine-tune, define leakage-safe fine-tuning data and blind-v2 evaluation, and prepare a
  reproducible specialized-model host runbook.
- Pinned the author's exact VoiceInk training prompt and checksum-addressed 1.19 GiB Q4_K_M
  artifact, added a two-corpus llama.cpp screening orchestrator with full provenance, and began the
  internal model download. The fine-tune license remains a distribution blocker.
- Added the v1 cleanup-training JSONL contract and validator, including frozen-eval contamination,
  family/template split leakage, review/provenance, lexical-anchor, and manifest hash checks. No
  evaluation case has been reused as training data.
- Completed the checksum-verified VoiceInk inference-only screen with its exact author prompt. Raw
  output reached 12/24 seed exact and 26/45 regression exact, but only 2/10 corrections were exact;
  audit found six retained superseded edits, three meaning/fact changes, and one answered command.
  Rejected it for Android and automatic labeling.
- Confirmed that model training will happen later on the separate training machine. This Mac will
  only prepare portable data/tooling and run inference/evaluation.
- Added the GitHub remote and a root agent-routing file plus a self-contained RTX A6000 handoff.
  The handoff defines environment preflight, immutable source pins, data review/isolation,
  train/resume/monitor/evaluate phases, artifact policy, and a copyable new-session bootstrap
  instruction.
- Selected Sotto transcript cleanup as the primary public-data candidate and Disfl-QA/Nyra
  Disfluency Speech as supplements. Recorded immutable revisions and conservative rejection/
  quarantine rules; no dataset was downloaded, converted, approved, or used for training here.

## 2026-08-17 — Direct-source model decision and trainer

- Rechecked the current small-model families from primary sources. Kept Qwen3-0.6B for the initial
  fixed-data comparison, selected Qwen3.5-0.8B as the first stronger-base follow-up, retained
  Gemma 3 1B as the quality alternative, and retained LFM2.5-350M as the deployment-speed wildcard.
  Gemma 4 E2B is not sub-1B: it has about 2.3B effective and 5.1B total parameters.
- Chose BF16 rank-16 LoRA for the first run. A full sub-1B tune fits the A6000, but adaptation
  method will remain fixed until the source experiment shows whether LoRA capacity is limiting.
- Added a direct-source config and trainer for Sotto, Disfl-QA, Nyra, and combined runs. It keeps
  the reviewed Gate A trainer unchanged, verifies pinned source identities and payloads, checks
  frozen-corpus isolation, refuses silent truncation, applies assistant-only loss, and records
  sanitized source/tokenization/run evidence.
- Audited all configured splits successfully: Sotto 135,503/6,921, Disfl-QA 7,181 usable/1,000
  (one declared empty publisher train row), Nyra 4,458/250, and combined 147,142/8,171. No exact
  raw/target overlap with the 69 frozen diagnostic surfaces was found.
- All 97 script tests and all 10 host tests pass. Verified the idle 49,140 MiB RTX A6000, driver
  550.144.03, PyTorch 2.6.0+cu124, CUDA 12.4, and BF16 availability before the smoke launch.
- The smoke caught two mechanical incompatibilities before training: Transformers 5.14 returns a
  mapping from Qwen's chat template and no longer accepts `overwrite_output_dir` in
  `TrainingArguments`. Added focused compatibility fixes to the shared/direct trainers; all 98
  script tests and 10 host tests pass afterward.
- The third, unchanged smoke attempt completed at run
  `direct-sotto-qwen3-0.6b-smoke2-seed23-20260817T121729Z`: two optimizer steps, 1.4543 final train
  loss, 5.019 seconds trainer runtime, maximum formatted length 229 train/273 validation tokens,
  no truncation, checkpoint-2, and a 40,422,168-byte final adapter.
- Committed the pipeline and compatibility fixes locally through `9318f32`. Push is blocked:
  HTTPS cannot obtain credentials and the existing SSH key is not authorized for GitHub. The full
  one-epoch Sotto run remains unlaunched pending the required pre-run push or explicit direction.
