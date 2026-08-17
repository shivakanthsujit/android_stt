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
- [ ] Commit the completed Milestone 2 harness, results, and no-go decision.

All three generic candidates failed: 230M and 350M lack capability; 1.2B remains unsafe and too slow
under stronger prompts. Cleanup model selection is parked until a task-specific fine-tune or a
stronger model with an acceptable Pixel memory/latency budget is available.

## Active next: Milestone 3 — STT-only evaluation

- Keep cleanup unloaded and do not join the pipeline.
- Define a fixed, repeatable audio/transcript corpus covering conversational speech, names, numbers,
  corrections, technical terms, pauses, and longer dictation.
- Add file-fed audio evaluation so identical recordings can be tested without repeated speaking.
- Score word error rate, punctuation/case behavior, omissions, and finalization latency.
- Benchmark Moonshine Small first, then compare Moonshine Tiny and Pixel's on-device
  `SpeechRecognizer` if its offline path can be made deterministic.
- Record memory, thermal behavior, model load time, and offline cache behavior for each candidate.
- Select an STT engine on measured quality rather than the current interactive anecdotes.

## Later: joined pipeline

- Begin only after both an STT engine and a cleanup model pass their independent fixed evaluations.
- Feed the completed Moonshine transcript into the cleanup engine.
- Display raw and cleaned text simultaneously.
- Report STT tail, cleanup TTFT, cleanup total, and end-to-end tail.
- Keep both models warm between utterances.
- Run the go/no-go cleanup evaluation set on the physical Pixel.

## After the joined pipeline

1. Revisit cleanup with a task-specific fine-tune or stronger acceptable model.
2. Build the joined pipeline only after both independent stages pass.
3. Implement the minimal voice-only `InputMethodService`.
4. Add daily-driver lifecycle, cancel/undo, interruptions, sensitive fields, and polish.
