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

## 2026-08-17 — Full Sotto launch blocked by whole-corpus sequence audit

- Accepted the user's explicit direction to launch from local commit `53a5551` without the
  previously required GitHub push. Re-ran all 98 training tests and 10 host tests; the locked
  Python 3.10.12 / PyTorch 2.6.0+cu124 / CUDA 12.4 BF16 environment and idle RTX A6000 passed.
- The initial managed launch `direct-sotto-qwen3-0.6b-e1-seed23-20260817T122428Z` exposed a race:
  the read-only monitor created its files while the trainer was still checking that the new run
  directory contained only its managed console log. The trainer rejected the unexpected files
  before creating run state or taking an optimizer step. The evidence directory was preserved and
  the orphan monitor was stopped.
- Relaunched the identical recipe as
  `direct-sotto-qwen3-0.6b-e1-seed23-20260817T122523Z`, attaching the monitor only after the trainer
  wrote `status.json`. The trainer then failed closed before model load or optimizer work because
  `direct-sotto-train-75` formats to 1,294 tokens, above the fixed 1,024-token ceiling.
- Completed a text-free full-split audit: 775/135,503 train rows exceed 1,024 tokens (maximum
  1,838), and 46/6,921 validation rows exceed it (maximum 2,050). No source text was emitted or
  committed. Preserved the aggregate evidence in
  `docs/evaluation/results/2026-08-17-direct-sotto-token-length-audit.json`.
- Stopped at the documented recipe decision. Truncation and silent row dropping remain prohibited;
  the recommended recovery is a fixed 2,112-token limit across the four-way comparison followed
  by a longest-row memory smoke before a newly named full Sotto run.
- Verified the pinned Qwen3-0.6B context supports 40,960 positions. A transient exact longest-row
  test showed that raising only the ceiling is insufficient: the 1,838-token train row at the
  original microbatch 8 OOMed around 46.14 GiB process memory while requesting another 8.32 GiB.
- Compared two full-data/effective-batch-preserving alternatives without changing committed
  configuration. Microbatch 4 / accumulation 8 passed two optimizer steps at 31,865,443,328 peak
  allocated bytes in 13.84 seconds. Microbatch 8 / accumulation 4 with gradient checkpointing also
  passed at 29,088,355,840 bytes in 17.76 seconds. Eval batch 8 passed the 2,050-token longest
  validation row at 26,304,277,504 bytes.
- Recorded the text-free result in
  `docs/evaluation/results/2026-08-17-direct-sotto-2112-memory-diagnostic.json`. Recommend 2,112
  tokens plus microbatch 4 / accumulation 8 because it preserves effective batch and expected
  optimizer-step counts, avoids global checkpoint recomputation, and was faster in this bounded
  worst-case comparison. The full run remains paused for explicit recipe authorization.

## 2026-08-17 — Full Sotto training launch and publisher-recipe check

- Accepted the user's explicit authorization to train/evaluate without a pre-run push and to use
  the RTX A6000 autonomously. Committed the 2,112-token, microbatch-4/accumulation-8 fixed recipe
  as `c556709`; it preserves effective batch 32, one epoch, rank-16 LoRA, and all 135,503 Sotto
  rows. The earlier exact longest-row diagnostic served as the memory proof; per explicit user
  direction, no additional managed smoke delayed the full run.
- Launched the managed run
  `direct-sotto-qwen3-0.6b-e1-seed23-20260817T124158Z`. Complete token audits passed with no
  truncation (train maximum 1,838; publisher-validation maximum 2,050). At 2026-08-17 12:56 UTC
  the run was healthy at step 400/4,235, loss 0.1031, gradient norm 0.36. Three-minute GPU/disk/
  process/checkpoint monitoring and a terminal-status monitor remain active; no OOM, NaN, stall,
  checkpoint, thermal, or disk anomaly has been observed.
- Added and committed the outside-Git publisher-validation exporter as `64e8931`. Exported all
  6,921 pinned publisher-validation pairs under the run directory so full generation/scoring can
  begin immediately after the terminal adapter is verified. All 99 training tests and 10 host
  tests pass; unrelated untracked `t.txt` remains untouched.
- Checked the publisher's official Sotto materials. No formal paper was found; Sotto calls its
  evolving Hugging Face model card the full training research document. The most complete v23 SFT
  disclosure is LFM2.5-350M full tuning on 157,556 rows for three epochs, LR 3e-5, microbatch 1 /
  accumulation 8, cosine with 50 warmup steps, AdamW beta2 0.95, weight decay 0.01, BF16+TF32,
  packed 4,096-token context, and seed 42. Later production versions add GRPO, targeted data,
  two-epoch refinement at 2e-6, and checkpoint soup. Recorded immutable primary-source links and
  a comparison with the active Qwen LoRA recipe in
  `docs/research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md`.

## 2026-08-18 — Full Sotto completion and interim evaluation

- The full managed Sotto run completed all 4,235 optimizer steps and exited zero after 7,662.1
  seconds. Final train loss was 0.09389; publisher-validation loss improved from 0.09679 at step
  1,059 to 0.07938 at step 4,235. Checkpoints at 1,059, 2,118, 3,177, and 4,235 include adapter,
  optimizer, scheduler, RNG, and trainer state. The final adapter is 40,422,168 bytes and exactly
  matches checkpoint 4,235 with SHA-256
  `22736a4d4aff8b5788386a80d643296874c3b54dd980404e7196a5665023fa2b`.
- Run root:
  `/data/rise/android_stt/runs/direct-sotto-qwen3-0.6b-e1-seed23-20260817T124158Z`.
  Final adapter is `final-adapter/`; resumable state is in `checkpoint-*`, `trainer_state.json`,
  `metrics.jsonl`, and `status.json`. Raw evaluation artifacts are under `evaluation/` and remain
  outside Git.
- Ran the Sotto adapter concurrently on the untouched Disfl-QA dev and Nyra validation publisher
  splits. Disfl-QA reached 472/1,000 exact with 732 guardrail flags; Nyra reached 32/250 exact with
  76 flags. Three concurrent Qwen processes saturated the A6000 while using only about 6.0/49.1
  GiB VRAM. The evidence does not support skipping either standalone source training.
- Completed raw generation/scoring on the retired 24- and 45-case suites: 15/24 and 36/45 exact,
  153/163 anchors, 7/10 self-corrections, 15/17 must-not-answer, no empty outputs, 11 guardrail
  flags, and one cap hit. Agent review of every non-exact output found eight substantive raw-policy
  failures. This is a large quality improvement but fails the raw semantic-safety gate and is not
  a deployment candidate; the audit is not a human qualification.
- Added the sanitized interim evidence report at
  `docs/evaluation/results/2026-08-18-direct-sotto-qwen3-interim-evaluation.json`. Full 6,921-row
  Sotto publisher generation remains active under the same run directory and is monitored every
  500 records with immediate failure reporting.

## 2026-08-18 — Final Sotto publisher evaluation and next-run decision

- Full Sotto publisher generation completed all 6,921/6,921 rows and the managed evaluator exited
  zero. Exact match was 4,751/6,921 (68.65%); there were no empty outputs, 48 output-cap hits, and
  3,098 guardrail flags. Mixed-concurrency A6000 latency was 91.5 ms median TTFT and 583.4 ms
  median total, so it is not treated as a standalone latency benchmark.
- Verified and hashed publisher cases, results, their provenance sidecars, and the aggregate score
  under the completed Sotto run's `evaluation/` directory. Added the final text-free report at
  `docs/evaluation/results/2026-08-18-direct-sotto-qwen3-evaluation.json`; raw source text and model
  artifacts remain outside Git under `/data`.
- Confirmed the Sotto adapter remains a no-go: publisher exactness is weak and the fully reviewed
  retired diagnostics already contain eight substantive raw semantic-policy failures. Full manual
  review of all 2,170 non-exact publisher outputs was not performed because it cannot reverse that
  deployment decision.
- Selected the fixed-recipe standalone Disfl-QA adapter as the next controlled run, followed by
  Nyra. The combined run remains conditional on comparing the three standalone source adapters.

## 2026-08-18 — vLLM serving and sharded evaluation

- Cloned the official vLLM repository to `/home/shiva/vllm`, inspected current main for Qwen3.5
  guidance, then pinned the clean v0.8.5 commit compatible with the host's CUDA 12.4 driver stack.
  Created an isolated, fully locked uv environment under `/data/rise/android_stt/vllm` with Python
  3.10.19, vLLM 0.8.5, Torch 2.6.0+cu124, and Transformers 4.51.3.
- Added a hash-verifying local-only server launcher for the pinned Qwen3-0.6B snapshot and completed
  Sotto rank-16 LoRA. The profile uses BF16, 90% GPU memory, a 4,096-token request limit, 256
  sequences, a 16,384-token scheduler budget, prefix caching, vLLM generation defaults, and no
  request-payload or Uvicorn access logging. The smoke completion returned the expected text.
- Added deterministic SHA-256 case sharding, independent OpenAI clients, strict prefix resume,
  per-row corpus/config/shard provenance, raw qualification output with parallel guardrail fields,
  and a fail-closed source-order merger. The authoring path rejects blind inputs.
- Ran and validated the full 6,921 publisher rows plus the committed 24- and 45-case diagnostic
  corpora through the served LoRA. No sequential evaluation score or artifact was modified.
- Swept 16, 32, 64, and 128 publisher clients on the final server profile. Validated-merge wall
  times were 91, 87, 83, and 84 seconds; 64 clients is the measured default. Peak observed vLLM
  intervals reached 18.1k prompt tokens/s and 1.43k generated tokens/s with no waiting requests or
  preemption. Raw outputs and server artifacts remain outside Git under `/data`.
- Full verification passed: 111/111 script tests, 10/10 host tests, shell syntax, command rendering,
  smoke inference, diagnostic/publisher merges, and `git diff --check`. Sanitized evidence is
  `docs/evaluation/results/2026-08-18-vllm-sharded-evaluation.json`.
- A subsequent row-by-row comparison found that the 24- and 45-case vLLM diagnostics match their
  sequential outputs exactly, but publisher generation is not batch-invariant. Sequential raw
  exact was 4,751; vLLM runs ranged from 4,739 to 4,750. Each vLLM run changed 110–124 outputs
  relative to sequential inference, while two 64-client repeats changed 75 outputs relative to
  each other despite matching at 4,739 exact. All runs retained 6,921 rows, zero empty outputs,
  and 48 cap hits, confirming a generation reproducibility boundary rather than a shard/merge bug.
- Documented the fixed-backend comparison rule and stopped the local vLLM server after completing
  all requested evaluations.

## 2026-08-18 — Standalone Disfl-QA/Nyra results and combined launch

- Completed the unchanged Disfl-QA run at
  `/data/rise/android_stt/runs/direct-disfl-qa-qwen3-0.6b-e1-seed23-20260817T165542Z`: 225 steps,
  0.19946 train loss, 0.14729 final dev loss, no truncation, five resumable checkpoints, and a
  verified 40,422,168-byte final adapter. The fixed vLLM profile scored 765/1,000 own-source,
  100/6,921 Sotto, and 30/250 Nyra exact. Full retired-output review found 23 substantive safety
  failures, so the adapter is rejected.
- Completed the unchanged Nyra run at
  `/data/rise/android_stt/runs/direct-nyra-qwen3-0.6b-e1-seed23-20260817T171059Z`: 140 steps,
  0.12580 train loss, 0.07235 final dev loss, no truncation, four resumable checkpoints, and a
  verified 40,422,168-byte final adapter. Fixed-profile vLLM scored 150/250 own-source,
  1,479/6,921 Sotto, and 73/1,000 Disfl-QA. Retired exactness was 38/69 with zero of ten exact
  self-corrections; exhaustive review of all 31 non-exact raw outputs found 18 substantive safety
  failures. The adapter is rejected.
