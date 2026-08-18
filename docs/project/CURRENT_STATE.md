# Current state

Last updated: 2026-08-18

## Repository

- Branch: `main`
- Remote: `https://github.com/shivakanthsujit/android_stt.git`
- Last verified milestone: joined Parakeet/Sotto integration test build (see integration evidence)
- Workspace: `/Users/ssujit/Documents/projects/android_stt`
- Current phase: Phase A ordinary Android benchmark app
- Completed milestones: 0 (toolchain), 1 (Moonshine smoke test), 2 (cleanup harness and Liquid
  no-go evaluation), 3 (cross-family generic-model quality screen)
- Active milestone: 4 (task-specific cleanup model qualification/training)
- Partially completed milestone: 5 (standard-corpus STT probe plus batch-on-Stop microphone
  integration; dictation/streaming qualification remains)
- Diagnostic milestone: joined integration path is implemented for testing, without relaxing the
  independent STT or cleanup deployment gates

## Working functionality

- Kotlin/View-based joined integration Activity on a physical Pixel 7.
- Moonshine Voice `0.1.2`, English Small Streaming architecture `4`.
- Model download, persistent no-backup cache, progress display, and offline cache reuse.
- Raw provisional/final transcript display and monotonic latency metrics.
- Debug-only, microphone-free STT benchmark Activity that accepts checksum-verified 16 kHz PCM16
  WAVs over ADB and records raw hypotheses, WER inputs, repeat latency, process CPU time, PSS,
  native heap, and thermal status.
- Debug-only joined benchmark Activity that accepts a generated corpus or one host-canonicalized
  WAV/MP3, loads Parakeet and Sotto once, never opens the microphone, and records raw STT, exact
  model input/output, guarded output, fallback reason, and per-stage/joined latency.
- Mac-local, locked Qwen3-TTS/MLX-Audio fixture pipeline that converts literal text or bounded
  regression suites into resumable, hash-addressed 24 kHz masters and Pixel-compatible 16 kHz
  mono PCM16 WAV corpora without putting model weights or generated audio in Git.
- Pinned Android ARM64 `parakeet.cpp` 0.5.0 JNI/C API integration for file-fed and live-captured
  TDT/CTC 110M Q4_K GGUF inference. Its ggml dependency is statically isolated from
  Moonshine/LEAP's packaged ggml.
- Optional Perfetto power mode that attributes Pixel CPU/GPU/memory rail energy to measured model
  calls using app trace slices.
- ARM64-only joined debug APK; current verified APK is 88,044,777 bytes with SHA-256
  `22719570e435a379ecbaa2d91e823fb0b5b846f93a761d9021f86524d5b40ae3`.
- Microphone permission is requested from the Activity.
- The model stays loaded between utterances.
- Android `AudioRecord` is created and started only after **Start Dictation**.
- **Stop Dictation** synchronously stops active microphone capture before final processing.
- The selected offline Parakeet model transcribes the complete capture after Stop; it does not
  expose partial/streaming hypotheses.
- Liquid LEAP `0.10.9` cleanup-only benchmark with model download progress, persistent cache reuse,
  load/unload, conservative guardrails, and monotonic TTFT/total-generation metrics.
- Editable direct-text cleanup UI plus a 24-case, multi-prompt batch runner that exports JSONL for
  deterministic host-side scoring without involving the microphone or Moonshine.
- Sideloaded LEAP runtime for the pinned public Sotto LFM2.5-350M checkpoint, reproducibly converted
  to a 229,310,304-byte Q4_K_M GGUF. The native Sotto prompt/parser and decoder settings are fixed.
- Joined Parakeet → Sotto execution after every non-empty final transcript. The UI preserves raw
  STT, complete raw model output, guarded output, STT tail, cleanup timing, and end-to-end tail.
