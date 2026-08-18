# Next steps

Last updated: 2026-08-18

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

## Active: Milestone 4 — task-specific cleanup

Cleanup is the blocking stage. The current offline STT path is provisionally good enough to supply
raw transcripts while cleanup quality is solved. A clearly labeled diagnostic join now exercises
the Android boundary with public Sotto; keep it separate from checkpoint qualification and never
treat guardrail fallback as a passing raw model result.

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
- [ ] Run the approved Sotto LFM correction-repair experiment in
  `docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`. First continue the pinned public checkpoint
  with full SFT for two epochs at `2e-6` on the deterministic source-balanced correction mixture;
  evaluate both epochs before starting the clean-base arm. Then full-SFT a pinned
  `LFM2.5-350M-Base` for three epochs at `3e-5` with the same ordered mixture and disclosed
  publisher settings. Save/evaluate every epoch, target only the ten relevant failures, and never
  use either committed diagnostic corpus as training data.

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
- [ ] Complete the approved LFM2.5-350M correction-repair and clean-base comparison before
  returning to the deferred Qwen3.5-0.8B alternative.
- [ ] Quantize the best checkpoint and re-run seed, regression, and blind-v2 quality gates with the
  same short output bound and non-thinking behavior.

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
- [ ] Define a fixed, repeatable dictation corpus covering conversational speech, protected names,
  numbers, corrections, technical terms, paths/versions, pauses, commands/questions, and longer
  utterances. Score protected-token preservation and numeric equivalence separately from WER.
- [ ] Integrate Parakeet Q4_K streaming/end-of-utterance behind `SpeechToTextEngine` without
  weakening the project-owned microphone lifecycle; measure partial responsiveness and
  Stop-to-final latency.
- [ ] Verify cold load, offline model reuse, sustained thermal behavior, and live dictation memory.
- [ ] Compare Pixel's on-device `SpeechRecognizer` only if its offline path can be made deterministic.
- [ ] Make the final STT choice after the dictation/streaming gate; the read-speech probe is not
  sufficient by itself.

This remains required before final product selection, but it is not the current bottleneck.

## Diagnostic joined pipeline

- [x] Feed the completed Parakeet transcript into a swappable cleanup engine automatically.
- [x] Convert and sideload the pinned public Sotto LFM2.5-350M checkpoint as Q4_K_M without
  committing model artifacts.
- [x] Display raw STT, complete unguarded model output, and guarded cleanup simultaneously.
- [x] Report STT tail, cleanup TTFT, cleanup total, and end-to-end tail.
- [x] Keep both models warm between utterances while releasing the microphone at Stop.
- [x] Run one real Pixel microphone → Parakeet → Sotto smoke test and preserve sanitized timing and
  fallback evidence.
- [ ] Replace the public Sotto model identity with the best correction-repair checkpoint only after
  its raw output passes the independent quality/safety gates.
- [ ] Run the fixed cleanup evaluation and sustained dictation checks on that qualified quantized
  checkpoint before calling the joined pipeline deployable.

## After the joined pipeline

1. Implement the minimal voice-only `InputMethodService`.
2. Add daily-driver lifecycle, cancel/undo, interruptions, sensitive fields, and polish.