- Recorded text-free, hash-addressed Disfl-QA and Nyra reports under `docs/evaluation/results/`;
  raw pairs, outputs, checkpoints, review queues, and weights remain outside Git under `/data`.
- The standalone matrix establishes high source specificity, so launched the predeclared combined
  run unchanged at
  `/data/rise/android_stt/runs/direct-combined-qwen3-0.6b-e1-seed23-20260817T172338Z` from pinned
  commit `79d22a2`. It contains 147,142 train and 8,171 validation rows, expects 4,599 optimizer
  steps, passed frozen-surface overlap checks, and has durable 180-second telemetry plus terminal
  and error monitoring. No blind-v2 surface was used.
- At the user's request, gracefully interrupted that combined run at step 92/4,599 and preserved
  its run directory, logs, audits, telemetry, and `KeyboardInterrupt` terminal status. It had
  passed all input/isolation/tokenization gates; the stop was a recipe decision, not an OOM or
  training defect.
- Added a dedicated three-epoch combined learning-curve config and generalized the trainer's
  expected-step validation across integer epoch counts. The follow-up expects 13,797 optimizer
  steps and saves/evaluates exactly every 4,599 steps, yielding epoch-1, epoch-2, and epoch-3
  checkpoints. All other model/data/optimizer/batch/seed/sequence settings remain unchanged.
  The complete 112-script-test and 10-host-test suites pass before launch.
- Committed the learning-curve implementation as `00fae17`, created a clean detached training
  worktree under `/data`, verified the A6000 was idle, and launched
  `direct-combined-qwen3-0.6b-e3-seed23-20260817T173233Z`. The resolved 13,797-step config and
  147,142/8,171-row zero-overlap source audit are present; 180-second telemetry and durable
  terminal/error monitors are attached.

## 2026-08-18 — Combined three-epoch completion and checkpoint evaluation

- The combined run completed exactly 13,797 steps and exited zero after 23,584.5 seconds. It
  retained all 147,142 train and 8,171 validation rows with zero truncation. Complete resumable
  checkpoints are present at steps 4,599, 9,198, and 13,797; final-adapter bytes exactly match the
  epoch-3 checkpoint. Epoch validation losses were 0.09308, 0.08544, and 0.09364.
- Served each epoch checkpoint in turn through the same pinned vLLM 0.8.5 BF16 LoRA profile and
  ran 64-client Sotto/Disfl-QA/Nyra publisher sweeps plus four-client 24/45-case retired suites.
  Every chain exited zero, produced complete result sets, and was scored and hash-addressed.
- Epoch 1 scored 4,663/6,921 Sotto, 754/1,000 Disfl-QA, 129/250 Nyra, and 51/69 retired exact.
  Epoch 2 improved to 4,850, 769, 147, and 52 exact respectively. Epoch 3 reached 4,859, 773, 145,
  and 50; it also regressed validation loss and anchor preservation from 153/163 to 147/163.
- Exhaustively reviewed every non-exact retired raw output at each epoch. Found 8, 9, and 14
  substantive safety failures at epochs 1–3. All fail the raw semantic-safety gate; the audit is
  agent evidence, not human qualification, and guardrail fallback cannot change the decision.
- Selected epoch 2 (`checkpoint-9198`, adapter SHA-256
  `870ae3034e66b09c0e4e6b9f73c394a6fc69b035528a5f8c7faf5a18f880cb8e`) as research evidence
  only. It has the best validation loss, source-macro publisher score, and retired exactness.
  Epoch 3 shows that another epoch is counterproductive; do not extend this run.
- Added the final sanitized report at
  `docs/evaluation/results/2026-08-18-direct-combined-qwen3-learning-curve.json`. Raw outputs,
  review queues, serving logs/configs, environment reports, weights, optimizer state, and
  checkpoints remain outside Git under the completed run directory.

## 2026-08-18 — Public Sotto LFM2.5-350M checkpoint screen

- Pinned `juanquivilla/sotto-cleanup-lfm25-350m` at revision
  `6df6f019170b8b55333c047b901886a51750a965`, downloaded its 708,984,464-byte BF16 weight file to
  the external artifact store, and verified SHA-256
  `6e96eeffdcdd60f881e13eb2019b339b39d1a74951446f062e7e641a82f6422e`.
- Added a local-only, blind-refusing native-prompt Transformers runner with pinned model identity,
  weight verification, publisher decoding/parsing, raw generation, guardrail evidence, latency,
  and provenance. All 115 script tests pass.
- Ran all 69 retired diagnostics on the A6000. The model reached 42 exact outputs and preserved
  147/163 anchors, with zero empty/capped outputs and 19 guardrail flags. It transcribed rather
  than answered all 17 dictated questions/commands.
- Applied a practical manual audit that ignores harmless punctuation, contractions, and disposable
  conversational lead-ins. Six outputs still changed meaning or protected text, and seven more
  retained superseded correction content; the checkpoint is not ready for Android conversion.
- Added the hash-addressed report at
  `docs/evaluation/results/2026-08-18-sotto-lfm25-350m-public-screen.md`. Downloaded weights and raw
  results remain outside Git under `/data/rise/android_stt/`.

## 2026-08-18 — User-calibrated Sotto gate and next LFM experiment

- Reviewed all 27 non-exact public-Sotto outputs with the user. The immutable strict score remains
  42/69, while 59/69 are acceptable for the intended ordinary-conversation workload.
- Fixed the relevant baseline at ten failures: seven retained superseded corrections, two retained
  direct repetitions, and one statement changed into a question. The user explicitly excluded the
  malformed Gradle command and the other formatting, punctuation, contraction, normalization,
  bracket, name/currency, and technical-literal mismatches from this experiment's product gate.
- Approved a two-stage LFM2.5-350M study as the next work: two-epoch `2e-6` full-SFT continuation
  of the pinned public Sotto checkpoint on a deterministic 55/25/10/10 correction-weighted source
  mixture, followed—only after evaluation—by a three-epoch `3e-5` full-SFT reproduction from a
  pinned LFM2.5-350M base using the same mixture and disclosed publisher settings.
- Added the self-contained next-session plan at
  `docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md` and updated the training-machine handoff.

## 2026-08-18 — Sotto LFM campaign audit and data preparation

- Audited the existing trainers and rejected reuse of the Qwen LoRA/chat-template path for LFM:
  the campaign requires full-parameter SFT and the Sotto-native `### Input` / `### Output`
  completion format. Confirmed source-field mappings and publisher holdouts.
- Audited Transformers 5.14.1's LFM2 implementation and added explicit packed-example boundaries:
  reset `position_ids`, pass `seq_idx`, omit the ordinary attention mask, append EOS, supervise only
  the target, and fail rather than truncate. A real packed BF16 A6000 forward pass succeeded.
- Moved the pinned Sotto and Nyra snapshots into the global Hugging Face hub cache and verified
  offline resolution. Preserved DISCO English at its pinned `/data` path, stopped the redundant
  Nyra transfer, and deleted the inspected 449 MB duplicate staging tree.
- Initially prepared an exact 55/25/10/10 stream, then rejected it because it replayed Disfl-QA and
  DISCO more than five times per epoch. Prior Qwen evidence showed that the natural 92/5/3 combined
  mixture essentially matched source-specific Disfl-QA/Nyra performance after two epochs. Replaced
  the superseded artifact with a shuffled single-pass stream containing all 149,922 eligible train
  and 8,519 dev rows exactly once. Natural train shares are 90.38/4.79/1.86/2.97 for
  Sotto/Disfl-QA/DISCO/Nyra. The runtime seed is `5612273261405755832`; DISCO test remains excluded,
  and frozen-corpus screening removed two Sotto train rows. Manifest SHA-256 is
  `5a08a5692d82bff9b3f7556ca4933fd4554fef724257c4dd7a4ae25d36126080`.
- Added preparation, canonical-cache, full-SFT, packed-boundary, resume, and generalized LFM
  inference code plus focused unit tests.

## 2026-08-18 — File-fed Pixel Parakeet and power evaluation

- Added a debug-only ADB-driven STT benchmark Activity that never opens the microphone. It verifies
  a JSONL manifest and WAV hashes, decodes strict 16 kHz mono PCM16, warms once, runs three measured
  repeats, flushes atomic JSONL results, and keeps transcript text out of Logcat.
- Added a deterministic 24-clip, 12-speaker LibriSpeech `test-clean` probe prepared from pinned
  Hugging Face revision `71cacbfb7e2354c4226d01e70d77d5fca3d04ba1`; manifest SHA-256
  `7c90de45a130caf4ceb2f5215be114bd9daaa34e95549958440ccb7a95cc187f`.
- Pinned and cross-built `parakeet.cpp` v0.5.0 commit
  `1bfbebfaaf493866f49597cd3b7901959d395c60` with ggml
  `e705c5fed490514458bdd2eaddc43bd098fcce9b` for Android ARM64. Repaired the incomplete SDK
  Manager NDK r28 install from Google's checksum-verified archive.
- Prevented a native-library collision by statically embedding Parakeet's ggml rather than
  packaging another incompatible `libggml.so` alongside Moonshine/LEAP. Added the pinned C API ABI
  6 JNI bridge and ARM64 OpenMP runtime.
- Ran clean, idle, untraced Pixel comparisons. Moonshine scored 3.54% WER; Parakeet F16 1.69%;
  Parakeet Q4_K 1.85%. Q4_K was fastest at 717 ms median and 1,798 ms p90, used about 383 MiB PSS,
  and produced stable output across all repeats.
- Excluded an earlier F16 latency run after learning the phone was in active use; that run contained
  a 345.8-second outlier. Repeating from thermal 0 with competing Gmail work stopped reduced the
  maximum to 3.77 seconds without changing F16 output.
- Added p99/max latency, process CPU time, average core use, post-inference memory/thermal telemetry,
  and optional Perfetto on-device CPU/GPU/memory rail measurement restricted to measured inference
  trace slices.
- In matched power runs, Q4_K used 553.3 process-CPU seconds and 235.1 J compute energy versus F16's
  725.7 seconds and 306.6 J. Q4_K also used 8.6% lower average compute power and 25.5% less peak PSS.
  GPU rail energy was negligible because the build is CPU-only.
- Changed the provisional STT candidate from F16 to Q4_K after the user accepted one extra proper-
  name substitution in exchange for the measured efficiency gains. F16 remains the quality
  reference; live streaming and dictation-focused protected-token qualification remain unbuilt.
- Added the STT benchmark and result report to the project and evaluation indexes so the new
  workflow and evidence are discoverable from both documentation entry points.

## 2026-08-18 — Joined Parakeet/Sotto integration build

- Replaced the ordinary Activity's Moonshine/Liquid execution with a swappable joined path using
  the selected Parakeet TDT/CTC 110M Q4_K artifact and the pinned public Sotto LFM2.5-350M model.
  Parakeet owns a 16 kHz mono `AudioRecord`, stops it synchronously at Stop, and runs one final
  offline inference without fabricated partials. Every non-empty final transcript flows to Sotto.
- Added a sideloaded LEAP Sotto engine with its native completion prompt, greedy decoder, delimiter
  parser, complete raw-output retention, and the existing semantic guardrail/fallback layer.
- Pinned and converted the public BF16 checkpoint to F16 GGUF and a 229,310,304-byte Q4_K_M GGUF.
  Added a source-hash-verifying exporter, scoped LFM2.5 tensor mapping patch, and ADB staging script;
  all model outputs and conversion checkouts remain ignored outside Git.
