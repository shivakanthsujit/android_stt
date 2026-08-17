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
5. Defer the formal STT comparison while cleanup is the demonstrated blocker. The current working
   offline Moonshine path is a provisional input, not the final STT selection.

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
7. The three Liquid no-go results reject those candidates, not all small-model cleanup. Before STT
   integration, run one bounded cross-family screen: Granite 4.0 H 350M, Qwen3-0.6B no-think, and
   Gemma 3 270M, with Qwen3.5-0.8B and Gemma 3 1B reserved for a second wave.
8. Screen quality before adding a runtime to the Android app. Only models with zero semantic safety
   failures and successful self-corrections earn Pixel performance work.
9. Prefer LiteRT-LM for the first Qwen Android run and llama.cpp for GGUF/Granite portability.
   Benchmark LiteRT CPU and GPU on Pixel 7; do not assume a Tensor G2 NPU path.
10. Benchmark deterministic cleanup and a hybrid deterministic/LLM router. Comparable open Android
    keyboards show that conservative mechanical cleanup can cover common cases without generation.
11. Reject Granite 4.0 H 350M, Qwen3 0.6B, Gemma 3 270M, Qwen3.5 0.8B, and Gemma 3 1B for automatic
    cleanup after the 45-case held-out host screen. Each failed the semantic safety or explicit
    self-correction gate; guardrail fallback did not make the underlying cleanup adequate.
12. Do not add LiteRT-LM or llama.cpp to Android merely to benchmark a failed model. Quality gates
    runtime work. The next generative cleanup candidate should be task-specific rather than another
    untuned small chat model.
13. Keep the deterministic cleaner as a near-zero-latency control, not as the selected product
    cleaner: it scored 0/7 exact on held-out self-corrections.
14. Make task-specific cleanup the active milestone. First screen the public VoiceInk Qwen3.5-2B
    fine-tune as a quality probe; if it is too large or slow, use it only as a reviewed teacher and
    fine-tune a smaller Qwen base.
15. The committed 24-case and 45-case suites are regression evidence, not training data. Because
    the 45-case set informed guardrail fixes, create a new untouched blind v2 set before measuring
    any trained model's generalization.
16. A 2B model may establish achievable cleanup quality without being shippable. Android runtime
    work remains gated on both semantic quality and a mobile-appropriate quantized artifact.
17. Reject the VoiceInk Qwen3.5-2B Q4_K_M checkpoint after its exact native-prompt screen. It failed
    8/10 corrections semantically/exactly, retained superseded content six times, changed facts or
    meaning three times, and followed one dictated instruction. It is not an automatic labeler.
18. Prepare training data, validators, manifests, and runbooks on this Mac, but run LoRA/QLoRA only
    on the separate training machine. No local training job is authorized or needed now.
19. Use Sotto transcript cleanup as the primary public-data candidate, with Disfl-QA and Nyra
    Disfluency Speech as supplements. Pin immutable revisions and treat every row as untrusted;
    reject or quarantine grammar rewrites, guessed ASR corrections, unsafe deletions, and other
    policy conflicts before project splitting or training.
20. A new RTX A6000 session may build and run the documented pilot, but it must pass Gate A first,
    keep blind-v2 outside the optimization context, monitor/resume long jobs reproducibly, and keep
    datasets, weights, checkpoints, secrets, and private references out of git.

## Android/toolchain

1. Pixel-7-first, `arm64-v8a`, minSdk 31.
2. Use Views/XML to minimize Activity and future IME integration overhead.
3. Keep AGP 8.13.2, Gradle 8.13, Kotlin 2.3.20, API 36, and JDK 17 while those are the verified
   Liquid/Moonshine-compatible versions.