- The active synthetic product regression is now the 20-case personal-conversation v3 suite:
  messages, journal entries, lists, ordinary names/numbers, uncertainty, repetition, explicit
  formatting, natural corrections, and four 3–5 sentence latency cases. Phone-number dictation and
  technical v1 cases are historical/excluded from the active workload.
- A deterministic pre-model pass removes only standalone `um`, `uh`, and `erm`. Result metadata and
  cleanup JSON preserve the original transcript, exact model input, removed-token list, and whether
  Sotto ran; the UI exposes the model input and removal count. Ambiguous discourse words,
  uncertainty markers, acronyms, likely names, quotes, paths, identifiers, hyphenated words, and
  paragraph breaks are excluded from removal.
- Android and host guardrails no longer protect lexical surfaces more strictly than meaning where
  deterministic equivalence exists. They accept bounded removal of sentence-initial discourse,
  explicit `sorry`/`actually make that` corrections, equivalent word→digit/time rendering, and
  consumed list/paragraph directives; changed names, values, negation, uncertainty, unsupported
  additions, and answered content still fail closed.
- LFM2.5-230M, 350M, and 1.2B-Instruct `Q4_K_M` were exercised on-device; their raw static-corpus
  results and summaries are preserved under `docs/evaluation/`. All three are cleanup no-go results.
- A deterministic baseline plus Granite 350M, Qwen3 0.6B, Gemma 270M, Qwen3.5 0.8B, and Gemma 1B
  were screened on a fresh 45-case held-out set through llama.cpp on the host. None passed the
  semantic safety/self-correction gate, so no new runtime or model was added to the Android app.
- The runtime-neutral runner now applies a parity-tested port of the Android lexical/intent
  guardrails and emits scorer-compatible JSONL with raw output, guarded selection, TTFT, and total
  latency.
- Cleanup is still the product bottleneck. Public Sotto is an integration-only placeholder while
  correction-repair training proceeds; the joined build is not a deployment qualification claim.

## Physical device

- Google Pixel 7 (`panther`), ARM64, adb serial `33040DLH20004E`.
- Cached Moonshine model remains installed on the device.
- F16 and Q4_K Parakeet GGUFs plus the generated LibriSpeech probe remain in ignored local/device
  evaluation storage; they are not committed app assets.
- The selected Parakeet Q4_K and converted Sotto Q4_K_M artifacts are staged in app-scoped external
  storage with their exact hashes verified on the device. Both load successfully in the installed
  integration APK.
- On-device joined smoke: Parakeet model load 270 ms; 22.091-second microphone capture; 1,568 ms
  Stop-to-STT final; Sotto total 456 ms; 2,029 ms Stop-to-cleanup. Sotto deleted protected negation,
  and the guardrail correctly returned the raw STT text. This is useful integration evidence and a
  direct reminder that the placeholder cleanup model remains unqualified.
- Historical technical-v1 acoustic synthetic run under the superseded guardrail: 4/20 strict and
  11/20 normalized STT exact; 934 ms median
  Stop-to-STT final; 565 ms median cleanup total; 1,466 ms median Stop-to-cleanup. Sotto fell back
  on 15/20 cases. Case 014 changed a dictated technical command and passed the guardrail; case 011
  correctly resolved a beta-to-canary correction but was rejected by the guardrail. The 35-second
  long case completed at 3,350 ms STT tail and 5,484 ms end to end. Thermal status remained 0.
- Personal-v3 direct-file joined run: 20/20 completed; Parakeet reached 8/20 strict and 15/20
  normalized exact against spoken references. Public Sotto/guarded output reached 8/20 strict and
  10/20 normalized exact against intended cleanup with three fallbacks, all on retained explicit
  corrections. Median STT/cleanup/joined times were 625/645/1,261 ms. The four long-form cases ran
  from 2,543 to 4,746 ms joined for 14.88–25.84 seconds of audio. This fast regression does not test
  microphone acoustics or lifecycle.