- Added immutable runtime hashes and model-file verification, shared Parakeet JNI loading, joined UI
  states, automatic cleanup, and end-to-end tail reporting. The Activity labels the public Sotto
  model as integration-only and keeps raw STT, raw model output, and guarded output visible.
- Lint, unit tests, assembly, shell syntax, and diff checks pass. Installed and staged both models
  on Pixel 7. Both loaded, direct cleanup ran, and a real microphone → Parakeet → Sotto smoke
  completed with a 1,568 ms STT tail and 2,029 ms end-to-end tail. The smoke also reproduced a
  meaning-affecting Sotto deletion that guardrails rejected, reinforcing that integration success
  does not qualify this placeholder model.
- Added the sanitized, hash-addressed evidence manifest at
  `docs/evaluation/results/2026-08-18-parakeet-sotto-integration-build.json`. No evaluation corpus,
  blind reference, raw personal transcript, model weight, or checkpoint was used as training data
  or added to Git.

## 2026-08-18 — Conservative pre-model filler removal

- Added a deterministic Sotto input pass that removes only standalone `um`, `uh`, and `erm` before
  inference. It leaves ambiguous discourse/uncertainty words untouched and preserves uppercase
  acronyms, likely title-cased names without filler punctuation, quoted text, `uh-oh`, paths,
  identifiers, and paragraph breaks.
- Extended cleanup results and batch JSON with original raw text, exact model input, removed filler
  tokens, and a model-executed flag. The Activity now displays the exact text sent to Sotto and the
  removal count while keeping the Parakeet transcript unchanged.
- Guardrails evaluate Sotto against the deterministic model input. A rejected generation falls back
  to that visible pre-cleaned text; filler-only input skips Sotto rather than prompting it with an
  empty payload.
- Added focused JVM coverage for punctuation, unpunctuated fillers, ambiguous words, quoted/code-
  like text, acronyms, likely names, paragraph preservation, and filler-only input. The complete
  Android lint/unit/assembly gate passes. The updated APK installed successfully on Pixel 7; the
  interactive UI smoke remained pending because the phone re-entered its secure lock screen.

## 2026-08-18 — Mac-local Qwen3-TTS fixture pipeline

- Added a locked Python 3.12 environment for MLX-Audio 0.4.6 and pinned
  `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit` at revision
  `41d3337e8b7f2843a75841595fc14e4b9a7a4b96`. Kept the inspected MLX-Audio checkout under
  `~/Documents/projects/mlx-audio` at release commit
  `d28d68c6ac4e28f7d2d66007f640b06cf3fd8ceb` as requested.
- Added generic literal-text and bounded cleanup-regression entry points, stable per-case seeds,
  strict source allowlists, resumable generation, atomic progress, 24 kHz master retention,
  deterministic ffmpeg conversion, WAV/silence/clipping validation, and Android-compatible
  manifests. All dependencies, model files, masters, and canonical WAVs remain ignored locally.
- Projected only the `spoken` input field from the retired cleanup suites. The TTS generation plan
  contains no simulated `raw` transcript, cleanup `expected`, must-preserve anchors, prompt,
  captured model output, VoiceInk material, or blind-v2 data.
- Added 20 project-authored regression utterances spanning protected names/Unicode, numbers,
  times/dates/currency/phone strings, versions, paths/URLs/identifiers, corrections, negation,
  uncertainty, questions/commands-as-data, formatting directives, homophones, repetition, and a
  35-second long-form case.
- Verified the cached model with network disabled, then generated 45 heldout-v1 retired-regression
  clips plus the 20 additional cases entirely offline. All 65 native and canonical WAVs pass
  hashes and format checks, contain 401.28 seconds of audio, show no clipped samples, and retain a
  byte-stable manifest across resume. Manifest SHA-256 is
  `10a06cdece044e4c0383eb5719461fdba3b74cb6638efd9d5c238cf7728964cf`.
- Added sanitized evidence at
  `docs/evaluation/results/2026-08-18-mac-qwen3-tts-fixture-corpus.json`. The 10 TTS tests pass;
  the repository suite is 126/127 with only the existing macOS `/var` versus `/private/var`
  temporary-path assertion failing. Listening review and real-speaker qualification remain open.

## 2026-08-18 — Acoustic TTS joined-pipeline regression

- Loaded the hash-pinned Parakeet Q4_K and public Sotto Q4_K_M models once in the installed Pixel
  Activity, then played all 20 project-authored synthetic dictation stress fixtures from the Mac
  speakers through the Pixel microphone. UI automation captured every raw transcript, exact
  post-filler model input, unguarded Sotto output, guarded result, and stage timing.
- The app completed 20/20 cases without a crash, recorder leak, failed model state, or missing
  result. Median Stop-to-STT was 934 ms, median cleanup total 565 ms, and median Stop-to-cleanup
  1,466 ms. The 35-second long-form case completed at 3,350 ms STT tail and 5,484 ms end to end;
  final thermal status was 0.
- Parakeet reached 4/20 strict and 11/20 normalized exact on the uncontrolled speaker-to-microphone
  path. Names, spelled letters, URL/path surfaces, and the long-form `Ravi` name were weak.
- Sotto fell back on 15/20 cases. It correctly resolved the beta-to-canary correction in case 011,
  but the guardrail falsely rejected it. More seriously, case 014 changed a dictated technical
  command and the guardrail accepted the unsafe edit. This confirms that public Sotto remains an
  integration-only no-go and that guardrail fallback cannot establish raw semantic safety.
- Added the complete sanitized report at
  `docs/evaluation/results/2026-08-18-parakeet-sotto-tts-acoustic-integration.md`; the synthetic
  fixtures remain ignored regression evidence and were not used as training data.

## 2026-08-18 — Personal conversation suite and fast joined file runner

- Retired the technical v1 synthetic cases from the active product workload and replaced them with
  20 evaluation-only personal-conversation examples: messages, journal entries, lists, common
  names/numbers, uncertainty, repetition, formatting directives, and natural self-corrections.
  Explicitly excluded git/URL/checksum/CLI/path/TLS/version stress examples after user calibration.
- Added a debug-only joined Activity and host launcher accepting a corpus or one WAV/MP3. The host
  canonicalizes single files; the Activity verifies audio and staged model hashes, never opens the
  microphone, loads Parakeet and Sotto once, and exports complete per-stage JSONL. The scorer keeps
  spoken-reference STT metrics separate from intended-cleanup target metrics.
- Generated all 20 personal v2 Qwen3-TTS clips offline. Manifest SHA-256 is
  `771d2fff6b1d9bf8c2e9492d483dbe461f07dd7176996ad6f817e9e5f7c62029`; generated audio and manifests
  remain ignored under `.cache/`.
- Completed the valid-timing Pixel run in roughly one minute: 20/20 completed, 6/20 strict and
  16/20 normalized STT exact, 8/20 strict and 10/20 normalized intended-cleanup exact, and three
  guardrail fallbacks. Final STT/cleanup/joined medians were 499/637/1,135 ms. All three fallbacks
  were retained explicit corrections in raw Sotto output; guardrail fallback did not make them
  successful cleanup.
- Recorded and fixed the guardrail design problem exposed by the earlier run. Literal surface-token
  protection had falsely rejected sentence-initial `Well` deletion, explicit correction
  replacement, and word→equivalent-digit/time rendering. Android and host parity code now permits
  those bounded edits plus consumed explicit list/paragraph directives and one exact abandoned
  journal lead-in, while changed values/names/negation/uncertainty still fail closed.
- Updated the root README, TTS guide, training-machine handoff, current state, next steps, decisions,
  test log, and durable evaluation report. Personal v2 and all captured results remain strictly
  evaluation-only and are forbidden as training or demonstration material.

## 2026-08-18 — Personal v3 long-form and checkpoint-evaluation handoff

- Preserved v2 as immutable historical evidence and created personal v3 after the user removed
  phone-number dictation from scope. V3 retains 16 short/medium personal cases and adds four
  3–5 sentence journal/message/planning cases for longer cleanup latency.
- Generated all 20 v3 synthetic clips offline. The manifest SHA-256 is
  `35f43e00b8e2a6fa7d95ae15de96ed75db5af82a62ca95dcd9ce079a6b69794e`; audio remains ignored.
- Ran v3 through the file-fed Pixel path: 20/20 complete, 15/20 normalized STT exact, 10/20
  normalized intended-cleanup exact, and three retained-correction fallbacks. Median
  STT/cleanup/joined latency was 625/645/1,261 ms.
- The four long cases contain 14.88–25.84 seconds of audio and completed at 2,543–4,746 ms joined.
  The longest planning/correction case remained the slowest and fell back because Sotto retained
  both times.
- Added `cleanup_personal_conversation_v3.jsonl`, a standard scorer-compatible direct-text corpus,
  plus hash-pinned checkpoint identity options in `infer_sotto_lfm.py`. Updated the LFM experiment
  plan and training-machine handoff with commands requiring the public start and every Experiment
  A/B epoch to run v3 with raw review and per-long-case latency.
- V3 is evaluation-only. Its examples, expected output, results, errors, and phrasings remain
  forbidden from training, prompt demonstrations, retrieval, preference data, and repair
  generation.
## 2026-08-18 — Sotto LFM full-SFT campaign completion

- GPU smoke tests and Experiment A ran only after the exact inputs were tested and hash-recorded.
  Per subsequent user direction, dirty or unpushed Git state is explicitly allowed and is not a
  launch gate.
- The first 32-row overfit invocation stopped before training because a generated 63-bit seed was
  outside NumPy's accepted unsigned 32-bit range. Preserved the failed run and traceback, changed
  generated training seeds to the NumPy-compatible range, and retained the wider preparation seed
  because it is used only by Python's shuffle implementation.
- Re-ran the corrected full-parameter gates successfully. The 60-step 32-row overfit reduced loss
  from 0.75067 to 0.23514; the longest-example smoke completed with no truncation; the deliberate
  step-2 interruption resumed through step 4; and a reloaded saved checkpoint generated an exact,
  guardrail-clean result for the first retired diagnostic. All 126 script tests pass.
- Deleted the five inspected heavyweight smoke `checkpoint-*`/`final-model` directories after the
  reload gate, reclaiming 6.0 GB while retaining status, telemetry, manifests, hashes, logs, and
  the one-case inference evidence.
- Launched two-epoch full-SFT Experiment A on the RTX A6000 at
  `/data/rise/android_stt/runs/sotto-lfm-a-full-20260818T061643Z-dirty`. The run records the dirty
  Git paths plus exact code/config/data/model hashes, and has a live metrics monitor attached.
- Experiment A completed all 542 steps in 1,542.8 seconds. Dev loss improved from 0.15292 at epoch
  1 to 0.14940 at epoch 2; both 2.0 GB resumable checkpoints and the byte-identical epoch-2 final
  model are retained. Peak sampled GPU allocation was 13.3/49.1 GB and the artifact volume remained
  at 14% use.
- Fixed sequential retired evaluation gives 47/69 exact at both epochs versus 42/69 for the public
  start checkpoint. Epochs 1 and 2 produce identical text on all 69 cases. The run fixes most of
  the ten user-relevant failures, but `cleanup-004` changes a question into an imperative and
  `cleanup-021` deletes “works better.” Per user calibration, dropping “probably” on
  `heldout-036` remains logged but is not a product go/no-go gate.
- Added a token-budgeted batched Transformers evaluator and proved it exactly reproduced all 69
  sequential outputs at max batch 64 / 32,768 padded prompt tokens before using it on publisher
  dev. Start/epoch-1/epoch-2 overall exact counts were 2,736/4,636/4,670 of 8,519. Epoch 2 remained
  net-positive on every source: Sotto 4,101/6,921, Disfl-QA 320/1,000, DISCO 199/348, and Nyra
  50/250. Raw outputs remain outside Git.
