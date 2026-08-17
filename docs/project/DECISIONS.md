# Decisions

Last updated: 2026-08-17

## Product and architecture

1. Build and benchmark the ordinary Activity before introducing Android IME lifecycle complexity.
2. Keep STT and cleanup implementations behind interfaces so alternatives can be benchmarked.
3. Use explicit tap-to-start/tap-to-stop for V1; automatic endpointing is later polish.
4. Preserve full offline operation after one-time model setup. Do not silently add cloud fallback.
5. Keep transcript contents out of Logcat. UI may display them locally.

## Speech recognition

1. Start with Moonshine Voice `0.1.2`, English Small Streaming architecture `4`; Moonshine's helper
   defaults to the much larger Medium model, so the architecture must be explicit.
2. Own Android audio capture in this project. `MicTranscriber.stop()` leaves its `AudioRecord`
   capture infrastructure open, which violates the required microphone lifecycle.
3. Keep the Moonshine model loaded between utterances, but create `AudioRecord` only on Start and
   stop it synchronously on Stop.
4. Treat Android's built-in on-device SpeechRecognizer as an empirical A/B candidate, not an
   assumed replacement. Pixel-specific quality and punctuation must be measured.

## Cleanup

1. Liquid LEAP `0.10.9` remains the measured Android runtime; 230M, 350M, and 1.2B-Instruct
   `Q4_K_M` are all rejected as automatic cleanup models.
2. First prove manual text cleanup independently; join STT only after the cleanup smoke test works.
3. Use deterministic, conservative generation. Preserve meaning, apply obvious self-corrections,
   remove fillers/abandoned starts, fix punctuation, never answer dictated questions, and emit only
   cleaned text.
4. Fall back to raw text for empty output or suspicious expansion (initial ceiling: 1.8× raw
   character count, subject to evaluation).
5. Treat positive anchor preservation as necessary but insufficient: copied disfluencies can score
   well, and summaries can preserve some anchors while changing intent.
6. Require zero meaning changes, zero answered instructions after guardrails, and successful explicit
   self-correction handling before joining cleanup to STT.
7. Park generic-model cleanup work after the 1.2B no-go. Continue with STT-only evaluation and
   revisit cleanup with a task-specific fine-tune or stronger acceptable model.

## Android/toolchain

1. Pixel-7-first, `arm64-v8a`, minSdk 31.
2. Use Views/XML to minimize Activity and future IME integration overhead.
3. Keep AGP 8.13.2, Gradle 8.13, Kotlin 2.3.20, API 36, and JDK 17 while those are the verified
   Liquid/Moonshine-compatible versions.
