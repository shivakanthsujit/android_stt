# Current state

Last updated: 2026-08-18

## Repository

- Branch: `main`
- Remote: `https://github.com/shivakanthsujit/android_stt.git`
- Last verified milestone: Milestone 3 cross-family cleanup screen (see current `git log`)
- Workspace: `/Users/ssujit/Documents/projects/android_stt`
- Current phase: Phase A ordinary Android benchmark app
- Completed milestones: 0 (toolchain), 1 (Moonshine smoke test), 2 (cleanup harness and Liquid
  no-go evaluation), 3 (cross-family generic-model quality screen)
- Active milestone: 4 (task-specific cleanup model qualification/training)
- Deferred milestone: 5 (formal STT-only evaluation)

## Working functionality

- Kotlin/View-based Android benchmark Activity on a physical Pixel 7.
- Moonshine Voice `0.1.2`, English Small Streaming architecture `4`.
- Model download, persistent no-backup cache, progress display, and offline cache reuse.
- Raw provisional/final transcript display and monotonic latency metrics.
- ARM64-only debug APK; current cleanup-harness APK is about 61 MiB.
- Microphone permission is requested from the Activity.
- The model stays loaded between utterances.
- Android `AudioRecord` is created and started only after **Start Dictation**.
- **Stop Dictation** synchronously stops active microphone capture before final processing.
- Liquid LEAP `0.10.9` cleanup-only benchmark with model download progress, persistent cache reuse,
  load/unload, conservative guardrails, and monotonic TTFT/total-generation metrics.
- Editable direct-text cleanup UI plus a 24-case, multi-prompt batch runner that exports JSONL for
  deterministic host-side scoring without involving the microphone or Moonshine.
- LFM2.5-230M, 350M, and 1.2B-Instruct `Q4_K_M` were exercised on-device; their raw static-corpus
  results and summaries are preserved under `docs/evaluation/`. All three are cleanup no-go results.
- A deterministic baseline plus Granite 350M, Qwen3 0.6B, Gemma 270M, Qwen3.5 0.8B, and Gemma 1B
  were screened on a fresh 45-case held-out set through llama.cpp on the host. None passed the
  semantic safety/self-correction gate, so no new runtime or model was added to the Android app.
- The runtime-neutral runner now applies a parity-tested port of the Android lexical/intent
  guardrails and emits scorer-compatible JSONL with raw output, guarded selection, TTFT, and total
  latency.
- Cleanup is the current product bottleneck. The working offline Moonshine capture/transcription
  path is the provisional speech input while task-specific cleanup is pursued. This is a priority
  decision, not a claim that formal STT comparison is complete.

## Physical device

- Google Pixel 7 (`panther`), ARM64, adb serial `33040DLH20004E`.
- Cached Moonshine model remains installed on the device.
- Pixel `stay_on_while_plugged_in` was restored to its original `0`; airplane mode is disabled.
- The cleanup harness and all three Liquid evaluations are committed in `8dce7ab`.

## Known issues and observations

- Moonshine Small Streaming handled a 59.6-second utterance without ending microphone capture, but
  it produced overly short line segments and several recognition errors.
- Completed Moonshine lines are currently displayed on separate lines. This makes segmentation
  more visually prominent; the future cleanup stage should receive the whole transcript.
- Automatic end-of-speech is deliberately not implemented. V1 uses explicit Start/Stop.
- Android's built-in on-device `SpeechRecognizer` is a planned A/B branch after the joined pipeline.
- Liquid LEAP is governed by its own Terms of Use; its model weights have separate LFM licensing.
- LFM2.5-230M passed Android/offline runtime checks but failed cleanup quality: only 3/24 strict
  matches for the safest prompt. It remains a latency baseline, not the selected default.
- LFM2.5-350M performed worse (1/24 exact, 77.0% preservation, meaning-changing negation failure)
  and is rejected.
- LFM2.5-1.2B-Instruct reached 13/24 exact at best but still changed meaning, answered content,
  dropped technical details, and failed all self-corrections. It is rejected for automatic cleanup.