- Because epoch 2 still changed 348 source-dev outputs and gained 34 net exact matches, launched a
  separately named four-epoch learning curve from the same public checkpoint at
  `/data/rise/android_stt/runs/sotto-lfm-a4-full-20260818T071437Z-dirty`. It changes only the epoch
  horizon and checkpoint retention, uses one new four-epoch cosine schedule rather than silently
  restarting the completed schedule, and has live monitoring attached.
- The four-epoch learning curve completed all 1,084 steps in 3,078.3 seconds. Dev loss by epoch was
  0.14752, 0.13859, 0.13755, and 0.13746. Source-dev exact rose from 2,736/8,519 at the public start
  to 4,709, 4,868, 4,883, and 4,889. Epoch 4 remained net-positive on every source: Sotto
  4,231/6,921, Disfl-QA 401/1,000, DISCO 201/348, and Nyra 56/250.
- Retired exact was 47/69 at epoch 1 and 46/69 thereafter. The epoch-4 model fixes or acceptably
  handles eight of the ten user-prioritized cases, but still converts `cleanup-004` from a question
  to an imperative and deletes “works better” from `cleanup-021`. It also reaches the 900-token cap
  with repetition loops on two source-dev rows. Selected epoch 4 as the best research checkpoint,
  but marked it not deployment-qualified; the flat epoch-3-to-4 gain does not justify epoch 5.
- Wrote the sanitized learning-curve result to
  `docs/evaluation/results/2026-08-18-sotto-lfm-a4-learning-curve.json`. Raw source outputs remain
  outside Git. All four resumable checkpoints remain retained for comparison with the predeclared
  clean-base Experiment B; artifact storage still has more than 9 TB free.

## 2026-08-18 — Separate GPT-5.4 hosted-API pilot

- Created `docs/evaluation/GPT54_CLOUD_API_EVALUATION.md` as an isolated optional cloud campaign;
  it is explicitly not part of the local-LLM training plan. Recorded the user's authorization to
  send both committed evaluation corpora while retaining evaluation-only and blind-v2 boundaries.
- The first heldout pilot attempt was blocked locally before transmission. Switched the pilot to
  four older seed cases. The first API compatibility request returned HTTP 400 without generation
  because GPT-5.4 rejects `max_tokens` and requires `max_completion_tokens`.
- Added a fingerprinted `--output-token-field` runner option, kept `max_tokens` as the local-server
  default, protected both cap fields from request-extra overrides, and added focused unit coverage.
  All 12 runner tests pass.
- Completed four successful sequential requests on each dated model with the frozen baseline
  prompt, streaming, standard/default service tier, `reasoning_effort=none`, temperature 0.1, seed
  23, raw scoring, and Android-equivalent caps. GPT-5.4-mini used 418 input/64 output tokens and
  scored 2/4 raw exact; GPT-5.4 used 418/57 and scored 3/4.
- Median TTFT/total was 932/1,156 ms for mini and 1,209/1,336 ms for full. Mini retained a
  superseded correction; full title-cased a protected literal. The sample is not a selection
  result. Preserved hashes and the conservative no-cache paid-cost estimate in
  `docs/evaluation/results/2026-08-18-gpt54-api-pilot.md`; raw JSONL remains under ignored `build/`.
- Paused before the complete 138-request evaluation so the user can confirm the Usage dashboard
  attributes the 957 successful tokens to the data-sharing incentive tier without a Cost increase.
- Downloaded pinned `LiquidAI/LFM2.5-350M-Base` revision
  `9960764e30892e01f29a6dc23df2533fcd8bd5ae` into the machine-wide Hugging Face cache and pinned
  its weight SHA-256 as `af70818c41a5cdb3f9587f91de12ff5f7847b8b0a2ba734534205ccea1d98aba`.
  Its tokenizer produces byte-for-byte-equivalent tokenization and packing statistics to the
  public task-tuned checkpoint. Clean-base format and BF16 full-parameter overfit gates passed;
  the 32-row loss fell from 0.88651 to 0.0000153. Reload inference succeeded, then the 681 MB
  smoke final-model copy was deleted while retaining compact evidence.
- Completed clean-base Experiment B at
  `/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty`: 813 steps over three epochs
  in 2,358.6 seconds with generated seed `3084480448`. Dev loss was 0.10190, 0.09617, and 0.10112.
  All three 2.13 GB resumable checkpoints are retained, with weight SHA-256 values
  `e9d552f472374b51f8d59fe67623e0ae737ca9393a4b28d87341e9f5fab5de65`,
  `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6`, and
  `7e817690331e4d8f5e067ff8df1e499de1013567f70c8dbb976ce52820db6ffb`.
- Evaluated every Experiment B checkpoint on all 8,519 source-dev rows and all 69 retired
  diagnostics. Source exact rose 5,477→5,731→5,796, but retired exact regressed 51→47→46 and
  anchors regressed 155→149→149 of 163. Epoch 1 handles nine of ten user-prioritized cases and
  retains the `cleanup-021` rationale; `cleanup-004` still changes a question into an imperative.
  It also has one source repetition loop plus independent command, identifier, name, and structured
  payload failures. Selected epoch 1 as the safety-weighted research checkpoint, but marked the
  entire campaign not deployment-qualified. Raw outputs remain outside Git.
- During monitoring, sandboxed process visibility briefly hid the still-running authoritative
  trainer and prompted two redundant launches. Host-level inspection corrected the record; both
  duplicates were intentionally stopped at step 1 without checkpoints, while the original run
  continued to completion. Preserved correction notes and recorded the lifecycle in the sanitized
  A/B report rather than erasing the audit trail.
- Wrote `docs/evaluation/results/2026-08-18-sotto-lfm-ab-comparison.json`. It selects clean-base
  epoch 1 over public-refinement epoch 4 by +588 source exact, +5 retired exact, +11 protected
  anchors, and one fewer cap hit. The later clean-base source leader is not selected because its
  safety diagnostics regress. Test-only heavy weight copies remain deleted; artifact storage has
  over 9 TB free.

## 2026-08-18 — Remote evaluation integration and personal-v3 checkpoint matrix

- Fetched remote `main` and inspected its eight dependent commits. Integrated them at merge
  `ab85a54`; the two newest are `b0ed579` (personal voice regression and fast joined runner) and
  `cd77e76` (personal-v3 long-form checkpoint evaluation). Preserved the existing dirty campaign
  work in its original unstaged form and retained a named safety stash.
- Confirmed why the active evaluation changed: ordinary personal messages/journals/lists now
  replace technical stress prompts, the phone-number case is removed, four 3–5 sentence cases add
  long-form coverage, and bounded correction/number/formatting equivalence is represented without
  weakening name, value, negation, uncertainty, invention, or answering checks.
- Verified the v3 corpus, runner, and all eight model-weight hashes. The focused runner/batched/
  guardrail unit suite passed 34/34. Ran public start, A epochs 1–4, and B epochs 1–3 sequentially
  in BF16 on all 20 cases; every run completed without a token-cap hit.
- Public start leads at 11/20 exact, 53/61 literal anchors, and 15/20 all-anchor cases. A epochs are
  all 8/20 and 50/61. B epochs are 7/20 and 46/61, 8/20 and 50/61, then 8/20 and 47/61. B epoch 2
  is therefore best fine-tuned on v3, but public start remains the strongest product checkpoint.
- Reviewed every non-exact and safety-sensitive raw output. All A epochs change a currency unit;
  public and B avoid unsupported substitutions in this suite but retain required corrections and
  formatting directives. The guard misses the A substitution and a public numeric-surface
  correction retention, while falsely rejecting valid A numbered-list formatting. No fine-tuned
  model advances to Android.
- Raw/provenance JSONL remains outside Git under
  `/data/rise/android_stt/evaluations/personal-v3-20260818/`; sanitized evidence is
  `docs/evaluation/results/2026-08-18-sotto-lfm-personal-v3-checkpoint-matrix.md`.

## 2026-08-18 — GPT-5.4 hosted API full and publisher-dev screens

- After the user confirmed the pilot calls were complimentary, completed sequential raw-output
  runs on all 24 seed and 45 heldout-v1 cases for both dated hosted models. Mini reached 27/69
  exact and 155/163 anchors; GPT-5.4 reached 51/69 and 150/163. Mini retained superseded content in
  eight correction cases. GPT-5.4 answered dictated instruction text with `Approved`; both fail
  the raw deployment gate.
- Reused the checkpoint harness's public/synthetic 8,519-row source-dev input set without running
  any checkpoint inference. Mini completed all rows at 2,358/8,519 exact. GPT-5.4 completed a
  deterministic 1,500-row source-stratified sample at 511/1,500, versus mini 380, existing A4 848,
  and existing B1 951 on the identical IDs.
- Added hosted `max_completion_tokens` forwarding to the sharded launcher, a selectable
  Android/publisher output-cap policy, live API-reported input/output aggregation, prior-use
  offsets, and an automatic campaign token cutoff. The focused runner/sharding suite passes 17/17.
- Mini's first source pass used the Android cap and retained 52 documented cap hits per the user's
  direction to leave the completed run alone. GPT-5.4's seven cap-hit rows alone were rerun with
  the checkpoint evaluator's 900-token allowance; they produced zero exact matches and no final
  cap hits. No mini repair API request was sent.
- Mini used an estimated 1,131,170 campaign tokens after reconstructing one missing usage trailer.
  GPT-5.4 live accounting stopped at 212,019, below the 220k automatic cutoff and 250k pool. Total
  hosted traffic was 1,343,189 tokens, corresponding to $2.4309 at captured standard rates if
  billed. Raw API artifacts remain ignored under `build/`; the sanitized decision, costs, timings,
  and hashes are in `docs/evaluation/results/2026-08-18-gpt54-api-screen.md`.

## 2026-08-18 — Hosted GPT personal-v3 rerun with GPT-5.6 Luna

- Used the user's explicit authorization to send only the 20-case evaluation-only personal-v3
  corpus to the OpenAI API. Loaded the credential from local `free_usage.md` without printing it;
  added that filename to `.gitignore` and restricted it to owner-only mode `0600`. No
  HF/publisher source-dev, retired-69, or blind-v2 request was made.
- Ran dated GPT-5.4-mini, dated GPT-5.4, and `gpt-5.6-luna` sequentially with the frozen
  `baseline_rules` prompt, streaming, standard/default service tier, `reasoning_effort=none`,
  temperature 0.1, seed 23, raw scoring, and Android-equivalent completion caps. All 60 requests
  completed on their first attempt with `stop`, non-empty output, and no cap hit.
- Mini/full/Luna reached 10/12/12 strict exact of 20 and 53/55/55 literal anchors of 61. The user
  explicitly accepts collapsed `really really` emphasis; under that calibration full and Luna are
  20/20 acceptable, while mini is 18/20 because cases 002 and 011 retain superseded content. Luna
  had the best median total latency at 649 ms versus 827/860 ms.
- The extension used 7,164 input and 1,631 output tokens. Captured standard paid equivalent is
  $0.01951 total. Raw results remain ignored under `build/evaluation-results/gpt-personal-v3/`;
  the sanitized report and exact result hashes are in the hosted API screen.

## 2026-08-18 — Default relaxed calibration and cross-model comparison

- Made version 1 of `docs/evaluation/PERSONAL_CLEANUP_ACCEPTANCE.md` the default product-ranking
  policy. User-calibrated semantic acceptability now leads result tables; strict exactness and
  literal anchors remain immutable secondary diagnostics. The policy accepts harmless surface
  equivalence and collapsed duplicated intensifiers but retains hard failures for corrections,
  facts/units/tense, negation/uncertainty, answered content, invention/deletion, and unfulfilled
  explicit formatting directives.
