# Next steps

Last updated: 2026-08-17

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
raw transcripts while cleanup quality is solved. Keep the stages unjoined until cleanup passes.

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

Prepare all data and training inputs portably in this repository, but run training only on the
separate training machine when it is available. Do not start training on this Mac.

- [x] Freeze a training schema for raw transcript, cleaned target, transformation labels, protected
  spans, and provenance. Never train on either committed evaluation corpus.
- [x] Select and pin public candidate sources: Sotto transcript cleanup as primary, Disfl-QA for
  question corrections, and Nyra Disfluency Speech for an audio-backed supplement. Treat every row
  as untrusted until project validation/review.
- [x] Add a self-contained RTX A6000 handoff covering environment preflight, source pins, data
  isolation, training/evaluation deliverables, monitoring, resume, artifacts, and blind-v2 rules.
- [ ] Build the pinned source fetcher, importer, conservative filter/quarantine rules,
  near-duplicate family splitter, and deterministic source manifest.
- [ ] Build a balanced, reviewable training/dev corpus covering fillers, repeats, false starts,
  explicit corrections, punctuation, commands/questions-as-data, adversarial text, names, numbers,
  uncertainty, negation, Unicode, and technical tokens.
- [ ] Prepare the blind evaluator contract early. After training templates stabilize, have an
  independent context author/double-review and seal blind v2 outside the training job's readable
  path; do not use it for checkpoint or prompt selection.
- [ ] Fine-tune the smallest practical base first (Qwen3 0.6B or Qwen3.5 0.8B), using the stronger
  task-tuned model as a teacher only when outputs pass deterministic preservation checks and human
  review.
- [ ] Quantize the best checkpoint and re-run seed, regression, and blind-v2 quality gates with the
  same short output bound and non-thinking behavior.

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

## Deferred: Milestone 5 — STT-only evaluation

- Keep cleanup unloaded and do not join the pipeline.
- Define a fixed, repeatable audio/transcript corpus covering conversational speech, names, numbers,
  corrections, technical terms, pauses, and longer dictation.
- Add file-fed audio evaluation so identical recordings can be tested without repeated speaking.
- Score word error rate, punctuation/case behavior, omissions, and finalization latency.
- Benchmark Moonshine Small first, then compare Moonshine Tiny and Pixel's on-device
  `SpeechRecognizer` if its offline path can be made deterministic.
- Record memory, thermal behavior, model load time, and offline cache behavior for each candidate.
- Select an STT engine on measured quality rather than the current interactive anecdotes.

This remains required before final product selection, but it is not the current bottleneck.

## Later: joined pipeline

- Begin only after both an STT engine and a cleanup model pass their independent fixed evaluations.
- Feed the completed Moonshine transcript into the cleanup engine.
- Display raw and cleaned text simultaneously.
- Report STT tail, cleanup TTFT, cleanup total, and end-to-end tail.
- Keep both models warm between utterances.
- Run the go/no-go cleanup evaluation set on the physical Pixel.

## After the joined pipeline

1. Implement the minimal voice-only `InputMethodService`.
2. Add daily-driver lifecycle, cancel/undo, interruptions, sensitive fields, and polish.