- The cleanup harness now has stricter lexical/intent fallback checks, but a safety fallback cannot
  compensate for inadequate cleanup quality. Do not feed cleanup output into STT automatically.
- Gemma 3 1B was the closest generic candidate at 32/45 raw exact and 94.1% anchor preservation,
  but it retained a superseded command and obeyed two embedded instructions. It is rejected.
- Current host timings are Apple M2 screening measurements, not Pixel 7 results. Pixel integration
  was intentionally skipped because no candidate passed quality first.
- The original 24 cases are a development/regression set. The 45-case held-out set has now informed
  guardrail fixes, so it is also a regression set rather than a future blind test. Training work
  must create leakage-isolated train/dev data and a new untouched blind v2 evaluation set.
- The first specialized quality probe, VoiceInk Qwen3.5-2B Q4_K_M, is complete and rejected. It
  reached 38/69 raw exact but only 2/10 explicit corrections, retained six superseded edits,
  changed meaning/facts three times, and answered one dictated instruction. Its fine-tune license
  is also undeclared.
- Task-specific data work has a versioned JSONL contract and standard-library validator covering
  provenance/review policy, frozen-corpus overlap, split leakage, anchors, lexical additions, and
  deterministic SHA-256 manifests. No training rows have been generated yet.
- Public candidate sources are now pinned for audit: Sotto transcript cleanup at
  `183cc8fd58532f13fa192980185214de1bcd5acc`, Disfl-QA at
  `1f0c16171c77b3d3408be92c485f11b8998a9189`, and Nyra Disfluency Speech English at
  `723e9e69bfbdc8214a9b8ce8815985e90afcbaa3`. None has been imported or approved yet.
- `TRAINING_MACHINE_HANDOFF.md` is the self-contained entry point for the RTX A6000 session. It
  authorizes building the missing data/training/evaluation pipeline and running the pilot there,
  subject to Gate A, monitoring, artifact, review, and blind-isolation rules.
- RTX Phase 0 hardware/storage checks pass on host `dante`: the user verified NVIDIA-SMI
  550.144.03, CUDA compatibility 12.4, an idle 49,140 MiB RTX A6000, and about 9.6 TiB free under
  the writable `/data/rise/android_stt/` artifact root. The exact CUDA 12.4 environment lock is
  synchronized under `/data/rise/android_stt/env`; the exact package check and BF16 CUDA matmul
  pass. See
  `docs/training/2026-08-17-RTX-A6000-PHASE0.md`.
- The first reproducible data-pipeline checkpoint now contains pinned-source configuration, a
  revision-verifying/hash-recording fetcher, conservative Sotto/Disfl-QA/Nyra import and
  quarantine logic, pre-split family/near-duplicate grouping, exact pilot quota checks, and unit
  tests. The 14-file, 1.1 GiB pinned source snapshot passes identity/byte/SHA verification; the
  real importer dry run passes, no public row is approved, and the durable `/data` import remains
  to be created.
- A text-free profile of all 147,142 mappable pinned rows records 63,990 candidates, 81,325
  quarantined rows, and 1,827 rejected rows without consuming source-native holdouts. Even as an
  optimistic upper bound, public data is short by 326 adversarial-primary rows, 53 paragraph rows,
  402 adversarial cross-cutting rows, and 524 Unicode/multilingual rows for the 5,000/500 pilot.
  The sanitized profile is `docs/evaluation/results/2026-08-17-cleanup-source-profile.json`.
- A deterministic supplemental generator now produces 2,800 pending, non-blind candidates outside
  Git: 720 adversarial-primary, 400 paragraph-primary, and 1,576 Unicode/multilingual cross-cutting
  rows, plus edit-bearing adversarial variants. Its dry run passes the V2 validator for all 2,800
  rows. The quota builder reserves rare cross-cutting supply and satisfies minima during selection;
  no generated or public row is auto-approved.
- Dataset/annotation contract V2 treats explicit bullet/numbered-list, paragraph-break, and
  spoken-punctuation directives as reviewed editor controls while preserving arbitrary commands
  as text. Following product clarification, the 5,000/500 pilot also has dedicated 500/50 strata
  for conservative grammar repair and context-supported ASR repair, retains mixed/crutch,
  high-stakes, protected, and declared lexical-addition candidates for human review, and still
  rejects invented formatting items automatically.