- Re-reviewed all 160 existing local raw outputs covering the public Hugging Face Sotto SFT, A
  epochs 1–4, and B epochs 1–3. No local inference was rerun. Public and every A epoch reach 14/20
  acceptable; all B epochs reach 15/20. B fixes public's case-002 time correction but still fails
  cases 011, 014, 017, 019, and 020. A additionally changes past tense and euros to dollars.
- Compared those results with the 60 hosted outputs. GPT-5.4 and Luna reach 20/20 acceptable, mini
  18/20, B 15/20, and public-HF/A 14/20. Luna leads the hosted option on latency/cost. The revised
  local ordering does not authorize checkpoint conversion or replacement because B still fails
  required behavior and its broader safety evidence remains disqualifying.
- Preserved the immutable v3 case file and historical strict results. Added the policy and complete
  case-level failure matrix in
  `docs/evaluation/results/2026-08-18-personal-v3-relaxed-cross-model-comparison.md`; no evaluation
  text or outputs were used for training or repair generation.
- Corrected the formatting submetric to require both realizing and consuming each directive:
  public and B are 0/3, A is 1/3, and all hosted models are 3/3. Recorded the user-authorized Pixel
  integration handoff for Luna plus local B epoch 2. The local checkpoint stays on `dante` at
  `/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty/checkpoint-542`; no weights
  are included in Git.

## 2026-08-18 — Luna versus B epoch-2 Pixel comparison, local half

- Read the project/training handoffs and recent comparison commit, verified the Pixel 7 connection,
  and confirmed B epoch 2 on `dante`. Copied only inference files, not the 1.42 GB optimizer state;
  the 708,984,464-byte source weight hash remains
  `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6`.
- Added a reproducible export for the current Transformers checkpoint shape. The compatibility
  aliases are applied only in an ignored export copy. The final 229,310,336-byte Q4_K_M hash is
  `02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0`;
  weights and GGUFs remain outside Git.
- Added a debug-only direct cleanup benchmark and extended the joined runner with selectable Sotto
  identity, process CPU, tokens/s, PSS/heap/thermal data, and separate Perfetto STT/cleanup trace
  slices. Added projected hosted-E2E input and timing-combination tools. No transcript is written
  to Logcat.
- Direct B Q4_K_M completed 60 measured Pixel calls after one model warmup: 15/20 manually
  acceptable, 8/20 strict, 46/61 literal anchors, 1/3 corrections, and 0/3 formatting. Median
  TTFT/total are 159/481 ms, decode is 38.0 tokens/s, peak PSS is 669,140 KiB, and attributed
  cleanup compute is 161.62 J total or 2.69 J/call at 3.84 W. Thermal status stayed 0.
- The 20-case Parakeet-fed run reached 15/20 normalized STT exact and 8/20 normalized raw cleanup
  exact. Manual cleanup acceptance is about 13/20; failures separate STT name/number damage from
  Sotto correction/formatting gaps. Median STT/cleanup/pipeline are 764/784/1,552 ms. Attributed
  STT plus cleanup energy is 143.69 J, or 7.18 J per utterance; joined peak PSS is 920,517 KiB.
- Did not run the hosted joined half. `OPENAI_API_KEY` is unset, and the only historical credential
  found is in macOS Trash. It was not restored or used implicitly. The already projected exact
  post-filler Parakeet input is ready for a 20-call Luna run once a credential is authorized.
- Published aggregate-only interim evidence, later superseded by the complete
  `docs/evaluation/results/2026-08-18-luna-vs-sotto-b-epoch2-pixel.md`. Raw personal output, audio,
  traces, projected hosted inputs, models, and checkpoint files remain ignored.

## 2026-08-18 — Luna direct and Parakeet-fed completion

- The user identified and authorized the credential in `free_usage.md`. Extracted exactly one key
  token without displaying or copying it into the repository. Sent only the 20 active direct cases
  and 20 exact post-filler Parakeet inputs; no retired/source-dev/blind-v2 request was made.
- The first 40 requests revealed that the streaming profile omitted usage. Added
  `stream_options.include_usage=true` and repeated the same 40 requests for canonical token/cost
  evidence. All 80 calls finished on their first attempt with `stop`, non-empty output, and no cap
  hit. The first pass is excluded from canonical latency/result identity but bounded in total cost.
- The first E2E scoring attempt also caught spoken-surface preservation anchors in the projection.
  The API request's `raw` and `expected` fields were already correct; only scorer metadata was
  wrong. Rebuilt from the cleanup case contract, added pre-request anchor validation, and scored
  against projection SHA-256
  `027819989c3a7a31d83028a31f978f5c25c13d213084dbb880540f130300b78b`.
- Canonical Luna direct: 20/20 acceptable, 11/20 strict, 54/61 anchors, 3/3 corrections, 3/3
  formatting, and zero raw semantic failures. Median TTFT/total are 630/836 ms; p95 total is
  1,127 ms. Usage is 2,388 input plus 534 output tokens, or $0.001118 paid-equivalent.
- Canonical Parakeet→Luna: 17/20 acceptable, 9/20 strict, 53/61 anchors, 3/3 corrections, and 3/3
  formatting. Estimated cleanup/pipeline medians are 941/1,585 ms. Luna correctly repairs the
  train-time ASR error, but on case 012 it changes protected `ICO` into a first-person subject.
  The guard flags it; the raw semantic failure keeps Luna out of automatic deployment.
- Canonical 40-call usage is 4,763 input and 1,068 output tokens ($0.002234). Including the first
  usage-less pass, completion caps bound all 80 requests at $0.005353 paid-equivalent; the user's
  dashboard remains authoritative. Cloud-server and Pixel-radio energy remain unmeasured.
- Replaced the interim report with
  `docs/evaluation/results/2026-08-18-luna-vs-sotto-b-epoch2-pixel.md`. Luna is the leading optional
  hosted candidate, while both Luna and Sotto remain raw-gate no-go results.

## 2026-08-19 — Sotto B default integration and product roadmap

- At explicit user direction, promoted Sotto B epoch 2 from a debug benchmark override to the
  ordinary app's provisional fully local cleanup default. Pinned the existing 229,310,336-byte
  Q4_K_M filename and SHA-256 in `IntegrationModels`, changed the default staging source and device
  destination, and added a unit test locking the identity.
- Updated the Activity copy to identify B epoch 2 and state its known correction, formatting, and
  semantic-safety failures. The UI continues to expose raw model output, guarded output, and
  fallback behavior; `CleanupEngine` and the debug artifact override remain swappable. This is an
  integration choice, not deployment qualification.
- Reworked the handoff and ordered roadmap. The joined Activity baseline is complete at the host
  boundary; the active product step is a minimal voice-only `InputMethodService`, followed by
  daily-driver lifecycle/polish, consented human and multi-speaker dictation evaluation, Parakeet
  streaming/qualification, fresh cleanup research, and a later evidence-backed model swap.
- Offline Android lint, unit tests, and debug assembly pass. The generated APK is 88,045,661 bytes
  with SHA-256 `2b40bd16238df4285cfcf48b5d826238a6175e7d8638a3ab1d2694439e7edf92`.
- Tried both the install/staging workflow and a direct ADB check, but no device was attached. The
  final no-override Pixel reinstall/stage/file-fed smoke remains explicitly open rather than being
  inferred from the earlier B benchmark runs.

## 2026-08-19 — Minimal voice IME host implementation

- Implemented and registered a voice-only `InputMethodService` without requiring Pixel access.
  Its compact view provides local model load, explicit Start/Stop, Cancel, bounded Undo, and a
  switch-to-next-keyboard action. Added setup controls in the Activity for microphone permission,
  Android input-method enablement, and keyboard selection.
- Added an application-scoped coordinator so the Activity and IME share one Parakeet Q4_K and
  Sotto B epoch-2 engine pair. The Activity no longer tears down shared models on ordinary
  destruction, but it still cancels microphone capture that it started itself.
- The IME never records merely because an editor gains focus. It blocks password, numeric-password,
  web-password, visible-password, no-personalized-learning, and non-editable destinations. It
  invalidates in-flight output when the editor changes and commits only through `InputConnection`.
- Added Parakeet cancel-before-inference, processing cancellation/invalidation, raw/inserted local
  review, guardrail/raw-fallback status, transcript-free timing, and exact-suffix same-editor Undo.
- Host lint, 46 Android unit tests, and debug assembly pass. The APK is 88,045,853 bytes with
  SHA-256 `6652b4a2cffbc0fcef8e1c16534eddf4fd50e379695771abcbdda7732f5dabb7`.
  Pixel enable/select, cross-app commit, microphone/focus lifecycle, fallback, undo, memory,
  thermal, power, and true Stop-to-commit verification remain pending by user agreement.

## 2026-08-19 — FluidVoice local reference preservation

- Inventoried the owner-local FluidVoice application before and after its self-update from 1.6.0
  build 12 to 1.6.9 build 20. Pinned ignored FluidVoice 1.6.0 source and FluidAudio source snapshots
  and traced capture, Core ML Parakeet TDT v2 decoding, filler/dictionary preprocessing, Fluid-1
  prompt/template rendering, thinking stripping, and app formatting/continuous-dictation output.
- Confirmed that Parakeet TDT v2 is the only locally installed STT artifact despite multiple UI and
  registry options. It is an Apple-only 0.6B Core ML package, not the project's 110M Parakeet GGUF.
- Preserved the pre-update 3,427,878,144-byte Fluid-1 Q4_K_M at SHA-256
  `38fafbfaab6504b7ad125523f0b993d52112c3cc7e20543f4929e619022bc7d8` and the 4,945-byte
  Fluid-1 prompt at SHA-256
  `e542001e392bb201fd975c7981bdfbf27833c07d0468b181c24f12db1278037a` in ignored storage.
- Monitored the replacement download and preserved the complete eight-file, 3,583,024,557-byte
  Fluid-1 NVFP4 MLX main model. Every live and copied file matches the v1.6.9 manifest's byte count
  and SHA-256; the 3,550,633,590-byte main weight hash is
  `8211486bf8299f4e59e691c12d90fac1a264fc27a93df646d927d46fc4f25b51`. The signed manifest's
  optional 188,714,557-byte MTP drafter was not downloaded and is not claimed as preserved.
- Preserved the 1.6.9 inference helper plus its Fluid Intelligence and MLX Metal resource bundles.
  Added `scripts/run-fluidvoice-fluid1-baseline.sh`; both the ignored old GGUF and new MLX snapshot
  independently clean the ad hoc text `um send the package on tuesday` to
  `Send the package on Tuesday.` The MLX preserved-helper smoke reported 5,706 ms total, 5,552 ms
  TTFT, 6 generated tokens, and 41.99 tokens/s. No committed evaluation case was used.
- Recorded FluidVoice's exact “Trained on 100K+ dictation data points to polish your words” UI
  sentence as an unverified vendor scale claim. It provides no dataset provenance, pair structure,
  licensing, diversity, split, or quality evidence and does not authorize teacher-label or training
  reuse. The located model-card restrictions and Pixel size/platform mismatch keep both artifacts
  outside Android selection and project training.

## 2026-08-21 — S1-mini v1 BF16/F16/Q4_K_M local performance

- Pinned the official S1-mini by Superwhisper v1 artifacts outside Git: 1,503,300,328-byte BF16
  safetensors, 1,509,347,232-byte F16 GGUF, and 484,219,808-byte Q4_K_M GGUF. Verified exact
  revisions, byte counts, SHA-256 identities, and all 311 reference tensors as BF16.
