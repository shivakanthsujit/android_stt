# Next steps

Last updated: 2026-08-22

## Completed: S1-mini v1 selection and preferred joined integration

- [x] Pin and hash the official BF16 safetensors, F16 GGUF, and Q4_K_M GGUF artifacts outside Git.
- [x] Preserve the exact publisher system prompt, trained control line, thinking-off template,
  greedy decoding, and input-relative output cap in reproducible host harnesses.
- [x] Run the 69-case seed + held-out project screen and 20-case personal-v3 suite × 3 measured
  repeats after warmup on Q4_K_M and F16 through llama.cpp and on actual BF16 through the
  documented Transformers CPU path. Exclude blind-v2 and STT/audio suites.
- [x] Record latency, native GGUF decode rate, load/readiness, sampled RSS, repeat stability, and
  raw-output agreement without reading expected answers or making a quality claim.
- [x] Record the owner's personal-use acceptance policy: model semantic quality remains measurable
  research evidence, but it does not gate insertion because the owner reviews and edits text.
- [x] On the attached Pixel, use LEAP 0.10.9's Android llama.cpp backend to reproduce the exact
  trained prompt/template contract and measure Q4_K_M. Raw-token/output-cap parity is 69/69 and
  raw text parity is 66/69 versus Mac Q4. Preserve 1.576 s traced median total, 1.29M KiB PSS,
  6.493 J/call, and sustained thermal status 1 as product caveats. BF16 Pixel feasibility remains
  open.
- [x] At explicit user direction, make exact-contract S1-mini the preferred ordinary cleanup
  engine/artifact, move model and joined-corpus staging to Android 17-compatible app-private
  storage, and keep raw output visible.
- [x] Run the no-override 20-case Parakeet → S1-mini joined path on Pixel. The final run completes
  20/20 with one genuine correction fallback; raw and guarded strict/normalized counts agree.
- [ ] Before redistributing or bundling S1-mini weights, retain its license/attribution notices and
  exact required name, `S1-mini by Superwhisper`, and confirm the additional naming term covers the
  intended distribution. Current sideloaded development staging is not a release package.

Full evidence: `docs/evaluation/results/2026-08-21-s1-mini-v1-local-performance.md` and
`docs/evaluation/results/2026-08-21-s1-mini-v1-pixel.md`.

## Active: S1-mini Pixel inference optimization

Follow the controlled sequence in
`docs/research/S1_MINI_PIXEL_INFERENCE_OPTIMIZATION_PLAN_2026-08-22.md`. Keep the official S1
Q4_K_M bytes and exact publisher contract fixed while isolating each source of performance change.
Do not add lower-bit GGUF variants.

- [x] Audit LEAP 0.10.9's public controls. It exposes two-to-four-thread candidates, context size,
  mmap, memory/disk cache policy, and cached-prompt statistics, but not batch/ubatch. The fixed
  prompt is 78 tokens and the maximum permitted pass needs 2,410 tokens, so 3,072 and 2,560 are
  safe context candidates while 2,048 is not.
- [x] Add debug-only LEAP parameters and result metadata. The host implementation accepts only
  explicit CPU threads 2/3/4 or implicit, contexts 4,096/3,072/2,560, and cache-off or memory-only
  four-entry 32/64 MiB arms. It keeps mmap and fresh conversations, asserts prompt+cap context
  capacity, records cached tokens plus requested/resolved configuration, gives every arm a unique
  run ID, and keeps the scorer backward compatible while rejecting mixed or out-of-matrix
  configurations. Measured repeats are interleaved instead of placing identical prompts adjacent.
- [x] Run the controlled LEAP Pixel matrix and select explicit two threads, 2,560 context, cache
  off, and mmap on. The matched trace improves median/p90 total by 17.88%/19.32%, peak PSS by
  10.50%, and inference compute energy by 10.09% with 60/60 raw parity. Cache reused zero tokens.
  Production now uses the selected supported LEAP settings. Evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-leap-pixel-tuning.md`.
- [x] Build a separate collision-free Android benchmark module pinned to llama.cpp `ece963f41` /
  build 10450, NDK `28.0.13004108`, and CMake `3.31.6`. The 18,701,319-byte host-verified Release
  APK contains only the isolated llama/ggml CPU stack and has SHA-256
  `8931caef1a33acc84c9eb173d4d09d986f71ea0f6816716e3a3e93ce05b1bfad`. Evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-direct-llamacpp-host-readiness.md`.
- [x] Run the direct APK's initial device contract smoke. The Pixel selected
  `libggml-cpu-android_armv8.2_2.so`; 4/4 rows exactly match host golden prompt bytes and raw/prompt
  token IDs, all fixed deltas/caps match, no cap was reached, and thermal remained 0. This is not a
  matched LEAP/Mac raw-output or performance result.
- [x] Complete Stage 2 direct llama.cpp Pixel evidence. A natural cap fixture passed 6/6 measured
  calls; the bounded thread/internal-token-buffer/flash matrix ran one cleanup request at a time;
  and every parity-safe arm was rejected. On the final user-shaped 10-case corpus (median 22 raw
  tokens), direct matched prompt/cap/raw output 30/30 but was 9.3% slower at median total latency,
  7.2% slower at p90, used 8.8% more median CPU, and reached thermal 1 while LEAP stayed at 0.
  Retain LEAP; preserve the isolated direct probe as evidence. Report:
  `docs/evaluation/results/2026-08-22-s1-mini-direct-llamacpp-pixel.md`.