- Pixel `stay_on_while_plugged_in` was restored to its original `0`; airplane mode is disabled.
- The cleanup harness and all three Liquid evaluations are committed in `8dce7ab`.

## Known issues and observations

- Moonshine Small Streaming handled a 59.6-second utterance without ending microphone capture, but
  it produced overly short line segments and several recognition errors.
- On the clean 24-clip read-speech probe, Moonshine scored 3.54% WER, Parakeet F16 1.69%, and
  Parakeet Q4_K 1.85%. Q4_K was the fastest untraced path (0.72 s median, 1.80 s p90), with zero
  output instability across repeats.
- The pinned Qwen3-TTS 1.7B CustomVoice 8-bit pipeline generated 45 retired held-out-v1 cleanup
  regression clips plus 20 project-authored dictation stress clips with the built-in Ryan voice.
  The 65 canonical files total 401.28 seconds and have manifest SHA-256
  `10a06cdece044e4c0383eb5719461fdba3b74cb6638efd9d5c238cf7728964cf`; all WAV/header/hash,
  silence, clipping, offline-cache, and resume checks pass. Audio remains ignored under
  `.cache/stt-eval/`. This clean single-speaker synthetic corpus validates plumbing and lexical
  regressions, not real dictation quality. The 20 project-authored cases have now completed one
  uncontrolled acoustic Pixel integration run; listening review and controlled/human-speaker
  qualification remain pending. Full evidence is in
  `docs/evaluation/results/2026-08-18-parakeet-sotto-tts-acoustic-integration.md`.
- Q4_K's only normalized difference from F16 was `Hidalgo` → `Hadalgo`. In matched power runs it
  used 23.8% less process CPU time, 23.3% less inference compute-rail energy, 8.6% less average
  compute power, and 25.5% less peak PSS. Q4_K is the provisional deployment candidate; F16 is the
  quality reference.
- The current Parakeet build is CPU-only. GPU rail energy was below 0.1% of compute energy. Live
  microphone capture is integrated, but it is batch-on-Stop rather than streaming; a protected-
  token dictation corpus and streaming responsiveness remain required for product qualification.
- An initial F16 latency run was contaminated by active phone use and excluded. Clean runs start
  with no competing app and thermal status 0. Perfetto affects wall timing, so untraced runs select
  latency while traced runs supply CPU/energy evidence.
- The older Moonshine path displayed completed lines separately. The joined Parakeet path supplies
  its whole final transcript to cleanup automatically.
- Automatic end-of-speech is deliberately not implemented. V1 uses explicit Start/Stop.
- Android's built-in on-device `SpeechRecognizer` is a planned A/B branch after the joined pipeline.
- Liquid LEAP is governed by its own Terms of Use; its model weights have separate LFM licensing.
- LFM2.5-230M passed Android/offline runtime checks but failed cleanup quality: only 3/24 strict
  matches for the safest prompt. It remains a latency baseline, not the selected default.
- LFM2.5-350M performed worse (1/24 exact, 77.0% preservation, meaning-changing negation failure)
  and is rejected.
- LFM2.5-1.2B-Instruct reached 13/24 exact at best but still changed meaning, answered content,
  dropped technical details, and failed all self-corrections. It is rejected for automatic cleanup.
- The cleanup harness has stricter lexical/intent fallback checks, but a safety fallback cannot
  compensate for inadequate raw cleanup quality. The joined UI shows fallback selection for
  diagnosis; no failed model is qualified by that behavior.
- Guardrail fallback now returns the visible deterministic post-filler input rather than restoring
  removed fillers. This is a declared mechanical transformation; Sotto's raw output still must
  pass semantic safety independently.
- Gemma 3 1B was the closest generic candidate at 32/45 raw exact and 94.1% anchor preservation,
  but it retained a superseded command and obeyed two embedded instructions. It is rejected.