- Added performance harnesses and nine focused tests that lock the exact publisher system prompt,
  semi-formal/prose/general control line, thinking-off template, greedy decoding, and
  `ceil(1.3 × raw tokens + 32)` cap. The harnesses read only `id` and `raw`, never expected fields.
- Ran 20 personal-v3 raw inputs × 3 measured repeats after warmup. llama.cpp Q4_K_M reached 29.7 ms
  median TTFT, 167.5 ms median total, and 139.25 tok/s native decode; F16 reached 30.7 ms, 308.9 ms,
  and 62.64 tok/s. Q4 was 1.84× faster in median total and used 0.945 GiB less peak server RSS.
- Ran the actual BF16 weights through the publisher's Transformers CPU path: 1,088.8 ms median
  first decoded text and 1,720.9 ms median total, making Q4 10.28× faster across the two documented
  runtimes. BF16 peak process RSS was 1.555 GiB; it is not compared to llama-server's four-slot,
  40,960-token-per-slot allocation.
- BF16 and F16 matched on 60/60 requests. Q4 matched them on 48/60; all three variants were stable
  on 20/20 cases across repeats. Per user scope, no expected-output, semantic-safety, or guardrail
  scoring was performed, so no quantization accuracy claim or deployment selection was made.
- Extended the same unchanged configuration across the 24-case seed and 45-case held-out cleanup
  suites, three repeats each. Pooled 69-case medians are 110.2 ms Q4_K_M, 206.0 ms F16, and
  2,147.6 ms BF16; Q4 is 1.87× faster than F16 in llama.cpp and 19.48× faster than the documented
  BF16 CPU path. Pooled native GGUF decode medians are 141.17 versus 64.85 tok/s.
- The first held-out attempt exposed a harness rejection of a valid filler-only empty output.
  Updated output tokenization to retain zero tokens, added a regression test, and repeated the
  held-out run from a fresh path without changing inference configuration. `heldout-015` returns
  empty deterministically in all three variants and has total latency but no TTFT.
- On the 69-case screen, BF16/F16 match 207/207 requests and Q4 matches 201/207, differing only on
  every repeat of `heldout-006` and `heldout-039`. Across project evals plus personal-v3, all three
  variants are stable on 89/89 cases; BF16/F16 match 267/267 and Q4 matches 249/267. These remain
  raw-agreement observations, not semantic or quantization-accuracy judgments.
- Recorded full aggregate evidence and reproducibility hashes in
  `docs/evaluation/results/2026-08-21-s1-mini-v1-local-performance.md`. Pixel latency, memory,
  thermal, power, runtime compatibility, and BF16 feasibility remain pending because no device was
  attached.

## 2026-08-21 — S1-mini v1 exact-contract Pixel benchmark

- Added a debug-only S1-mini engine on LEAP 0.10.9's Android llama.cpp backend plus transcript-only
  case preparation and a Pixel runner with verified internal staging for Android 17. The shipping
  Sotto engine/default is unchanged.
- Preserved the exact publisher system prompt, semi-formal/prose/general control line, embedded
  Qwen3 template with `enableThinking=false`, temperature-zero greedy decoding, no reasoning-budget
  override, and `ceil(1.3 × raw tokens + 32)` cap. Publisher-tokenizer and llama.cpp raw counts
  match 20/20; Pixel and Mac prompt-token counts match 20/20.
- Ran personal-v3 three times after warmup with Perfetto and again untraced. Outputs are stable on
  20/20 cases. Pixel and Mac Q4 text match on 19/20; the sole difference is equivalent `12` versus
  `twelve` rendering.
- Manual policy review reaches 17/20 acceptable, 2/3 corrections, 1/3 explicit formatting, 11/20
  strict exact, and 54/61 anchors. The failures are one retained superseded recipient plus missing
  bullet and numbered-list realization. Guardrails were not used to qualify raw output.
- The traced run remains thermal status 0 and measures 975.5 ms median TTFT, 1,576 ms median total,
  3,840 ms p90, 1,293,620 KiB peak PSS, and 6.493 J/call at 3.159 W. A matching untraced run starts
  at status 0 but crosses to status 1 after 27/60 calls and reaches 1,665 ms median, 4,294 ms p90,
  and 7,052 ms maximum.
- Decided not to replace Sotto B: S1 gains two acceptable cases but is about 3.3× slower, 2.4× more
  compute-energy-intensive, and 1.9× larger in measured PSS on the current Pixel CPU path.
- Android lint/unit tests/assembly pass. Relevant Python tests pass 16/16. Full script discovery is
  174/175 with only the pre-existing macOS `/var/folders` path-alias assertion failing. Complete
  evidence is `docs/evaluation/results/2026-08-21-s1-mini-v1-pixel.md`.

## 2026-08-21 — S1-mini preferred integration and joined Pixel gate

- At explicit user direction, recalibrated the two personal-v3 list cases against the fixed
  publisher `[Structure: prose]` control. They are configuration conflicts rather than Pixel
  deployment failures, so personal-v3 raw acceptability is 19/20. Case 011's retained superseded
  family-group recipient remains the one genuine raw failure; no guardrail is credited as a pass.
- Extended Mac/Pixel parity across all 69 seed + held-out cleanup cases. Raw transcript token counts
  and publisher output caps match 69/69; raw output text matches 66/69. The three differences are
  bounded decoder/backend surfaces, with no system prompt, control, template, thinking flag,
  temperature, or cap drift. The held-out Pixel runner also asserted its LEAP-derived runtime cap
  against the publisher-tokenizer-prepared cap on 45/45 requests.
- Added the production `S1MiniCleanupEngine` and moved the ordinary coordinator, Activity, UI copy,
  integration identity, and tests from Sotto B to the official S1-mini by Superwhisper Q4_K_M
  artifact. The production path uses the embedded template, exact system/control messages,
  `enableThinking=false`, greedy decoding, and a runtime `ceil(1.3 × raw tokens + 32)` cap; it does
  not run the Sotto-specific filler preprocessor.
- Moved integration models and joined benchmark inputs/results to app-private storage after Android
  17 reproduced shell-pushed external-app-data invisibility. Updated model staging and joined
  runners to copy through fixed readable `/data/local/tmp` files with app-private hash verification.
- Final no-override run `20260820T182349Z-joined-file` completed all 20 personal-v3 audio cases
  through Parakeet → shipping S1. Median STT/cleanup/pipeline totals were 725.0/1,927.5/2,664.5 ms,
  peak PSS was 1,589,901 KiB, and max thermal status was 1. Raw and guarded strict/normalized target
  counts agree at 8/20 and 9/20. One fallback remains, exactly the genuine retained-recipient case.
- The first joined pass exposed four guardrail false rejections. Added regressions and fixed full
  `actually make that` matching at sentence boundaries, trailing list-colon normalization, and
  capitalized ordinal equivalence. The rerun reduced fallback count from five to one while keeping
  raw semantic safety and protected-content checks intact.