- Do not start LoRA/QLoRA training on this Mac; use it for Android work, authoring/validation, local
  inference screens, and result analysis only.
- The immediate experimental direction is now four direct-source adapters: Sotto, Disfl-QA, Nyra,
  and all three combined. Hold Qwen3-0.6B and a one-epoch LoRA recipe fixed so the experiment
  measures the dataset effect; train Sotto first and evaluate its raw output before launching the
  other three. This fast evidence track is documented in
  `docs/training/DIRECT_SOURCE_EXPERIMENT_PLAN.md` and does not qualify an adapter for deployment.
- A separate direct-source trainer/config now supports Sotto, Disfl-QA, Nyra, and combined
  publisher splits without weakening the reviewed-pilot Gate A path. It verifies source
  revisions/bytes/hashes, nonempty-pair counts, frozen-corpus isolation, exact optimizer steps,
  assistant-only masking, and the no-truncation 2,112-token contract.
- The exact Qwen3-0.6B snapshot is cached and the 32-row/two-step Sotto smoke completed at run
  `direct-sotto-qwen3-0.6b-smoke2-seed23-20260817T121729Z`: step 2, train loss 1.4543, no
  truncation, 10,092,544 trainable LoRA parameters, checkpoint plus final adapter present. Two
  earlier mechanical attempts failed before any optimizer step and led to committed Transformers
  5.14 compatibility fixes for mapped chat-template output and `TrainingArguments`.
- The user explicitly waived the pre-run push gate for local commit `53a5551`. The first managed
  full-run launch exposed a monitor/startup race and exited before run state or optimizer work;
  its directory is preserved. A second clean launch reached the full-corpus no-truncation audit
  and failed before model load because row 75 formats to 1,294 tokens under the fixed 1,024-token
  limit. No optimizer step ran.
- The completed text-free audit found 775/135,503 Sotto train rows and 46/6,921 publisher-validation
  rows above 1,024 tokens, with maxima of 1,838 and 2,050 respectively. The evidence is
  `docs/evaluation/results/2026-08-17-direct-sotto-token-length-audit.json`. Do not truncate, drop,
  or change the fixed sequence policy without an explicit recipe decision and a new longest-row
  memory smoke.
- The authorized 2,112-token limit is within Qwen3-0.6B's pinned 40,960-token context, but the exact
  longest train row OOMs at the original microbatch 8 without checkpointing. Two-step worst-case
  diagnostics pass with either microbatch 4 / accumulation 8 (31.87 GB peak allocated, 13.84 s)
  or microbatch 8 / accumulation 4 plus gradient checkpointing (29.09 GB, 17.76 s); validation
  batch 8 passes at the 2,050-token maximum. The authorized recipe is 2,112 tokens plus microbatch
  4 / accumulation 8, preserving effective batch 32 and all expected step counts. Evidence is
  `docs/evaluation/results/2026-08-17-direct-sotto-2112-memory-diagnostic.json`.
- The full 135,503-row Sotto run completed successfully at
  `/data/rise/android_stt/runs/direct-sotto-qwen3-0.6b-e1-seed23-20260817T124158Z` from training
  commit `c556709`. It passed complete no-truncation audits (train maximum 1,838; validation
  maximum 2,050), reached 4,235/4,235 optimizer steps, and exited zero. Train loss was 0.09389;
  validation loss improved from 0.09679 at step 1,059 to 0.07938 at step 4,235. Runtime was
  7,662.1 seconds. Resumable checkpoints are under `checkpoint-1059`, `checkpoint-2118`,
  `checkpoint-3177`, and `checkpoint-4235`; the final adapter is under `final-adapter`, and the
  root `trainer_state.json` and `status.json` record the terminal state.
- The final 40,422,168-byte adapter has SHA-256
  `22736a4d4aff8b5788386a80d643296874c3b54dd980404e7196a5665023fa2b` and exactly matches the
  step-4,235 checkpoint adapter. Its config SHA-256 is
  `f08b77c9295ebedfee2c0230f7277c7ec5d17f33ea54d040c19440b19d71249d`.
