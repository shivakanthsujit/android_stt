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
  inference code plus focused unit tests. GPU smoke tests and Experiment A remain pending until the
  repository checkpoint is fully tested and committed.
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