- Historical host screens remain Apple M2 measurements. Public Sotto now also has Pixel 7 runtime
  smoke evidence solely to unblock integration work; this does not supersede its failed quality
  decision.
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
  The server was stopped after evaluation. Sharding and merge membership are deterministic, but
  vLLM 0.8.5 generation is not batch-invariant: publisher exact counts ranged from 4,739 to 4,750
  versus 4,751 sequential, with a maximum 0.17-point aggregate delta and 110–124 changed outputs
  per run. Use one fixed 64-client backend for comparisons and repeat borderline results. All raw
  results remain under `/data`.
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
- The fixed-recipe Disfl-QA standalone run completed at
  `/data/rise/android_stt/runs/direct-disfl-qa-qwen3-0.6b-e1-seed23-20260817T165542Z`: 225/225
  steps, 7,181/1,000 rows, no truncation, 0.19946 train loss, and 0.14729 final validation loss.
  Its own-source vLLM score was 765/1,000 exact, but transfer collapsed to 100/6,921 Sotto and
  30/250 Nyra. Exhaustive review of its 62 non-exact retired outputs found 23 substantive raw
  policy failures. It is source-specific and rejected; sanitized evidence is
  `docs/evaluation/results/2026-08-18-direct-disfl-qa-qwen3-evaluation.json`.
- The fixed-recipe Nyra standalone run completed at
  `/data/rise/android_stt/runs/direct-nyra-qwen3-0.6b-e1-seed23-20260817T171059Z`: 140/140 steps,
  4,458/250 rows, no truncation, 0.12580 train loss, and 0.07235 final validation loss. Its
  same-profile vLLM results were 150/250 own-source, 1,479/6,921 Sotto, and 73/1,000 Disfl-QA.
  Retired diagnostics reached 38/69 exact but all 10 self-corrections missed exact targets, and
  exhaustive review of all 31 non-exact outputs found 18 substantive raw policy failures. It is
  rejected; sanitized evidence is
  `docs/evaluation/results/2026-08-18-direct-nyra-qwen3-evaluation.json`.
- Poor cross-source transfer and raw-safety failure across all three standalone adapters justify
  the predeclared combined experiment. The initial one-epoch combined run at
  `/data/rise/android_stt/runs/direct-combined-qwen3-0.6b-e1-seed23-20260817T172338Z` passed the
  complete no-truncation audit and reached step 92/4,599 before an explicit user-requested stop;
  its `KeyboardInterrupt` status and logs are preserved, and it is not a training failure.
- The combined follow-up is deliberately three epochs so checkpoints at steps 4,599, 9,198, and
  13,797 can be evaluated as an epoch-wise learning curve. The dedicated config changes only
  epochs, total expected steps, save/eval cadence, and checkpoint retention relative to the
  combined one-epoch recipe; data, Qwen3-0.6B, BF16 rank-16 LoRA, optimizer settings, effective
  batch 32, seed 23, and the 2,112-token no-truncation contract remain fixed. This is a recipe
  follow-up, not a directly identical fourth row in the one-epoch dataset comparison. Never use
  blind-v2 to choose among its checkpoints.
- The three-epoch run completed at
  `/data/rise/android_stt/runs/direct-combined-qwen3-0.6b-e3-seed23-20260817T173233Z` from clean
  training commit `00fae17`: exactly 13,797 steps, 23,584.5 seconds, 0.07053 aggregate train loss,
  and zero truncation across 147,142/8,171 rows. Complete resumable checkpoints exist at steps
  4,599, 9,198, and 13,797; the final adapter exactly matches checkpoint 13,797.
- Validation loss was 0.09308, 0.08544, and 0.09364 at epochs 1–3. The fixed vLLM profile scored
  every epoch on all three publisher splits and both retired diagnostic suites. Epoch 2 is the
  experimental selection: 4,850/6,921 Sotto, 769/1,000 Disfl-QA, 147/250 Nyra, 52/69 retired
  exact, and 153/163 anchors. It improves the same-profile standalone Sotto/Disfl-QA counts by
  111/4 but trails Nyra by 3. Epoch 3 marginally improves Sotto/Disfl-QA while regressing Nyra,
  validation loss, retired exactness, anchors, no-op behavior, and safety.
