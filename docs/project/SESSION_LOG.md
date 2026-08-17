# Session log

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
