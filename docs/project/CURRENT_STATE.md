# Current state

Last updated: 2026-08-17

## Repository

- Branch: `main`
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
- Training will run later on the separate training machine. Do not start LoRA/QLoRA training on
  this Mac; use it for authoring/validation, local inference screens, and result analysis only.

## Toolchain

- Android Studio Quail 3 / 2026.1.3 Patch 1
- Android Gradle Plugin 8.13.2
- Gradle 8.13
- Kotlin 2.3.20
- JDK 17
- compileSdk / targetSdk 36; minSdk 31
- Android Platform-Tools 37.0.1

## Resume checklist

1. Read this file and `NEXT_STEPS.md`.
2. Run `git status --short` and preserve any uncommitted work.
3. Run `./scripts/check-toolchain.sh` with the Pixel attached.
4. Run `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`.
5. Continue active Milestone 4 in `NEXT_STEPS.md`: build the reviewed training/dev corpus and freeze
   blind v2. Keep the portable training recipe ready, but run it only on the separate training
   machine.