- No combined checkpoint is deployable. Exhaustive agent review of every non-exact retired raw
  output found 8, 9, and 14 substantive policy failures at epochs 1–3, including answered content,
  changed dictated intent, deleted framing/negation/tone, protected name/literal changes, and
  invented formatting. Guardrails cannot rescue these raw failures. Sanitized hashes and the
  selection rationale are in
  `docs/evaluation/results/2026-08-18-direct-combined-qwen3-learning-curve.json`; raw artifacts and
  review queues remain under the run's `/data/.../evaluation/epoch-*` directories.
- The publisher's finished Sotto LFM2.5-350M checkpoint was pinned at
  `6df6f019170b8b55333c047b901886a51750a965`, downloaded, hash-verified, and evaluated in BF16 with
  its native prompt/decoder on all 69 retired diagnostics. It reached 42/69 exact, 147/163 anchors,
  and 2/10 exact self-corrections; all 17 dictated questions/commands remained text rather than
  being answered. User review calibrated 59/69 outputs as acceptable for ordinary conversation.
  The ten relevant failures are seven retained superseded corrections, two retained direct
  repetitions, and one statement changed into a question. It has been converted only as a
  replaceable Android integration placeholder and is not deployment-ready; see
  `docs/evaluation/results/2026-08-18-sotto-lfm25-350m-public-screen.md`.
- The user-calibrated everyday-conversation screen does not gate on disposable lead-ins,
  punctuation/contractions, word-to-digit time conversion, inferred list formatting, redundant
  but correct version wording, currency/non-Latin-name normalization, brackets, or technical/code
  literals such as the malformed Gradle case. Strict metrics remain unchanged for reproducibility.
- The approved next work is `docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`: first continue the
  public Sotto checkpoint for two full-SFT epochs at `2e-6` on a deterministic 55/25/10/10
  Sotto/Disfl-QA/DISCO-English/Nyra mixture, then—after complete evaluation—run a clean three-epoch
  `3e-5` full-SFT reproduction from pinned `LFM2.5-350M-Base` using the same mixture and the
  publisher's disclosed batch/schedule/packing settings.

## Toolchain

- Android Studio Quail 3 / 2026.1.3 Patch 1
- Android Gradle Plugin 8.13.2
- Gradle 8.13
- Kotlin 2.3.20
- JDK 17
- compileSdk / targetSdk 36; minSdk 31
- Android Platform-Tools 37.0.1
- Android NDK 28.0.13004108 and SDK CMake 3.31.6 for the pinned Parakeet ARM64 build
- Perfetto trace processor 57.2 for optional Pixel power-rail analysis

## Resume checklist

1. Read root `AGENTS.md`, this file, and `NEXT_STEPS.md`.
2. Run `git status --short` and preserve any uncommitted work.
3. On the RTX A6000 machine, read `TRAINING_MACHINE_HANDOFF.md` completely and follow its Phase 0
   preflight. Do not run the Mac/Pixel steps below.
4. On the Mac with the Pixel attached, run `./scripts/check-toolchain.sh`, then
   `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`.
5. To resume integration testing, install the debug APK, run
   `./scripts/stage-integration-models.sh`, then load staged Parakeet and Sotto in the Activity. The
   ignored `.cache` artifacts must match the hard-coded hashes; see the root README and integration
   evidence manifest.
6. Continue active Milestone 4 with
   `docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`. Preserve all completed Qwen source
   experiments, but the next evidence-bearing work is the two-stage LFM correction-repair study.
   Preserve the reviewed-pilot Gate A path, never use blind-v2 for iteration, and do not compare
   the LFM sequential-Transformers results directly with the older Qwen vLLM profile.