- [ ] Treat a direct Pixel Mali Vulkan build as a separately scoped optional experiment, not the
  next production step. The project-owned CPU runtime failed its displacement gate.
- [x] On the Linux RTX A6000 host, convert the pinned S1 BF16 checkpoint—not the GGUF or generic
  Qwen—to LiteRT-LM with a metadata-verified blockwise-32 INT4/FP32 recipe. Export context 4,096
  first; explicitly exclude channelwise, block-128, sub-four-bit, and smaller-GGUF arms. The
  436,596,864-byte bundle has SHA-256
  `8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403`; all 1,154 INT4 tensors
  are proven block size 32 and all KV signatures are FLOAT32. Evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-litert-conversion.md`.
- [x] Pass the initial host LiteRT-LM CPU/GPU load and byte-exact prompt/template/cap smoke. Both
  arms returned `Hello there` for the authored 3-token filler input; native JVM benchmark counters
  were unavailable and are explicitly not inferred from wall time.
- [x] Add an isolated, permissionless Android LiteRT-LM probe and run the frozen English
  user-shaped cases on Pixel CPU/GPU. Exact rendered prompts and caps passed; CPU/GPU lost 10/10
  paired latency calls. CPU median total/PSS regressed 448.2%/42.4%; genuine Mali/OpenCL GPU
  regressed 91.0%/142.9%. Reject both and retain LEAP. The owner excluded the nonrepresentative
  Japanese/Unicode stress row from selection and future tests.
- [x] Uninstall `dev.localflow.litertlmbenchmark` with owner approval after evidence handoff.
  App-private model/cache removal recovered 1,062,396 KiB (about 1.01 GiB); the production keyboard
  remained installed. No further LiteRT performance arm is warranted.
- [ ] Select a replacement only after sustained same-method latency, p90, memory, energy, thermal,
  deterministic-output, and maintenance-cost comparison against the LEAP reference.

## Completed: streaming STT and long-transcript cleanup integration

- [x] Replace the ordinary live offline-on-Stop artifact with Parakeet Realtime EOU 120M v1 Q4_K,
  pin its filename/SHA-256, and extend the pinned `parakeet.cpp` JNI bridge to its cache-aware
  streaming C API.
- [x] Stream newly finalized raw text to the Activity and IME during recording while preserving
  project-owned `AudioRecord`, synchronous microphone Stop, explicit Start/Stop, and cancel without
  cleanup.
- [x] Keep cleanup final-only. Tokenize the complete final transcript with S1-mini's loaded
  tokenizer, greedily pack passes at no more than roughly 1,000 raw tokens, prefer EOU/punctuation
  boundaries, preserve per-pass prompt/thinking/greedy/output-cap settings, and rejoin in order.
- [x] Pass Android unit tests, rebuild the pinned ARM64 JNI libraries, assemble the debug APK, and
  verify the staged Realtime EOU artifact can load and create a native stream session on Pixel
  without opening the microphone.
- [ ] Owner-run live speech check: confirm raw partial text appears while speaking, cleanup does not
  start before Stop, Stop flushes the final tail, and the entire final text is then cleaned once.
- [ ] Add deterministic long-input integration coverage that exercises multiple real-tokenizer S1
  passes on device without using any evaluation-only corpus.
- [ ] Before redistributing or bundling the Parakeet GGUF, reconcile and retain the NVIDIA source
  model license and the converted collection's declared CC-BY-4.0 terms/notices.

Runtime/model-card notes:
`docs/research/STREAMING_STT_AND_S1_MINI_RUNTIME_CONTRACT_2026-08-21.md`.

## Completed: owner-local FluidVoice reference inventory

- [x] Inventory the installed FluidVoice/FluidAudio application, active Parakeet TDT v2 Core ML
  model, selectable-model registry, transcript preprocessing, Fluid-1 prompt/template, inference
  artifacts, and output processing without recording personal dictionary contents or transcripts.
- [x] Preserve and hash the pre-update Fluid-1 Q4_K_M checkpoint, bundled prompt, current signed
  MLX manifest/helper/runtime bundles, and all eight files in the completed 3.58 GB main replacement
  model. Record that the manifest's optional 188.7 MB MTP drafter was not locally downloaded.
- [x] Add a one-shot owner-local GGUF/MLX smoke runner that emits raw cleanup output without using
  committed evaluation cases.
- [x] Record the vendor-reported “100K+ dictation data points” sentence as a scale heuristic only;
  it is not evidence of dataset composition, provenance, pair structure, licensing, or quality.
- [ ] Obtain explicit written permission before any Fluid-1 conversion, fine-tuning, teacher-label
  generation, research evaluation, redistribution, bundling, or product use. Until then, keep the
  artifacts outside training and Android candidate selection.

## Completed: Milestone 2 — Liquid cleanup model evaluation

Goal: select the smallest LEAP-compatible model that can conservatively clean manually supplied
text on the Pixel 7, remain usable offline after its first download, and meet the fixed quality and
latency evaluation bar. LFM2.5-230M, 350M, and 1.2B-Instruct all failed that bar.

- [x] Pin Liquid LEAP SDK/model downloader `0.10.9`.
- [x] Implement `CleanupEngine`, `CleanupResult`, and `LiquidCleanupEngine` behind an interface.
- [x] Load and benchmark `LFM2.5-230M` with `Q4_K_M`.
- [x] Add manual editable raw text, cleaned result, and raw pre-guard model output.
- [x] Add cleanup model/load/run actions with guarded UI states.
- [x] Add a 24-case direct-text corpus, three-way prompt runner, pullable JSONL, and host scorer.
- [x] Add empty, expansion, token-cap, and suspicious-contraction fallbacks.
- [x] Measure load, TTFT, total generation, tokens, throughput, EOS, and cap hits.
- [x] Build, lint, test, and run the matrix on Pixel 7.
- [x] Verify cached model load and the complete 72-run matrix in airplane mode.
- [x] Benchmark `LFM2.5-350M` Q4_K_M; it was worse than 230M and changed meaning.
- [x] Select `LFM2.5-1.2B-Instruct` Q4_K_M as the next stronger candidate to evaluate.
- [x] Run and score the same 24-case × 3-prompt matrix on 1.2B-Instruct.
- [x] Reject any candidate with a meaning-changing output, then compare exact score, anchor/case
  preservation, fallback rate, TTFT, and total latency against the recorded 230M baseline.
- [x] Verify cached 1.2B-Instruct load with airplane mode enabled.
- [x] Record 1.2B-Instruct memory/thermal observations.
- [x] Make and document the 1.2B-Instruct go/no-go decision; do not begin joined integration on model
  size or anecdotal examples alone.
- [x] Run a focused strict/few-shot prompt iteration and preserve its raw result.
- [x] Add conservative lexical/intent safety fallbacks and unit coverage.
- [x] Commit the completed Milestone 2 harness, results, and no-go decision as `8dce7ab`.

All three Liquid candidates failed: 230M and 350M lack capability; 1.2B remains unsafe and too slow
under stronger prompts. They remain no-go baselines while the bounded cross-family screen below is
run.

## Completed: Milestone 3 — cleanup candidate screening

Research note: `docs/research/CLEANUP_MODEL_CANDIDATES_2026-08-17.md`.

- [x] Add a deterministic Outspoke-style cleanup baseline and score it against the same corpus.
- [x] Add a fresh held-out cleanup set before any further prompt tuning or fine-tuning.
- [x] Add a host/runtime-neutral batch adapter so GGUF or OpenAI-compatible local servers can emit
  the existing JSONL result schema.
- [x] Quality-screen Granite 4.0 H 350M Q4_K_M, Qwen3-0.6B no-think INT4/Q4, and Gemma 3 270M IT
  against the fixed cases. Keep Qwen3.5-0.8B and Gemma 3 1B as second-wave candidates.
- [x] Reject any model that changes meaning, answers dictated content, invents facts, or fails
  explicit self-corrections; compare exact match only after the safety gate.
- [x] Evaluate second-wave Qwen3.5-0.8B and Gemma 3 1B after the smaller candidates failed.
- [x] Apply Android-equivalent guardrails to host output and independently audit the strongest
  candidate's non-exact results.
- [x] Do not advance a candidate to Pixel 7: every model failed the quality gate, so runtime
  integration and performance measurements would not influence the product decision.
- [x] Decide against generic zero-shot cleanup for the current model set. Keep deterministic
  cleanup as a control and make a task-specific fine-tune the next generative cleanup experiment.

Full evidence: `docs/evaluation/results/2026-08-17-cross-family-cleanup-screen.md`.

Do not join cleanup to STT during this milestone.

## Parallel: Milestone 4 — task-specific cleanup

Cleanup remains the model-quality bottleneck, but it no longer blocks product integration work.
The current offline STT path is provisionally good enough to supply raw transcripts, and the joined
Android boundary now defaults to exact-contract S1-mini as the explicit preferred local model. Keep
that engineering choice separate from checkpoint qualification and never treat guardrail fallback
as a passing raw model result.

Working references:

- `TRAINING_MACHINE_HANDOFF.md`
- `docs/research/VOICEINK_QWEN35_2B_SCREEN_2026-08-17.md`
- `docs/evaluation/SPECIALIZED_CANDIDATE_SCREENING.md`
- `docs/research/TASK_SPECIFIC_CLEANUP_TRAINING_PLAN_2026-08-17.md`
- `docs/research/CLEANUP_TRAINING_DATA_SOURCES_2026-08-17.md`

### Immediate public-model screen

- [x] Verify the exact public VoiceInk Qwen3.5-2B fine-tune artifact, license, template, and GGUF
  quantization. Preserve model revision and file checksum.
- [x] Run it through the existing host runner on the frozen 24-case and 45-case regression suites.
- [x] Manually audit every non-exact response and every must-not-answer/self-correction case. Raw
  output, not guardrail fallback, must pass the semantic gate.
- [x] Treat the 2B model as a quality probe or teacher if it is too large for an inline Pixel
  keyboard. Do not integrate it into Android solely because it beats the generic candidates.

Decision: VoiceInk is a no-go at 38/69 raw exact and 2/10 corrections, with ten critical outputs.
It may propose training candidates only under deterministic checks and human review; never accept
its labels automatically. Full report:
`docs/evaluation/results/2026-08-17-voiceink-qwen35-2b-q4km.md`.

### Small-model fine-tuning path

#### Immediate direct-source evidence track

The next training-machine session starts with
`docs/training/DIRECT_SOURCE_EXPERIMENT_PLAN.md`. This exploratory track intentionally gets models
to evaluation before completing the stricter balanced/reviewed corpus.

- [x] Add a separate direct-source loader/config/trainer without weakening or faking the reviewed
  pilot Gate A path.
- [x] Fix Qwen3-0.6B, one epoch, BF16 LoRA rank 16, effective batch 32, learning rate 2e-4, seed
  23, assistant-only loss, and a no-thinking format for the four-way comparison. After the complete
  Sotto audit, revise the no-truncation ceiling to 2,112 tokens with microbatch 4 / accumulation 8.
- [x] Run one 32-row/two-step mechanical smoke on Sotto and verify checkpoint/final-adapter output.
- [x] Record the user's explicit waiver of the pre-run push gate for local commit `53a5551` and
  attempt the full managed launch without pushing.
- [x] Diagnose the fail-closed 1,024-token startup failure across the complete Sotto split: 775
  train and 46 validation rows exceed the limit; maxima are 1,838 and 2,050 tokens.
- [x] Run text-free worst-case memory diagnostics for the 2,112-token proposal. Original microbatch
  8 OOMs; both microbatch 4 / accumulation 8 and gradient-checkpointed microbatch 8 pass while
  preserving effective batch 32.
- [x] Apply the authorized fixed four-way change to 2,112 tokens, microbatch 4, and accumulation 8;
  commit it and launch the full 135,503-row Sotto split unchanged otherwise. The exact longest-row
  diagnostic already passed, and the user explicitly directed launch without another managed
  smoke. The active run is
  `direct-sotto-qwen3-0.6b-e1-seed23-20260817T124158Z`; do not silently truncate or describe a
  filtered subset as the full run.
- [x] Research the Sotto publisher's own training settings. No formal paper was found; the official
  model-card lineage uses LFM2.5-350M full SFT, most clearly three epochs at 3e-5 with effective
  batch 8, packed 4,096-token context, AdamW beta2 0.95, and later GRPO/refinement/soup stages.
  Preserve the sourced comparison in
  `docs/research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md`; do not change the active recipe.
- [x] Finish and score all 6,921 Sotto publisher-validation rows: 4,751 exact (68.65%), zero empty,
  48 capped, and 3,098 guardrail-flagged outputs. The evaluator exited zero and the cases, results,
  provenance, and score artifacts are hashed in
  `docs/evaluation/results/2026-08-18-direct-sotto-qwen3-evaluation.json`.
- [x] Add the isolated vLLM serving environment and deterministic multi-client evaluation path.
  Smoke the served LoRA, validate publisher plus both committed diagnostic merges, and sweep full
  publisher concurrency. Use 64 clients for this Qwen3-0.6B/A6000 workload (83 seconds for 6,921
  cases); remeasure if the base, output distribution, or GPU changes. Sharding is deterministic,
  but vLLM 0.8.5 generation is not batch-invariant, so keep the serving profile fixed, repeat
  borderline comparisons, and do not mix its quality scores with sequential inference scores.
- [x] Train and evaluate the standalone Disfl-QA and Nyra adapters with the identical recipe and
  fixed vLLM profile. Disfl-QA reached 765/1,000 exact on its source but only 100/6,921 Sotto and
  30/250 Nyra, with 23 substantive retired-diagnostic safety failures. Nyra reached 150/250 on its
  source but only 1,479/6,921 Sotto and 73/1,000 Disfl-QA, with 18 substantive safety failures.
  Both are source-specific no-go results.
- [x] Complete and evaluate the justified combined learning curve. The initial one-epoch run was
  explicitly stopped and preserved at step 92 after the user requested a real epoch-sufficiency
  test. Run three epochs under the dedicated config, saving/evaluating at steps 4,599, 9,198, and
  13,797. Evaluate every epoch checkpoint with the same vLLM profile on the combined publisher
  validation, each source split, and both retired diagnostics; audit every non-exact retired raw
  output before selecting an epoch or deciding the next base/data/recipe experiment.
  The completed run is `direct-combined-qwen3-0.6b-e3-seed23-20260817T173233Z` from commit
  `00fae17`; preserve its durable telemetry, logs, status, and all three resumable checkpoints.
  Training and all three epoch evaluations are complete. Epoch 2 (`checkpoint-9198`) is the best
  experimental checkpoint, but all epochs fail raw safety; see the final combined report.
- [x] Use the four-way evidence to choose the next direction. Data repair matters first because all
  Qwen3-0.6B source recipes remain unsafe and the combined set is 92% Sotto by row count. Preserve
  epoch 2 as the research baseline; next create a leakage-safe safety-curated/source-balanced
  revision, then compare Qwen3.5-0.8B rank-16 LoRA at one and two epochs. Do not spend a fourth
  epoch on the current run and do not use blind-v2 during iteration.
- [x] Pin and directly screen the publisher's completed Sotto LFM2.5-350M checkpoint before doing
  more training. Native-prompt BF16 inference reached 42/69 strict exact, preserved 147/163
  anchors, and did not answer any dictated question/command. User review accepts 59/69 for ordinary
  conversation; the ten relevant failures are seven retained superseded corrections, two retained
  repetitions, and one statement changed into a question. It is now converted and integrated only
  as the user's temporary pipeline placeholder, not as a reversal of the no-go deployment
  decision.
- [x] Complete the approved Sotto LFM correction-repair experiment in
  `docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`. First continue the pinned public checkpoint
  with full SFT for two epochs at `2e-6` on the shuffled natural correction mixture;
  evaluate both epochs before starting the clean-base arm. Then full-SFT a pinned
  `LFM2.5-350M-Base` for three epochs at `3e-5` with the same ordered mixture and disclosed
  publisher settings. Save/evaluate every epoch, target only the ten relevant failures, and never
  use either committed diagnostic corpus as training data.
  Data preparation and all launch gates are complete under `/data`: every eligible source row is
  used once per epoch, canonical HF snapshots are used, DISCO is pinned, its test partition is
  excluded, and two frozen-diagnostic overlaps were removed. Formatting, overfit, longest-row,
  interruption/resume, and saved-checkpoint inference checks passed. The two-epoch Experiment A
  completed and both checkpoints were evaluated on all 69 retired cases plus all 8,519 source-dev
  rows. The separately named four-epoch learning curve also completed. Epoch 4 is the selected
  research checkpoint at 4,889/8,519 source exact, but it is not deployment-qualified because two
  dev prompts produce repetition loops through the 900-token cap; the final epoch adds only six
  exact matches over epoch 3. Experiment B then completed all three clean-base epochs and all
  checkpoint evaluations. Select epoch 1 as the safety-weighted research checkpoint: it reaches
  5,477/8,519 source exact, 51/69 retired exact, and 155/163 protected anchors, versus 4,889,
  46/69, and 144/163 for selected Experiment A. Do not select source-exact leader epoch 3 because
  its retired result regresses to 46/69 and 149/163. No LFM checkpoint is deployment-qualified:
  selected epoch 1 still has one source repetition loop and substantive intent, command,
  identifier, and name-preservation failures. Preserve the evidence; any next local-model run must
  be a separately reviewed targeted repair experiment rather than an automatic extra epoch.
- [x] Evaluate the public start and every retained A/B epoch on fixed personal v3. Public start is
  the strict leader at 11/20 exact and 53/61 literal anchors. Under the later default relaxed
  semantic calibration, all B epochs lead local models at 15/20 acceptable versus 14/20 for public
  and A. Raw review still keeps every fine-tuned checkpoint out of Android: A changes a currency
  unit/tense, while B retains required corrections and formatting directives. Record the guardrail
  false negatives and false rejection separately; do not use v3 output text for training.

Prepare all data and training inputs portably in this repository, but run training only on the
separate training machine when it is available. Do not start training on this Mac.

- [x] Freeze a training schema for raw transcript, cleaned target, transformation labels, protected
  spans, and provenance. Never train on either committed evaluation corpus.
- [x] Select and pin public candidate sources: Sotto transcript cleanup as primary, Disfl-QA for
  question corrections, and Nyra Disfluency Speech for an audio-backed supplement. Treat every row
  as untrusted until project validation/review.
- [x] Add a self-contained RTX A6000 handoff covering environment preflight, source pins, data
  isolation, training/evaluation deliverables, monitoring, resume, artifacts, and blind-v2 rules.
- [x] Build the pinned source fetcher, importer, conservative filter/quarantine rules,
  near-duplicate family splitter, and deterministic source manifest.
- [ ] Build a balanced, reviewable training/dev corpus covering fillers, repeats, false starts,
  explicit corrections, punctuation, commands/questions-as-data, adversarial text, names, numbers,
  uncertainty, negation, Unicode, and technical tokens.
- [ ] Prepare the blind evaluator contract early. After training templates stabilize, have an
  independent context author/double-review and seal blind v2 outside the training job's readable
  path; do not use it for checkpoint or prompt selection.
- [x] Complete the approved LFM2.5-350M correction-repair and clean-base comparison before
  returning to the deferred Qwen3.5-0.8B alternative.
- [ ] Do not quantize a fine-tuned checkpoint from this campaign. First decide whether to design an
  independently sourced repair experiment or retain deterministic/public-placeholder cleanup;
  create a new evaluation version for later policy changes.

Training-machine checkpoint (2026-08-17): fetch/import/filter/source-holdout/family-split/quota,
Gate A, training/resume, inference/scoring, and read-only monitoring code is implemented and fixture
tested. The locked CUDA environment, source fetch/verification, real importer dry run, and sanitized
coverage census pass. The measured public gaps now have a deterministic pending-only supplemental
generator. The balanced-corpus item remains open until the durable `/data` import/supplement outputs
are built, source licenses and all selected rows are human-reviewed, and Gate A/release manifests
pass. The next external step is durable import and pending review selection.

### Qualification gate

- [ ] Require zero meaning changes, invented content, or answered/obeyed dictation on blind v2.
- [ ] Require reliable explicit self-corrections and full preservation of protected names, numbers,
  negation, uncertainty, paths, versions, and code-like tokens.
- [ ] Compare exact match, edit precision/recall, protected-span preservation, fallback rate, and
  manual semantic audit; do not select on aggregate exact match alone.
- [ ] Advance only a quality-passing quantized checkpoint to Pixel. Then record load time, warm TTFT
  and total latency, peak PSS/RSS, model bytes, thermal drift, and offline cache reuse.

Decision point: use the public task-tuned model, train a smaller model, or ship conservative
deterministic cleanup while generative corrections remain disabled.

## Partially complete: Milestone 5 — STT-only evaluation

- [x] Keep cleanup unloaded during the controlled file-fed STT comparison.
- [x] Add file-fed audio evaluation so identical recordings can be tested without repeated
  speaking.
- [x] Prepare a deterministic 24-clip/12-speaker LibriSpeech `test-clean` probe with per-audio and
  manifest hashes. Do not present its score as official full-split WER.
- [x] Benchmark Moonshine Small and pinned `parakeet.cpp` 0.5.0 TDT/CTC 110M F16/Q4_K on Pixel 7.
- [x] Score normalized WER, S/I/D, median/p90/p99/max latency, corpus RTF, repeat stability, model
  load, PSS, thermal state, process CPU time, and Perfetto CPU/GPU/memory rail energy.
- [x] Choose Q4_K as the provisional deployment candidate: one additional word error versus F16,
  but 23.8% less process CPU time, 23.3% less compute energy, 25.5% less PSS, and about half the
  model bytes. Keep F16 as the non-quantized quality reference.
- [x] Integrate project-owned 16 kHz microphone capture with the selected Parakeet Q4_K model and
  run final offline inference after Stop. Record the lack of partial/streaming output explicitly.
- [x] Add a pinned, Mac-local Qwen3-TTS/MLX-Audio fixture pipeline and generate an ignored,
  Android-compatible 65-clip corpus from heldout-v1's `spoken` inputs plus 20 project-authored
  dictation stress cases. Preserve native/canonical hashes; that technical v1 set is now historical
  synthetic evidence rather than the active product workload.
- [x] Version the active 20-case personal-conversation suite to v3: remove phone-number dictation,
  retain messages/journals/lists/names/numbers/uncertainty/repetition/formatting/corrections, and add
  four 3–5 sentence cases for long-form quality and latency. Exclude technical stress text.
- [ ] Add human/multi-speaker personal dictation recordings for qualification, and score protected
  names, numeric equivalence, correction success, and formatting separately from literal WER.
- [x] Integrate Parakeet Realtime EOU 120M Q4_K streaming/end-of-utterance behind
  `SpeechToTextEngine` without weakening the project-owned microphone lifecycle. Partial
  responsiveness and Stop-to-final measurement remain part of the live qualification task.
- [ ] Verify cold load, offline model reuse, sustained thermal behavior, and live dictation memory.
- [ ] Compare Pixel's on-device `SpeechRecognizer` only if its offline path can be made deterministic.
- [ ] Make the final STT choice after the dictation/streaming gate; the read-speech probe is not
  sufficient by itself.

## Separate campaign: hosted GPT-5.4 API comparison

This optional personal-use/cloud comparison is not part of the local-model training research plan.
Keep its data handling, evidence, pricing, and product decision separate.

- [x] Define the isolated campaign and record the user's authorization to send both committed
  24/45-case evaluation corpora to the OpenAI API. Continue to prohibit blind-v2 and any reuse of
  evaluation inputs or outputs for training, retrieval, demonstrations, or preference data.
- [x] Add explicit `max_completion_tokens` support to the OpenAI-compatible runner and retain the
  local-server `max_tokens` default; cover the new request field with a unit test.
- [x] Run a four-case seed pilot on dated GPT-5.4-mini and GPT-5.4 snapshots with streaming,
  `reasoning_effort=none`, raw scoring, and usage capture. Eight successful requests used 957
  tokens total; the pilot evidence is
  `docs/evaluation/results/2026-08-18-gpt54-api-pilot.md`.
- [x] The user verified that pilot usage appeared under the complimentary shared-data offer, then
  authorized the complete hosted screens.
- [x] Run all 24 seed and 45 heldout-v1 cases sequentially for each model. Score raw output and
  parallel guardrail evidence, manually audit every non-exact output and safety-sensitive case,
  and report token usage plus sequential TTFT/total distributions.
- [x] Reuse the checkpoint publisher-dev evaluation inputs without running checkpoint inference:
  all 8,519 rows for mini and a deterministic source-stratified 1,500-row GPT-5.4 sample bounded by
  the 250k pool. Record four-client latency/throughput separately from sequential product latency.
  Do not run a further concurrency sweep because both models fail raw quality/safety gates.
- [x] Estimate standard paid cost from recorded input and output usage using
  `model_page.md`; distinguish the shared-data test project from the owner's later non-sharing key.
  The entire campaign used 1,343,189 tokens and corresponds to $2.4309 if billed.
- [x] Rerun only the active 20-case personal-v3 internal suite on both GPT-5.4 models and add
  GPT-5.6 Luna. Do not rerun the HF/publisher source-dev split. Full and Luna tie at 12/20 strict
  and 20/20 user-acceptable; Luna wins the hosted latency/cost comparison. Mini is 18/20 accepted
  because it retains two superseded corrections.
- [x] Make relaxed semantic acceptability the default product metric and compare every raw local
  Sotto result with the hosted models. Keep strict exactness as secondary reproducibility evidence.
  Luna/full reach 20/20, mini 18/20, B 15/20, and public-HF/A 14/20. Do not weaken correction,
  fact/unit/tense, must-not-answer, or explicit-formatting requirements.

This remains required before final product selection, but it is not the current bottleneck.

## Completed: joined integration app baseline

- [x] Feed the completed Parakeet transcript into a swappable cleanup engine automatically.
- [x] Convert and sideload the pinned public Sotto LFM2.5-350M checkpoint as Q4_K_M without
  committing model artifacts.
- [x] Display raw STT, complete unguarded model output, and guarded cleanup simultaneously.
- [x] Add conservative pre-model filler removal for standalone `um`, `uh`, and `erm`; expose the
  exact model input and retain original raw STT and removal metadata for diagnosis.
- [x] Report STT tail, cleanup TTFT, cleanup total, and end-to-end tail.
- [x] Keep both models warm between utterances while releasing the microphone at Stop.
- [x] Run one real Pixel microphone → Parakeet → Sotto smoke test and preserve sanitized timing and
  fallback evidence.
- [x] Play all 20 project-authored Qwen3-TTS dictation stress fixtures through the Mac speakers into
  the Pixel microphone and review every joined result. The lifecycle passed 20/20, but case 014
  exposed an accepted unsafe technical edit and case 011 exposed a correction-related false
  fallback. Keep this as synthetic regression evidence, not qualification.
- [x] Add a debug-only WAV/MP3/corpus-fed Parakeet → Sotto runner that never opens the microphone,
  verifies audio/model hashes, records complete stage output, and scores spoken STT separately from
  intended cleanup. Run personal v3 on Pixel: 15/20 normalized STT exact, 10/20 normalized cleanup
  exact, three genuine correction fallbacks, and 2.54–4.75 s joined tails on long-form cases.
- [x] Add the scorer-compatible `cleanup_personal_conversation_v3.jsonl` direct-text corpus and
  hash-pinned checkpoint options to `infer_sotto_lfm.py`. Require the A6000 to evaluate the public
  start plus every Experiment A/B epoch on v3, preserve raw output, and report long-form latency.
- [x] Reduce guardrail false rejection by accepting only bounded discourse deletion, explicit
  correction replacement, deterministic identical-value number rendering, and consumed explicit
  list/paragraph directives. Keep Android and host behavior aligned and retain strict protection
  for changed facts, names, values, negation, uncertainty, and answered content.
- [x] On the Pixel-connected machine, compare hosted `gpt-5.6-luna` with local B epoch 2 in an
  experimental build. Copy the uncommitted checkpoint from
  `dante:/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty/checkpoint-542` and
  preserve raw/guarded output plus cleanup and end-to-end latency. Do not treat the build as a
  deployment qualification. The checkpoint copy, Q4_K_M export, direct Pixel run, and local
  Parakeet-fed run are complete. B remains a no-go at 15/20 acceptable direct and about 13/20
  acceptable joined. The user authorized `free_usage.md`; Luna then reached 20/20 acceptable
  direct and 17/20 acceptable joined, with all corrections and formatting handled. It still
  changes one protected joined-input token into a different subject, so the raw deployment gate
  remains closed. Keep Luna as the leading optional hosted candidate, add human/multi-speaker
  dictation before another qualification claim, and do not manufacture cloud energy from Pixel
  rails.
- [x] At explicit user direction, promote B epoch 2 from a benchmark override to the ordinary app's
  provisional local default. Pin its filename and SHA-256 in app code and staging, keep the
  `CleanupEngine` boundary and debug override swappable, and preserve raw output, fallback reason,
  and the integration-only warning. This supersedes the public placeholder identity, not the raw
  quality/safety no-go result.
- [x] Build, lint, and unit-test the no-override app configuration on the host.
- [x] Reconnect the Pixel, install the current APK, run app-private default staging, and complete a
  no-override 20-case Parakeet → S1-mini file-fed run with verified artifact hashes.
- [x] Replace Sotto B with S1-mini as the preferred integration model at explicit user direction;
  preserve Sotto only for historical/debug reproducibility.
- [ ] Run the fixed cleanup evaluation and sustained dictation checks on that qualified quantized
  checkpoint before calling the joined pipeline deployable.

## Active next: minimal voice-only IME

Goal: make the already joined local pipeline usable from ordinary text fields without duplicating
model ownership or weakening microphone, privacy, and fallback behavior.

- [x] Add a voice-only `InputMethodService` and the manifest/settings metadata needed to enable it.
- [x] Add a small setup surface with microphone permission plus enable/select keyboard controls.
- [x] Reuse Parakeet and `CleanupEngine` through an application-scoped coordinator; do not create a
  second independent model stack in the IME.
- [x] Implement explicit tap-to-start/tap-to-stop and fast cancel-before-inference. Reuse the
  project-owned `AudioRecord` path, which starts only after the button tap and stops before final
  inference; never activate the microphone merely because an editor gains focus. Device behavior
  remains to be verified.
- [x] Commit the non-empty, non-capped cleanup result through `InputConnection`, while keeping the original raw
  transcript available for scrollable review, cancel, or bounded exact-suffix undo.
- [x] Detect password/private editor types. Disable dictation there by default, never
  log transcript content, and do not introduce a hosted fallback.
- [x] Add host-side editor identity checks, focus/window cancellation, service teardown handling,
  operation invalidation, and exact-suffix bounded Undo. The first QoL slice retains up to five
  same-editor commits and includes any automatically inserted separator in the undo transaction.
  Confirm all paths on-device before treating the lifecycle as complete.
- [x] Add cursor-aware commit spacing: empty fields and existing whitespace/punctuation receive no
  prefix, while consecutive ordinary dictations receive exactly one separating space. Cover both
  cursor boundaries with host tests.
- [x] Make raw transcript surfaces bounded and independently scrollable in both Activity and IME.
  Follow new partials while the owner remains at the tail, but preserve manual scroll position when
  they scroll upward. Scrolling must never pause microphone capture or STT; returning to the bottom
  resumes tail-follow.
- [x] Make a normal tap on either scrollable transcript surface copy the current raw transcript to
  Android's clipboard. Keep Android's touch-slop/drag behavior for scrolling, copy no placeholder
  or labels, and expose the action through the clickable accessibility surface. Owner-run
  scroll-versus-copy and clipboard-content verification remains open.
- [x] Instrument model load, recording, Stop-to-STT, cleanup, and Stop-to-result in the IME with
  transcript-free diagnostics.
- [ ] Add/measure IME-specific PSS, thermal state, power, and true Stop-to-editor-commit timing on
  the Pixel; host code cannot supply those device measurements.
- [ ] Finish the Pixel IME gate. Enable/select, permission-denied UI, model execution, and one
  consented in-app voice attempt are verified, and the minimal-check build is installed. Repeat the
  speech commit, then test cancel, empty/capped fallback, undo, focus switching, teardown, and
  several target apps before calling the baseline complete.

## Then: daily-driver and qualification work

- [ ] Complete the ordered QoL plan in
  `docs/research/LOCAL_FLOW_QOL_PLAN_2026-08-22.md`: clearer listening/processing/error hierarchy,
  a real non-persisted audio waveform, retry behavior, and final cancel/undo visual polish.
- [x] Add a persistent, accessible state hierarchy tied to the actual recording lifecycle. The
  separate state dot remains visible while the transcript scrolls; recording is muted dusty rose,
  processing is amber, ready is green, and the waveform accepts data only in `RECORDING`. Host
  verification and static Pixel visual QA pass; live color/state and TalkBack verification remains
  in the Pixel gate.
- [x] Add the real non-persisted waveform plumbing and lightweight custom view. Derive a throttled
  display-only envelope directly from live `AudioRecord` chunks, retain no PCM, clear immediately
  on Stop/Cancel/failure, and keep it presentation-only. After owner feedback, add an 80 Hz
  high-pass, -32 dB noise gate, slow attack/release, five-level quantization, and slimmer 36-bar
  rendering so idle noise stays quiet and speech detail is obscured. Final idle-room calibration,
  accessibility, and drawing-cost verification remains open on Pixel.
- [x] Enforce readable primary-action contrast independently of Android's Button state theme.
  Start/Stop and loading/processing use explicit light text over the muted blue or dusty-rose
  surface in XML and at every runtime state render. Static Pixel verification passes; confirm the
  live red Stop state during the next owner dictation.
- [ ] Add fail-safe recovery actions. Distinguish missing models, permission loss, STT failure, and
  cleanup failure; offer the smallest relevant retry while preserving any visible raw transcript,
  never reopening the microphone automatically, and never committing the same result twice.
- [ ] Add a compact post-result review affordance. Let the owner switch the local transcript card
  between raw and inserted text and copy either one without retaining history or changing the
  permissive insertion policy. Consider exact-suffix Replace/Redo only if editor identity and
  surrounding-text checks can remain fail-closed.
- [ ] Polish tactile and accessible feedback. Add restrained haptics for Start, Stop, Cancel, Undo,
  commit, and failure; verify TalkBack action/state announcements, dynamic type, contrast, minimum
  touch targets, and reduced-motion behavior. Do not add spoken/audio feedback that can leak into
  an active recording.
- [ ] Add compact and landscape keyboard layouts. Keep Stop and the lifecycle indicator dominant,
  collapse diagnostics by default, retain transcript scrolling/copy, and prevent the IME from
  obscuring more of the destination editor than necessary.
- [ ] Add a transcript-free recording timer and clearer Stop-to-result phase progress. Show elapsed
  listening time plus `Finalizing transcript` and `Cleaning locally` phases without estimating fake
  completion percentages or logging transcript content.
- [ ] Improve setup/model health. Detect missing or hash-invalid staged files with a direct setup
  action, make permission recovery actionable, and choose a warm/unload policy from measured Pixel
  memory and battery cost rather than a fixed guess.
- [ ] Choose model warm/unload policy based on measured memory and battery cost.
- [ ] Build a consented, evaluation-only human dictation set with multiple speakers, rooms, pace,
  accents, corrections, names, numbers, uncertainty, long-form speech, and interruptions. Keep all
  personal audio/transcripts ignored and publish only sanitized aggregates and hashes.
- [ ] Qualify Parakeet Realtime EOU on that dictation workload, including partial responsiveness,
  Stop-to-final latency, EOU boundary behavior, and comparison with the earlier offline candidate.
- [ ] Continue cleanup research with fresh train/dev data and a new evaluation version. Keep
  blind-v2 sealed until a candidate and evaluation policy are frozen. Keep research scoring
  separate from the owner's permissive personal-use insertion policy.
- [ ] Swap the cleanup artifact through the existing boundary when a later local model earns it.
  Keep Luna as optional research only unless a separate privacy-aware hosted product decision is
  made and a real Pixel network client is measured.
- [ ] Run sustained daily-driver sessions across messaging, notes, browser, and long-form editors;
  measure reliability, Stop-to-commit latency, memory pressure, thermal behavior, and battery use.