- Installed and enabled the voice IME on the Pixel, temporarily selected it, and visually verified
  the permission-denied state in the app's own safe editor. It correctly displays `Microphone setup
  required` and no recording action. Microphone permission was then granted temporarily for the
  user-assisted interactive model-load gate; actual speech commit/cancel/undo/cross-app checks
  remain open.
- Offline Android unit tests, lint, and debug assembly pass. The 88,046,129-byte APK SHA-256 is
  `2f9ca73eaf1b30e454ee381f510c75dc75cbab8692177375659a56a0dd640357`.
- The first user-spoken IME attempt exposed a false lexical rejection: S1 rendered `ten PM` and
  `nine PM` as compact `10pm` and `9pm`. The owner then explicitly changed the repository's
  personal-use policy: accept every sanitized, non-empty generation that did not reach its output
  cap, and rely on manual editing instead of semantic rejection. Replaced the 656-line Android
  semantic guardrail with the two validity checks and reduced its unit suite to four focused tests;
  retained stricter host diagnostics only as historical research evidence.
- Full offline Android unit tests, lint, and debug assembly passed. Installed the 88,046,129-byte
  APK with SHA-256 `56da9d81c66dac13839064b5313c9ed4397a56b03b04bdfa7f2b01ddd7d52683`
  on the connected Pixel. Verified package presence, Local Flow still selected as the IME, and both
  app-private Parakeet/S1-mini model files preserved after the in-place update.

## 2026-08-21 — cache-aware streaming STT and final-only chunked cleanup

- Replaced the ordinary live batch-on-Stop Parakeet artifact with the 129,133,984-byte Realtime EOU
  120M v1 Q4_K GGUF at SHA-256
  `ac9109d0e422bd8aafa899c0f58e1938f4a2846838797a29c04f6a8729033c3c`. Retained the earlier
  offline 110M artifacts and evidence as the quality reference rather than rewriting historical
  benchmarks.
- Extended the pinned `parakeet.cpp` 0.5.0 JNI bridge to ABI-v6 stream begin/feed/finalize/free.
  The live engine now captures project-owned 16 kHz `AudioRecord` chunks, transcribes on a separate
  stateful stream thread, displays newly finalized raw text in the Activity and IME, records EOU
  offsets, stops the microphone synchronously, and flushes only the stream tail after Stop. Cancel
  discards the stream without cleanup.
- Kept cleanup strictly final-only. Added an S1-mini transcript path that counts raw tokens with the
  loaded LEAP tokenizer, packs passes to at most 1,000 tokens, prefers EOU/punctuation/paragraph
  boundaries, uses whitespace only for an overlong unpunctuated span, preserves the exact prompt,
  thinking-off, greedy, and per-input output-cap contract for every pass, and rejoins results in
  source order.
- Added seven focused chunker tests plus STT boundary metadata coverage. The full offline unit,
  lint, and assembly set passes; the pinned ARM64 native libraries rebuild. The final debug APK is
  88,046,129 bytes at SHA-256
  `884ef7413d8a338fa3a30332bfbc94ace4ae9076bc17f3e926f5eb40cd4ed7b0`.
- Downloaded the streaming GGUF into ignored storage and verified its exact hash. Installed the
  debug APK, staged both app-private models with device-side hash checks, and verified the streaming
  model loads and creates a native stream session. No microphone capture was started. At the
  owner's explicit direction, no further phone interaction will occur without first asking in the
  conversation and receiving explicit agreement; the owner will run the live speech pipeline test.
  The installed streaming build is the immediately preceding APK at SHA-256
  `015a408704932b49f1735fa31c8e9a1379fbd2ad9aa1da77555757034a910159`; the final host-only build
  was not installed.
- Reviewed the NVIDIA Realtime EOU and pinned S1-mini v1 model cards. Recorded English-only and
  no-punctuation/capitalization limits, publisher latency/WER context, the unmeasured Realtime EOU
  Q4 quality caveat, S1's raw-ASR/control/thinking/greedy/chunking requirements, valid empty output,
  and both models' redistribution caveats in
  `docs/research/STREAMING_STT_AND_S1_MINI_RUNTIME_CONTRACT_2026-08-21.md`.

## 2026-08-22 — S1-mini Pixel inference optimization plan

- At the owner's direction, defined a three-stage performance program: optimize supported LEAP
  settings with the exact selected S1 Q4_K_M, compare a direct pinned llama.cpp Android runtime
  with the same GGUF, then convert the exact BF16 checkpoint to LiteRT-LM blockwise-32 INT4 for
  Pixel CPU/GPU comparison. Explicitly excluded lower-bit GGUF, channelwise, and block-128 arms.
- Added `docs/research/S1_MINI_PIXEL_INFERENCE_OPTIMIZATION_PLAN_2026-08-22.md` with the fixed
  baseline, publisher-contract and evaluation-isolation invariants, common benchmark gate,
  per-stage tasks, artifact rules, device-consent boundary, selection criteria, and ordered
  tracker. Linked it from the project handoff and synchronized current state, next steps, and the
  durable decision log.
- Completed parallel read-only audits for all three stages. LEAP 0.10.9 exposes CPU threads,
  context, mmap, memory-only cache, and cached-token statistics but not batch/ubatch. The exact
  fixed prompt is 78 tokens, making 2,410 the worst permitted one-pass budget; 3,072 and 2,560 are
  safe candidates while 2,048 is not. Fresh conversations and mmap remain required.
- Chose an isolated benchmark APK/module as the first direct-runtime boundary because LEAP already
  packages generic llama/ggml shared libraries and Parakeet owns a separately isolated ggml. Pin
  llama.cpp `ece963f41` / build 10450 first to match the validated Mac reference; do not float the
  native runtime or package colliding SONAMEs/symbols.
- Routed LiteRT conversion to the Linux RTX A6000 host using the exact 1,503,300,328-byte BF16
  safetensors at SHA-256
  `69d2057077ab4dc738aaaab75d2a8ffa141e3a09fb9d956198cfce46f381131a`. Require inspected
  blockwise-32 metadata because the similarly named channelwise INT4 recipe has a documented
  Qwen3 failure mode. Export context 4,096 first and compare Pixel CPU/GPU only; Tensor G2 NPU is
  not an available assumption.
- Implemented Stage 1's host-only debug controls without changing production defaults. The runner
  accepts only implicit/2/3/4 CPU threads, contexts 4,096/3,072/2,560, and cache-off/four-entry
  32/64 MiB memory-only arms; invalid values fail before model or device work and every arm has a
  configuration-addressed run ID.
- Extended the debug S1 engine with exact prompt+cap context checks, explicit public LEAP options,
  app-cache-scoped memory caching with disk disabled, fresh-conversation isolation, fixed/cached
  prompt-token evidence, the SDK-resolved CPU thread count, and complete additive result metadata.
  Measured jobs are repeat-major with the warmed case rotated last, preventing adjacent identical
  prompts from biasing the four-entry cache arm. Extended the scorer to preserve legacy files,
  reject mixed/incomplete/out-of-matrix configurations, and summarize actual cached prompt tokens.
- Added focused Kotlin and Python coverage. Fourteen relevant Python tests, shell syntax,
  `git diff --check`, and the complete offline Android `lintDebug testDebugUnitTest assembleDebug`
  gate pass. The host-only APK remains 88,046,129 bytes and now has SHA-256
  `bbf420c874d3e4b13ee7a44622c6f2f8d65a02a10f01514dde1e78dd66a348b7`.
- No model conversion, new model artifact, app install, Pixel interaction, or new measurement
  occurred. The unrelated untracked `t.txt` was preserved untouched. The immediate task is the
  owner-approved LEAP Pixel matrix: threads first, context second, cache last.

## 2026-08-22 — S1-mini LEAP Pixel tuning and production selection

- After explicit owner approval, ran the complete thermal-clean Pixel 7 LEAP matrix with the exact
  Q4_K_M: implicit plus explicit 2/3/4 threads, contexts 4,096/3,072/2,560, cache off plus memory-only
  32/64 MiB, an independent winner confirmation, and matched Perfetto control/winner traces. The
  implicit LEAP advisor resolved to one thread on this device; the scorer now accepts and records
  implicit resolution 1–4 while explicit arms remain restricted to 2/3/4.
- Selected explicit two threads, context 2,560, cache off, and mmap on. Matched traced control to
  winner improved median/p90 total 1,694.5/4,178 → 1,391.5/3,371 ms, TTFT 1,122/1,773 →
  723/1,071 ms, peak PSS 1,327,967 → 1,188,541 KiB, native heap 1,295,974,128 →
  1,113,447,856 bytes, and inference compute energy 5.814469 → 5.227675 J/call. Every one of the
  60 paired outputs matched. Process CPU and instantaneous compute power rose, while total compute
  energy fell because the selected arm finished sooner; thermal status 1 was delayed, not removed.
- Rejected three/four threads because small additional median gains cost disproportionate process
  CPU and four threads regressed total p90. Rejected both cache arms because every warmup/measured
  call reported zero cached prompt tokens and latency, CPU, memory, and thermal behavior worsened.
- Retained and excluded one 18-line partial 2,560 run after its Activity lost foreground and Android
  froze the process. The retained partial SHA-256 is
  `a195cfa6a4477422f78a0c920b60c0bbd421835600680b5111efa0aba770b089`; the clean rerun completed
  normally and reproduced the same output.
- Applied the winner to the production `S1MiniCleanupEngine` without changing model bytes, prompt,
  template, decoding, chunking, fresh conversations, mmap, or cache policy. Full evidence and
  artifact hashes: `docs/evaluation/results/2026-08-22-s1-mini-leap-pixel-tuning.md`.
- Final offline `lintDebug testDebugUnitTest assembleDebug` passed: 55 tasks, 1 executed and 54
  up-to-date. Fourteen focused Python tests, Python compilation, shell syntax, and
  `git diff --check` pass. The final 88,046,229-byte host APK SHA-256 is
  `6aaa8adeeeb4a9fdafc398dc36c28e5cb64b4c8917256a16d9953246e943195c`; it was not installed.
  The benchmark-installed preceding APK remains on the Pixel. The unrelated `t.txt` remains
  untouched. Stage 2's isolated pinned llama.cpp same-GGUF module is next.

## 2026-08-22 — Direct llama.cpp Android host-readiness checkpoint

- Added a standalone `:llamacpp-benchmark` application with no LEAP, Moonshine, or Parakeet
  dependency. It is pinned to llama.cpp commit `ece963f41b0b02d7a0d61436ae365762c073a4c8`, tree
  `f59cbdf04f233655507cc98ee9f704b71bfd1403`, build `b10450`, NDK `28.0.13004108`, and CMake
  package/binary `3.31.6` / `3.31.6-g38307f9`.
- Implemented a persistent synchronized JNI model/context owner, exact GGUF-embedded Minja
  rendering with `enable_thinking=false`, exact raw/prompt token evidence, greedy EOG/cap
  generation, fresh KV metadata, authoritative native timings, and complete runtime/system/backend
  metadata. Fixed an integration collision in which native generation initially duplicated the
  host-owned schema field.
- Packaged seven runtime-scored Android ARM CPU variants. Fixed the unextracted-APK loader boundary
  by probing variant sonames through Android's linker and registering only the pinned runtime's
  highest-scoring supported CPU backend. Kept KleidiAI and every GPU backend off in this first arm.
- Added transcript-only preparation, strict result scoring, reproducible source/build evidence,
  and a future Pixel runner with explicit non-evaluation cases, explicit serial, one-device Pixel
  and ARM64 validation, exact hashes, thermal-zero gate, unique artifacts, failure retention, and
  optional matched LEAP/Perfetto scoring. The runner was not executed.
- The complete Release unit/build gate passed with 13 JVM tests. Twenty-one Python tooling tests,
  shell syntax, Python compilation, and `git diff --check` pass. APK integrity, 16 KiB alignment,
  v2 signing, ARM64 packaging, JNI exports, and dynamic dependencies were inspected.
- The final smoke-tested Release APK is 18,701,319 bytes at SHA-256
  `8931caef1a33acc84c9eb173d4d09d986f71ea0f6816716e3a3e93ce05b1bfad`; its stripped JNI DSO is
  131,936 bytes at SHA-256
  `5239a148be50160102d7f67397e81c27808a10f1af19b6cc206cb1756c1f3733`. The ignored build manifest
  SHA-256 is `b0fbfdc3ea95d6c51a25256549325e9b85d3eb6f2bceff4304108021bf9a9f51`.
- No ADB command, app install, Pixel interaction, model conversion, lower-bit quantization, or
  production runtime change occurred. Order 4 remains open for a fresh owner-approved device
  prompt/token/raw-output parity smoke and later CPU comparison. Full host evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-direct-llamacpp-host-readiness.md`.

## 2026-08-22 — Direct llama.cpp Pixel contract smoke

- After explicit owner approval, installed only the isolated benchmark APK on the connected Pixel
  7 and staged the exact 484,219,808-byte Q4_K_M plus three project-authored non-evaluation smoke
  strings in app-private storage. No microphone or production app path was used.
- Retained initial run `20260821T180154Z` after all four inference rows completed but the scorer
  rejected `llama_version=0.1.0-dev`: the scorer had incorrectly conflated llama.cpp's semantic
  version with build `b10450`. Split runtime provenance into semantic version, build number 10450,
  commit `ece963f41`, and target `Android aarch64`; added negative tests and rebuilt.
- Corrected run `20260821T180425Z-s1-direct-c2560-gt2-bt2-b512-u512-mm1-fa0-g0` passed. Every
  warmup/measured row exactly matches the host golden's rendered prompt bytes, raw token IDs, and
  prompt token IDs; the fixed delta is 78 and all output caps match. All rows ended on EOG, none
  capped, and filler-only returned a valid empty output.
- The two independent runs match outputs/token IDs/finish state 4/4. This does not replace a
  multi-repeat stability run. No LEAP/Mac raw-output control was supplied; Unicode cleanup changed
  text and omitted the emoji, so quality/runtime parity is deliberately not claimed.
- Pixel runtime: `libggml-cpu-android_armv8.2_2.so`, 2/2 threads, 512/512 batch, mmap on, flash off,
  CPU only. Thermal remained 0. Smoke-only results: load 996 ms, 507.0 ms median nonblank TTFT,
  601.1 ms median total, 486.0 ms median prompt evaluation, 27.85 decode tok/s median, 1,161,540
  KiB maximum post-call PSS, and 1,108,342,032-byte maximum post-call native heap.
- Corrected raw JSONL SHA-256 is
  `a9c87772dfa911afc9cf6ea2d2c478952c91f56b7cf68c21532d58834c683fb1`; summary SHA-256 is
  `72906c79413da1542b778f7c37290b4b6a215c3f3700658ef8f28a67a3831406`. The actual cap path,
  matched raw-output parity, non-evaluation CPU matrix, power, and sustained thermal remain next.

## 2026-08-22 — Direct llama.cpp Pixel CPU comparison and no-go

- With explicit owner approval, installed only the text-fed benchmark APKs and ran Stage 2 on the
  connected Pixel 7. No test opened `AudioRecord`, requested microphone permission, or used live
  speech. The exact Q4_K_M and publisher contract remained fixed; no smaller quantization ran.
- Added transcript-only runner support for LEAP controls without expected-output scoring, persisted
  direct start thermal status, and added project-authored cap, stress, and user-shaped fixtures.
  The cap path naturally terminated at the publisher limit on 6/6 measured direct calls.
- Matched smoke prompt counts/caps passed 3/3. Direct/host raw output matched 3/3; LEAP differed on
  one Unicode spacing choice. The 12-case stress corpus matched direct/LEAP raw output 36/36 and
  provided bounded thread/internal-token-buffer/flash evidence, but its 126–164-token tail was
  explicitly reclassified as thermal/decode stress after the owner questioned representativeness.
- `n_batch`/`n_ubatch` were confirmed as internal token buffers for one request, not concurrent
  request batching. Every case ran sequentially through one persistent model/context owner. Extra
  generation threads, four batch threads, smaller buffers, and flash attention all failed bounded
  advancement gates; 6/8-thread and 128-token expansions were stopped.
- Added a user-shaped 10-case fixture without copying private-evaluation text or expected outputs.
  Its exact raw-token counts are 18–26 for eight cases and 51/53 for two cases, median 22. In the
  thermal-clean LEAP-first/direct-second matched run, prompt counts, caps, and raw outputs matched
  30/30. Direct median/p90 total was 1,624.0/3,048.0 ms versus LEAP 1,486.0/2,843 ms, median CPU
  was 8.8% higher, and direct reached thermal 1 on calls 28–30 while LEAP stayed at 0. Direct median
  PSS was 1.8% lower. It lost 28/30 paired latency requests.
