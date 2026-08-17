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