- Retired diagnostics are complete: 15/24 seed exact, 36/45 heldout exact, 51/69 combined, 153/163
  anchors, 7/10 self-corrections, and 15/17 must-not-answer cases. Agent review of all 18 non-exact
  outputs found eight substantive raw-policy failures, including intent change, answered content,
  protected entity/name/identifier changes, and substantive deletion. Raw semantic safety fails;
  this adapter is not a deployment candidate and guardrails cannot convert it into one.
- Full Sotto publisher validation is complete: 4,751/6,921 raw exact (68.65%), zero empty outputs,
  48 output-cap hits, and 3,098 guardrail flags. Generation exited zero with exactly 6,921 result
  rows. Mixed-concurrency A6000 latency was 91.5 ms median TTFT and 583.4 ms median total; do not
  treat it as a clean standalone benchmark.
- A separate locked vLLM 0.8.5 / Python 3.10 / Torch 2.6.0+cu124 environment now serves the pinned
  Qwen3-0.6B base and completed Sotto LoRA on the A6000. The deterministic multi-client runner
  shards by case ID, resumes only validated prefixes, records raw and parallel guardrail evidence,
  refuses blind paths, and validates a source-order merge. Complete publisher sweeps took 91, 87,
  83, and 84 seconds at 16, 32, 64, and 128 clients; 64 is the measured default for this workload.
  The server remains available on `127.0.0.1:8000`, and all raw results remain under `/data`.
- Cross-dataset generation is complete. The Sotto adapter reached 472/1,000 exact on Disfl-QA dev
  with 732 guardrail flags and 32/250 exact on Nyra validation with 76 guardrail flags. Neither
  result justifies skipping standalone source training.
- Final sanitized training, artifact, publisher, cross-dataset, and retired-diagnostic evidence is
  in `docs/evaluation/results/2026-08-18-direct-sotto-qwen3-evaluation.json`; the earlier interim
  snapshot is retained for provenance. Raw publisher pairs/results and model artifacts remain
  under `/data`, outside Git.
- Sotto has no located formal paper; the publisher's evolving Hugging Face model card is its
  stated training research document. The closest detailed reference uses LFM2.5-350M full SFT for
  three epochs at 3e-5, effective batch 8, AdamW beta2 0.95, cosine/50-step warmup, packed 4,096
  context, BF16+TF32, and seed 42, followed by GRPO/refinement stages. This is follow-up evidence,
  not a directly transferable Qwen LoRA recipe. The immutable-source comparison is
  `docs/research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md`.
- The current base-model reassessment keeps Qwen3-0.6B plus BF16 rank-16 LoRA for the controlled
  source comparison, then prioritizes Qwen3.5-0.8B as the stronger-base follow-up. Gemma 3 1B is
  the quality alternative and LFM2.5-350M is the deployment-speed wildcard; Gemma 4 E2B is outside
  the sub-1B experiment.

## Toolchain

- Android Studio Quail 3 / 2026.1.3 Patch 1
- Android Gradle Plugin 8.13.2
- Gradle 8.13
- Kotlin 2.3.20
- JDK 17
- compileSdk / targetSdk 36; minSdk 31
- Android Platform-Tools 37.0.1

## Resume checklist

1. Read root `AGENTS.md`, this file, and `NEXT_STEPS.md`.
2. Run `git status --short` and preserve any uncommitted work.
3. On the RTX A6000 machine, read `TRAINING_MACHINE_HANDOFF.md` completely and follow its Phase 0
   preflight. Do not run the Mac/Pixel steps below.
4. On the Mac with the Pixel attached, run `./scripts/check-toolchain.sh`, then
   `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`.
5. Continue active Milestone 4 in `NEXT_STEPS.md`. On the RTX machine, preserve the completed
   Sotto run and launch the fixed-recipe standalone Disfl-QA experiment, followed by Nyra. Compare
   the three source adapters before deciding on combined training. Preserve the stricter
   reviewed-pilot path for later qualification work. Use the locked vLLM server plus 64 sharded
   clients for subsequent large evaluations unless a changed model/workload is re-benchmarked.