- Rejected direct llama.cpp CPU as a production replacement and retained tuned LEAP. No Perfetto
  energy arm was advanced because direct failed earlier latency/repeatability/thermal gates. The
  optional Mali build is deferred; exact S1 BF16 blockwise-32 LiteRT-LM conversion is next.
- Full report: `docs/evaluation/results/2026-08-22-s1-mini-direct-llamacpp-pixel.md`. Raw results,
  model bytes, APKs, and manifests remain ignored; the unrelated untracked `t.txt` remains
  untouched.

## 2026-08-22 — Exact S1 BF16 to LiteRT-LM block-32 conversion

- Brought Dante online and verified Linux x86_64, 120 GiB available RAM, 9.3 TB available disk,
  and the RTX A6000 before creating a dedicated workspace. Transferred only the exact S1-mini BF16
  snapshot outside Git; all 12 source files matched revision
  `65f84bcda1d13df582c4a8443c1c5aa53c0c66db`, including the 1,503,300,328-byte weights at SHA-256
  `69d2057077ab4dc738aaaab75d2a8ffa141e3a09fb9d956198cfce46f381131a`.
- Added a Linux-only Python 3.11 uv lock, exact conversion contract, source/recipe canary, guarded
  exporter, FlatBuffer inspector, detached-run launcher, and six fail-closed tests. The final lock
  uses LiteRT Torch 0.9.3, AI Edge Quantizer 0.8.0, and pins `backports-strenum==1.2.8` to avoid the
  unconstrained 1.3.1 release's intentional Python 3.11 exclusion. All 85 packages pass `uv pip
  check`; the full freeze is retained outside Git.
- Converted with `dynamic_wi4b32_afp32`, context 4,096, prefill shapes 128/256/512/1024/1152, float
  activations/KV, external embedder, and retained intermediates. The run completed in 5m46s with
  exit 0. Final bundle: 436,596,864 bytes, SHA-256
  `8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403`.
- Structural inspection passed: main 1,152 plus embedder 2 INT4 tensors, 1,154/1,154 block size 32,
  FLOAT16 scale references, and FLOAT32 KV signatures. Official `litert-lm-peek` confirms bundle
  version 1.6.0, Qwen3 metadata, context 4,096, stop IDs 151643/151645, and the embedded source
  Jinja template.
- No evaluation corpus, expected/model output, GGUF, generic Qwen weights, Pixel, microphone, or
  production runtime was used. LEAP stays production. Full conversion evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-litert-conversion.md`. The unrelated untracked
  `t.txt` remains untouched.

## 2026-08-22 — LiteRT-LM host runtime contract smoke

- Added the isolated `:litertlm-host-smoke` Kotlin/JVM module, pinned LiteRT-LM JVM 0.16.1, and
  three fail-closed unit tests for the exact S1 prompt and input-relative cap. The probe verifies
  the bundle size/hash and refuses generation if the runtime-rendered prompt differs by any byte.
- Loaded the exact artifact on CPU/XNNPACK with two threads and on Apple M2 GPU/Metal WebGPU. Both
  rendered the 404-byte prompt at SHA-256
  `0b546eb4a221629272391b80cbf55e5cf26af3f9ff9df2305923d1362b4c99fb` and returned
  `Hello there` for project-authored `um hello there`.
- Native benchmark counters were disabled in the JVM engine settings. Retained the explicit error
  and wall-clock smoke durations; made no TTFT/token-rate or Pixel-performance claim. The GPU
  sampler alone fell back to the linked C implementation because the optional WebGPU sampler DSO
  was absent.
- Dante, Pixel, microphone, committed evaluation corpora, expected outputs, private transcripts,
  and production LEAP were untouched during the host smoke. Next is an isolated Android probe and
  matched Pixel CPU/GPU evidence.

## 2026-08-22 — LiteRT-LM Pixel English representative no-go

- Added an isolated `:litertlm-android-benchmark` app pinned to LiteRT-LM Android 0.16.1. The
  ARM64 release APK declares no permissions, stages the hash-verified model app-privately, verifies
  exact rendered prompt bytes, sends one request at a time with fresh conversations, and captures
  callback TTFT because native benchmark counters are disabled.
- At the owner's direction, removed the Japanese/Unicode stress row from the active LiteRT fixture
  and excluded its prior smoke result from selection. The final comparison uses only the frozen
  ten-case English user-shaped fixture (median 22 raw tokens).
- CPU and GPU representative runs both stayed thermal 0. Against LEAP repeat 0 on the same fixture,
  CPU median total/TTFT/PSS regressed 448.2%/457.3%/42.4%; GPU regressed
  91.0%/5.8%/142.9%. Each lost 10/10 paired total-latency calls.
- Logcat proves GPU loaded OpenCL and delegated every main prefill/decode node through `LITERT_CL`;
  the external embedder and unavailable optional sampler remained CPU. The result is not silent
  CPU fallback.
- Exact output parity was 1/10; most differences were missing final periods. GPU preserved the
  English reminder, while CPU added an awkward comma in `water the balcony, herbs`. No thinking
  markup, loop, crash, or thermal event occurred.
- Rejected LiteRT CPU/GPU and retained tuned LEAP. No sustained, power, smaller-context conversion,
  or production integration arm is advanced. The isolated package remains installed pending owner
  approval to remove roughly 1.0 GiB of app-private model/cache evidence.
- Full report: `docs/evaluation/results/2026-08-22-s1-mini-litert-pixel.md`.
- With explicit owner approval, uninstalled only `dev.localflow.litertlmbenchmark` after the report
  was retained. Free `/data` space increased from 2,152,216 KiB to 3,214,612 KiB, recovering
  1,062,396 KiB; `dev.localflow.dictation` was verified still installed.

## 2026-08-22 — Daily-driver QoL slice 1

- Added bounded, independently scrollable raw-transcript surfaces to the Activity and voice IME.
  Live partials follow the tail by default and retain manual position once the owner scrolls up.
- Replaced the IME's discarded one-shot undo with a five-entry in-memory same-editor history. Each
  deletion still requires an exact immediate suffix; editor changes or mismatches clear history
  without deleting text.
- Added cursor-aware insertion spacing. Consecutive dictations receive exactly one needed boundary
  space, while empty fields, existing whitespace/newlines, and punctuation avoid duplicates. Any
  added separator is part of the undo transaction.
- Added the ordered QoL plan, including clearer states and a real, non-persisted microphone
  waveform as the next visual slice. Rambler/Gboard informed interaction principles only; no asset,
  prompt, transcript, or model behavior was copied.
- Built and owner-authorized-installed the 88,046,641-byte debug APK at SHA-256
  `cd2227b372a2f4028a6ae725ad28d566c130f7424b4241e3057f2290cb57035d`. Installation preserved
  all three app-private GGUFs. Local Flow remains enabled; Gboard was current default at the
  post-install check, so owner selection and live voice verification remain open.
- Handoff clarification: scrolling the transcript pauses only automatic tail-follow; capture and
  STT continue, and tail-follow resumes at the bottom. The owner requested a stronger visible
  listening indicator, now recorded as the first task for the next session.

## 2026-08-22 — Daily-driver QoL slice 2

- Added tap-to-copy to the Activity and IME transcript surfaces. The copied payload is only the
  current raw transcript (or the last inserted text when no raw IME transcript remains); blank
  placeholders and `Raw`/`Inserted` presentation labels are never copied. Android's normal
  click-cancellation after a touch-slop drag continues to distinguish scrolling from a tap.
- Reworked the keyboard into a calmer on-device hierarchy: compact Local Flow/privacy header,
  rounded lifecycle card, persistent state dot, concise supporting copy, bounded transcript card,
  dominant Start/Stop action, and reachable Cancel/Undo/keyboard controls. Recording uses the red
  action/state treatment; processing/loading is amber and ready is green.
- Added a real microphone waveform shared by Activity and IME. The capture thread computes a
  bounded RMS/peak display value at no more than 20 Hz, posts only that scalar to the UI, retains no
  PCM, logs/persists nothing, and resets the bounded 28-bar view as soon as capture stops. Added
  pure host tests for silence, monotonic loudness, and out-of-range bounding.
- `testDebugUnitTest`, `lintDebug`, and `assembleDebug` pass. Installed the final 88,047,120-byte
  APK at SHA-256 `4c6688e55d5f1c024da125c55ec6c387609fd288e5103bb02f5aed0b41b255b4`
  over the existing Pixel package; app-private models and IME enablement were preserved. Static
  Pixel screenshots verified both refreshed surfaces. Owner-run live waveform, clipboard,
  scroll-versus-tap, TalkBack, and recording/processing state checks remain open.
- The unrelated untracked `t.txt` was left untouched.

## 2026-08-22 — QoL palette and waveform refinement

- Incorporated owner feedback from live use: the initial saturated blue/red controls were too
  dominant, the waveform columns were too bulky, and idle room noise produced visible movement.
  Replaced the palette with muted periwinkle/dusty-rose tones and reduced the Activity/IME waveform
  heights to 36/30 dp.
- Replaced the direct RMS/peak presentation with a deliberately low-detail activity meter. It runs
  an 80 Hz first-order display-only high-pass, a firm -32 dB noise gate, slow attack/release,
  five-step quantization, and a 24-bar 1.6 dp rendering at no more than 20 Hz. The filtering does
  not mutate Parakeet's audio, retain PCM, log levels, or persist history.
- Clarified the recording subtitle to `Microphone active · scrolling won’t pause listening`.
  Owner observation that words and Listening remain live while scrolling matches the established
  presentation-only scroll contract; recording must not pause merely because the transcript is
  being reviewed.
- Expanded host tests to cover silence, gated quiet input, smoothed voice activity, steady-DC
  rejection, and state reset. `testDebugUnitTest`, `lintDebug`, and `assembleDebug` pass. Installed
  the 88,047,120-byte APK at SHA-256
  `8fb78d6c686ba5088285be787b202d840e712274404f0dda4e041e9bbd28d115` over the existing Pixel
  package and statically verified the muted Activity palette and slimmer idle waveform.
- The unrelated untracked `t.txt` remains untouched.

## 2026-08-22 — Primary contrast, waveform density, and QoL roadmap

- Fixed owner-reported dark text over blue/red primary actions by explicitly applying light text to
  the Activity dictation button and IME main action in both XML and every runtime state render. This
  covers Start, Stop, Load, loading, and processing instead of relying on Android's state theme.
- Increased the filtered waveform from 24 to 36 strokes while reducing each stroke from 1.6 to
  1.35 dp. The -32 dB gate, high-pass, slow envelope, five-level quantization, 20 Hz ceiling,
  non-persistence, and separation from Parakeet audio remain unchanged.
- Expanded the durable QoL roadmap with concrete recovery, raw-versus-inserted review, fail-closed
  Replace/Redo evaluation, restrained haptics, recording timer and real processing phases,
  TalkBack/dynamic-type/reduced-motion checks, compact/landscape layout, actionable setup/model
  health, and measured warm/unload policy.
- `testDebugUnitTest`, `lintDebug`, and `assembleDebug` pass. Installed the 88,047,120-byte APK at
  SHA-256 `8e102a5c27b2ba39ceaad89f8b1f5bfcdcdf888e0401e2ad6fe6f1858a52b708`
  over the Pixel package and statically verified light blue-button text plus the denser idle
  waveform. Live red Stop-state contrast remains an owner check; no microphone was opened for
  static QA.
- The unrelated untracked `t.txt` remains untouched.
