# Local On-Device Dictation for Android — Coding Agent Context

_Last verified: 2026-08-17_

## 0. What this document is

This is the implementation context for a coding agent building a **fully local Android dictation keyboard** for a **Google Pixel 7**.

The product idea is similar to **Wispr Flow / FluidVoice**:

1. User taps or holds a microphone button.
2. Speech is transcribed locally on the phone.
3. A small local language model cleans the transcript:
   - remove filler words
   - apply obvious self-corrections
   - fix punctuation/capitalization
   - turn rambling spoken phrasing into clean written text
   - preserve meaning and avoid inventing information
4. The cleaned text is inserted into whatever Android text field currently has focus.
5. The normal path must work **with the phone offline**.

The user develops on a **MacBook** and has little recent Android-development experience. The coding agent should therefore take ownership of setting up the Android toolchain, explaining any one-time phone setup, building the APK, installing/running it on the Pixel 7, and keeping the build process reproducible from the command line.

The target is initially a **personal sideloaded app**, not a Play Store product.

## Current project override — 2026-08-17

This document began as the bootstrap plan. When resuming implementation, treat
`docs/project/CURRENT_STATE.md`, `docs/project/NEXT_STEPS.md`, and
`docs/project/DECISIONS.md` as the authoritative current sequence.

The active bottleneck is **cleanup**, not STT:

- The working offline Moonshine capture/transcription path is provisionally adequate for
  prototyping. Formal STT comparison is deferred; this is not a final STT selection.
- Liquid 230M/350M/1.2B, five generic cross-family models, and the public task-tuned VoiceInk
  Qwen3.5-2B checkpoint all failed the cleanup semantic/correction gate.
- VoiceInk was screened with its exact author prompt: 38/69 raw exact, only 2/10 corrections exact,
  six retained superseded edits, three meaning/fact changes, and one followed instruction.
- Cleanup remains separate from STT and must not be integrated until a raw-output quality survivor
  passes a new blind evaluation.
- The next model path is a leakage-isolated Qwen3 0.6B versus Qwen3.5 0.8B task-specific pilot.
  Dataset schema, validation, provenance, and contamination checks are implemented.
- **Do not train on this Mac.** Prepare portable data/tooling here and run LoRA/QLoRA later on the
  separate training machine.

The earlier Liquid-first recommendations below are historical starting assumptions. Their measured
no-go outcomes are preserved in `docs/evaluation/results/` and supersede them.

---

# 1. Product goal

Build an Android **IME (Input Method Editor)** that acts primarily as a voice keyboard.

Conceptually:

```text
┌────────────────────────────────────┐
│ Android IME / voice keyboard       │
│                                    │
│              🎙                    │
│          Hold / tap to talk        │
└─────────────────┬──────────────────┘
                  │
                  ▼
          streaming local STT
                  │
                  ▼
             raw transcript
                  │
                  ▼
        small local cleanup LLM
                  │
                  ▼
           cleaned transcript
                  │
                  ▼
      InputConnection.commitText()
                  │
                  ▼
 WhatsApp / Messages / Gmail / Notes /
 browser / any normal Android text field
```

The core experience should feel like:

```text
spoken:
"uh can you send that to Sarah actually no send it to James tomorrow
morning and um tell him I'll look at the numbers later"

raw STT:
"uh can you send that to Sarah actually no send it to James tomorrow
morning and um tell him I'll look at the numbers later"

clean:
"Can you send that to James tomorrow morning and tell him I'll look at
the numbers later?"
```

The system should be conservative. If the cleanup model is uncertain, preserving the raw wording is preferable to hallucinating or changing the meaning.

---

# 2. Primary target device

**Google Pixel 7**
- Tensor G2
- 8 GB RAM
- ARM64
- modern Android with support for API 31+ features

This is the only device that needs to be optimized initially.

Do **not** prematurely optimize for every Android device.

A Pixel-7-first implementation lets us:
- use ARM64-only native dependencies if needed
- use Android 12+ APIs
- benchmark one known device
- aggressively compare local runtimes
- postpone compatibility work

---

# 3. Recommended V1 technical stack

## Preferred starting stack

### STT
**Moonshine Voice — Small Streaming English, 123M parameters**

Why:
- designed specifically for live speech rather than bulk transcription
- streaming model does work while speech is being spoken
- open-source
- official Android integration exists
- ships through Maven
- current project has Android examples
- much smaller than Parakeet 0.6B
- a good accuracy/latency compromise

Current Moonshine model options worth testing:

| Model | Params | Role |
|---|---:|---|
| Tiny Streaming | 34M | latency/minimum footprint baseline |
| **Small Streaming** | **123M** | **recommended default** |
| Medium Streaming | 245M | accuracy-oriented experiment |

Moonshine's own published Open ASR average WER numbers currently list:
- Tiny Streaming: 12.00%
- Small Streaming: 7.84%
- Medium Streaming: 6.65%

These are not Pixel 7 performance measurements. Benchmark the actual phone.

Official repo:
https://github.com/moonshine-ai/moonshine

Official docs:
https://moonshine-voice.readthedocs.io/

As of this document, Moonshine publishes an Android Maven package and a downloadable Android Transcriber example. **Do not blindly pin the version written in this document. Check the current repo/example and use the latest compatible stable release.**

---

### Cleanup model
Start by benchmarking:

1. **Liquid LFM2.5-230M**
2. **Liquid LFM2.5-350M**

Prefer 230M for the first vertical slice because dictation cleanup is a small, tightly constrained transformation task.

Use **Liquid LEAP** on Android first rather than introducing custom llama.cpp JNI glue unless LEAP becomes a blocker.

Official LEAP docs:
https://docs.liquid.ai/deployment/on-device/sdk/quick-start

Official Liquid model pages:
https://www.liquid.ai/models

LFM2.5-230M announcement/details:
https://www.liquid.ai/blog/lfm2-5-230m

LFM2.5-350M docs:
https://docs.liquid.ai/lfm/models/lfm25-350m

At verification time, LEAP's current documented Android requirements include:
- arm64-v8a device
- 3 GB+ RAM
- minSdk 31
- physical device recommended
- emulator may crash while loading model bundles
- current SDK documented as 0.10.7

Treat those versions as moving targets and verify before implementation.

---

# 4. Important architecture decision: do NOT begin by building the keyboard

There are two independent difficult areas:

1. Native/on-device ML runtime integration.
2. Android IME lifecycle and UX.

Do not debug both simultaneously.

Use this implementation sequence.

## Phase A — ordinary Android test app

Make a normal Android Activity with:

```text
[Load models]

[Hold to talk]

Raw:
...

Clean:
...

STT latency:
...
Cleanup latency:
...
Total end-of-speech latency:
...
```

Success criteria:
- runs on the Pixel 7
- airplane mode works after models are present
- Moonshine can stream microphone speech
- cleanup model can rewrite a transcript
- instrumentation exposes useful latency/memory numbers

Only after this works should the project become an IME.

## Phase B — voice-only IME

Create an `InputMethodService` with a very simple view:

```text
┌─────────────────────────────┐
│                             │
│             🎙              │
│                             │
│        Tap to dictate       │
│                             │
│        Cancel      Undo     │
└─────────────────────────────┘
```

No QWERTY keyboard is required for V1.

The user can switch back to Gboard when normal typing is needed.

This keeps the initial product tiny and lets us test whether the voice workflow is actually good.

## Phase C — polish

Only after V1 feels useful:
- provisional transcript
- automatic end-of-speech
- undo
- alternate cleanup modes
- text-selection rewrite
- better model lifecycle
- status/error UI
- model management
- optional normal keyboard layer

---

# 5. Android development on macOS: what the coding agent should set up

The Android development environment is straightforward on macOS now.

## Install Android Studio

Use the latest stable Android Studio from:

https://developer.android.com/studio

Installation guide:

https://developer.android.com/studio/install

Android Studio is the official IDE and bundles/manages:
- Android SDK
- SDK Platform Tools
- adb
- Android Gradle tooling
- emulator
- build/debug integration

Use the **Apple Silicon** build if the MacBook is Apple Silicon.

Prefer Android Studio's bundled JDK unless a dependency specifically requires something else.

## Initial SDK setup

The agent should ensure these are installed through Android Studio's SDK Manager:
- a current Android SDK platform suitable for the selected `compileSdk`
- Android SDK Build-Tools
- Android SDK Platform-Tools
- Android SDK Command-line Tools

If LEAP still requires `targetSdk = 36`, follow the current LEAP documentation rather than this document.

## Project language

Use:
- Kotlin
- Gradle Kotlin DSL (`build.gradle.kts`)
- a single app module initially

Compose is optional. For the benchmark Activity, Compose is convenient. For the IME input view, either Compose or normal Views is acceptable; choose whichever causes less IME-specific friction.

Do not introduce elaborate architecture frameworks.

---

# 6. Pixel 7 developer setup

Official guide:
https://developer.android.com/studio/run/device

Developer options guide:
https://developer.android.com/studio/debug/dev-options

On the Pixel:

1. Open **Settings → About phone → Build number**.
2. Tap Build number seven times to enable Developer options.
3. Open Developer options.
4. Enable **USB debugging**.
5. Connect the phone to the Mac via USB.
6. Accept the RSA debugging prompt on the phone.

macOS requires **no special USB driver** for adb.

Verify:

```bash
adb devices
```

The device should appear as `device`, not `unauthorized`.

Android 11+ also supports wireless adb. USB is simpler initially; wireless debugging can be set up later.

---

# 7. Build / install / run loop

The coding agent should make the project usable both from Android Studio and from the terminal.

## From Android Studio

For normal development:
- select the Pixel 7 as the run target
- click Run
- Android Studio builds and installs the debug app via adb

## From the terminal

From the repository root:

```bash
./gradlew assembleDebug
```

The APK will normally be under:

```text
app/build/outputs/apk/debug/app-debug.apk
```

Install/update via adb:

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

For logs:

```bash
adb logcat
```

Prefer adding a distinctive log tag such as:

```text
LocalFlow
```

so debugging can use:

```bash
adb logcat | grep LocalFlow
```

or the appropriate modern `adb logcat` filtering syntax.

## Important APK distinction

Android Studio's Run action may produce a `testOnly` APK intended for adb installation.

If the user wants a **debug APK that can be copied to the phone and tapped in Files to install**, use Android Studio:

```text
Build → Build Bundle(s) / APK(s) → Build APK(s)
```

or verify that the Gradle-built debug APK is installable in the intended way.

For long-term manual sharing/sideloading, eventually create a signed release APK.

Official build docs:
https://developer.android.com/build/build-for-release

Command-line build docs:
https://developer.android.com/build/building-cmdline

adb:
https://developer.android.com/tools/adb

---

# 8. Android IME basics

Official guide:
https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method

The core class is:

```kotlin
class LocalFlowImeService : InputMethodService()
```

An IME is an Android app containing an `InputMethodService`.

The system lets the user enable and select it as a keyboard.

Text is inserted into the focused editor through:

```kotlin
currentInputConnection
```

For example:

```kotlin
currentInputConnection?.commitText(cleanedText, 1)
```

This is the correct system-wide integration.

Do **not** use AccessibilityService hacks for ordinary insertion.

The IME should declare the service correctly in `AndroidManifest.xml` and include the required input-method metadata XML.

The coding agent should use the current Android IME documentation rather than old tutorials based around deprecated `KeyboardView` patterns unless useful as a reference.

---

# 9. Suggested internal software architecture

Keep model implementations behind interfaces so they can be swapped easily.

Example:

```kotlin
interface SpeechToTextEngine {
    suspend fun load()
    suspend fun start()
    suspend fun stop(): SttResult
    suspend fun unload()
}

data class SttResult(
    val text: String,
    val startedAtNs: Long,
    val speechEndedAtNs: Long?,
    val finalTextAtNs: Long,
)

interface CleanupEngine {
    suspend fun load()
    suspend fun clean(text: String): CleanupResult
    suspend fun unload()
}

data class CleanupResult(
    val rawText: String,
    val cleanedText: String,
    val startedAtNs: Long,
    val firstTokenAtNs: Long?,
    val completedAtNs: Long,
)
```

Implementations:

```text
SpeechToTextEngine
├── MoonshineSttEngine
└── AndroidOnDeviceSpeechRecognizerEngine   (experiment)

CleanupEngine
├── Liquid230MCleanupEngine
├── Liquid350MCleanupEngine
└── NoOpCleanupEngine                       (baseline)
```

Then:

```kotlin
class DictationPipeline(
    private val stt: SpeechToTextEngine,
    private val cleanup: CleanupEngine,
)
```

The UI and IME should not care which model is selected.

---

# 10. Moonshine integration path

Start from Moonshine's **official Android Transcriber sample**, not from scratch.

Current repo:
https://github.com/moonshine-ai/moonshine

The current README provides a downloadable Android Transcriber project and documents a Maven dependency.

The agent should:

1. Download/open the official Android example.
2. Build it unchanged first.
3. Run it on the Pixel 7.
4. Confirm live microphone transcription.
5. Confirm it works in airplane mode.
6. Copy the minimum required integration into this project.

Do not begin by rebuilding Moonshine native libraries from C++ source.

Use the prebuilt Android/Maven integration first.

Moonshine uses ONNX Runtime internally and supplies on-device quantized models.

## Starting STT model

Use:

```text
English Small Streaming — 123M
```

unless integration friction makes Tiny easier for the first smoke test.

After correctness:
- benchmark Tiny Streaming
- benchmark Small Streaming
- optionally benchmark Medium Streaming

The useful measurement is not just real-time factor. Measure:

```text
speech end
    ↓
final STT result delivered
```

because that determines perceived dictation latency.

---

# 11. Alternative STT branch: Android's built-in on-device SpeechRecognizer

Android provides:

```kotlin
SpeechRecognizer.isOnDeviceRecognitionAvailable(context)
SpeechRecognizer.createOnDeviceSpeechRecognizer(context)
```

These APIs exist from API 31.

Official reference:
https://developer.android.com/reference/android/speech/SpeechRecognizer

This should be implemented as a **benchmark branch**, not necessarily the primary architecture.

Why test it:
- zero bundled STT model
- potentially excellent Pixel-specific optimization
- Android/Google manages model memory
- minimal app size
- potentially very low energy use

Why not make it the only path immediately:
- exact behavior can vary by OS/device/language model availability
- less control
- portability is weaker
- internal recognizer/model can change across OS updates
- harder to guarantee a known reproducible model

We care about empirical results.

A/B test:

```text
A: Moonshine Small Streaming → LFM cleanup
B: Pixel on-device SpeechRecognizer → LFM cleanup
```

Use whichever is better on the actual Pixel 7.

The project design should make this a runtime toggle.

---

# 12. Alternative STT branch: Parakeet

If Moonshine quality is inadequate, benchmark **NVIDIA Parakeet 0.6B INT8** through sherpa-onnx.

This is likely larger/heavier than Moonshine Small but may provide better recognition quality in some conditions.

Sherpa-onnx:
https://github.com/k2-fsa/sherpa-onnx

Docs:
https://k2-fsa.github.io/sherpa/onnx/

This is an experiment, not the V1 starting point.

Do not add it before Moonshine and Android on-device SpeechRecognizer have been measured.

---

# 13. Cleanup model integration with Liquid LEAP

Official LEAP quick start:
https://docs.liquid.ai/deployment/on-device/sdk/quick-start

At verification time the Android Gradle dependencies were documented roughly as:

```kotlin
dependencies {
    implementation("ai.liquid.leap:leap-sdk:<current-version>")
    implementation("ai.liquid.leap:leap-model-downloader:<current-version>")
}
```

The current docs at the time of writing showed version `0.10.7`.

**Agent instruction: verify the latest compatible version before pinning dependencies.**

LEAP currently documents:
- `minSdk = 31`
- ARM64 device
- 3 GB+ RAM
- Android model downloader
- model caching
- support for sideloaded GGUF if needed

Prefer the LEAP model downloader if the desired LFM2.5 model/quantization is present in the LEAP model library.

If LFM2.5-230M is not exposed by the current LEAP library:
1. check current LEAP docs/model catalog
2. use LEAP's supported sideloaded GGUF path if possible
3. only then consider direct llama.cpp integration

## Models to compare

Primary:
```text
LFM2.5-230M
```

Secondary:
```text
LFM2.5-350M
```

Quantization:
- start with a supported Q4-ish quantization
- benchmark Q4_K_M or the closest LEAP-supported equivalent
- do not assume a specific quant type is available without checking

The task is simple enough that quality differences should be tested using actual dictation examples rather than generic benchmarks.

---

# 14. Cleanup prompt

Start with a short deterministic instruction.

Something like:

```text
You clean voice dictation into written text.

Rules:
- Preserve the speaker's meaning.
- Apply obvious self-corrections.
- Remove filler words and abandoned false starts.
- Fix punctuation and capitalization.
- Keep the speaker's tone.
- Do not add facts or ideas.
- Do not answer the text.
- If uncertain, preserve the original wording.
- Output only the cleaned text.

Dictation:
{{TRANSCRIPT}}
```

Avoid long system prompts. Prefill latency matters.

Use low/randomness-free generation:
- temperature 0 if supported
- otherwise minimum practical temperature
- no sampling where possible
- short max output length derived from input length

The output should generally not be dramatically longer than the input.

## Guardrails

Before committing:
- trim whitespace
- reject empty output
- detect pathological output expansion
- optionally fall back to raw STT if output is suspicious

Example heuristic:

```text
if cleaned length > 1.8 × raw length:
    use raw text
```

This is only a starting heuristic; tune empirically.

A future improvement is constrained generation or task-specific fine-tuning, but do not start there.

---

# 15. Build a dictation cleanup evaluation set early

Generic LLM benchmarks are not enough.

Create a small local JSON/JSONL corpus of 50–100 dictation examples covering:

### filler words

```text
"uh I think we should um probably send it tomorrow"
```

### false starts

```text
"send it on Tuesday actually make that Thursday"
```

### repeated words

```text
"can you can you send me the link"
```

### punctuation

```text
"hey James I got the file thanks I'll look tonight"
```

### conversational tone

```text
"yeah that sounds good to me let's do it"
```

### names

```text
"send it to Sébastien and Mariko"
```

### technical language

Use terms relevant to the user's real dictation.

### cases that should barely change

```text
"The benchmark completed in 237 milliseconds."
```

### cases where the model must not answer

```text
"what time should we meet tomorrow"
```

Expected output is cleaned dictation:

```text
"What time should we meet tomorrow?"
```

not an answer to the question.

This test set should be runnable independently against:
- no cleanup
- LFM2.5-230M
- LFM2.5-350M
- any future model

Track:
- meaning preservation
- filler removal
- false-start correction
- punctuation
- hallucination rate
- subjective preference

---

# 16. Latency metrics that matter

Instrument every stage with `SystemClock.elapsedRealtimeNanos()`.

At minimum record:

```text
mic_start
speech_end / stop_pressed
stt_final
cleanup_start
cleanup_first_token
cleanup_final
text_committed
```

Report:

```text
STT tail latency =
    stt_final - speech_end

cleanup TTFT =
    cleanup_first_token - cleanup_start

cleanup total =
    cleanup_final - cleanup_start

end-to-end tail =
    text_committed - speech_end
```

For tap-to-stop V1, use the button release / stop tap as the initial proxy for `speech_end`.

Important target:

```text
speech end → final committed clean text
```

Ideally this should feel comfortably below one second when warm.

Do not invent a hard requirement until measured on Pixel 7.

---

# 17. Cold start vs warm start

Measure separately.

## Cold
- app/IME process started
- models not loaded
- first dictation

## Warm
- model already in memory
- subsequent dictation

Daily usability is mostly about warm latency.

Model loading should not happen on every utterance.

Recommended lifecycle concept:

```text
IME/service starts
    ↓
load STT when practical

user dictates
    ↓
STT active

raw transcript ready
    ↓
cleanup model loaded/kept warm
    ↓
clean

several minutes idle
    ↓
consider unloading cleanup model

longer idle / memory pressure
    ↓
release STT too
```

Do not implement aggressive unloading before profiling.

Repeated model loading may cost more energy and latency than keeping a few hundred MB resident.

---

# 18. Battery and thermal testing

Battery is expected to be manageable because this is push-to-talk, not always-listening.

Still measure.

Useful experiments:
- 20 short dictations in 5 minutes
- 10 one-minute dictations
- repeated cleanup runs
- airplane mode
- screen-on normal usage
- device temperature before/after

Watch:
- process RSS
- CPU utilization
- thermal throttling
- battery percentage / batterystats if useful

Do not spend significant time on micro-optimization until end-to-end latency is known.

The likely first-order question is:
**Does Tensor G2 run these models quickly enough for the UX?**

---

# 19. V1 interaction design

Use one of these two modes.

## Mode A: tap to start, tap to stop

Recommended first.

```text
tap mic
→ recording

tap again
→ stop
→ finalize STT
→ cleanup
→ insert
```

This is easiest to debug.

## Mode B: hold to talk

Add after basic operation.

```text
ACTION_DOWN
→ start

ACTION_UP
→ stop/finalize
```

Do not initially depend on voice-activity detection for ending the utterance.

Moonshine already has voice/VAD-related facilities, but explicit user stop gives a cleaner V1.

---

# 20. Provisional text: postpone

Do not initially insert streaming partial transcripts into the destination app.

V1:

```text
speak
→ process
→ commit final cleaned sentence once
```

Why:
- no partial replacement bookkeeping
- no cursor race conditions
- no app-specific composition behavior
- cleanup can operate on the complete utterance

Later, if desired:
- display live raw text inside the IME UI only
- after stop, clean it
- then commit the final result once

Only after that consider composing/provisional text directly in the host editor.

---

# 21. Undo behavior

This becomes important quickly.

Before inserting text, capture enough information to undo the most recent insertion.

Simplest V1:
- store last committed string
- Undo button calls `deleteSurroundingText()` only if cursor/context matches expectations

Do not blindly delete by character count if the user has moved the cursor or edited text.

A conservative undo is better than corrupting existing text.

---

# 22. Privacy requirement

The core promise is local operation.

Once models are downloaded:
- STT must not require a network call
- cleanup must not require a network call
- speech audio must not be uploaded
- transcript must not be uploaded

Add an **airplane-mode acceptance test**.

Networking may be used only for:
- first-run model downloads
- optional update checks in future

Do not add analytics in V1.

Do not add cloud fallbacks without explicit user opt-in.

---

# 23. Model download strategy

For the first developer build, bundling models with the APK/assets may be acceptable if it gets the prototype working.

But very large APKs become annoying.

Preferred eventual behavior:

```text
APK installs
    ↓
setup screen
    ↓
Download STT model
Download cleanup model
    ↓
checksum/validate
    ↓
ready
```

Both Moonshine and LEAP have model/downloader support that should be evaluated before writing custom download code.

The user cares more about getting a working APK than Play Store packaging at this stage.

---

# 24. Permissions / security-sensitive fields

Expected permissions may include:

```xml
<uses-permission android:name="android.permission.RECORD_AUDIO" />
```

LEAP's model downloader may currently require permissions such as:
- INTERNET
- POST_NOTIFICATIONS
- FOREGROUND_SERVICE
- FOREGROUND_SERVICE_DATA_SYNC

Follow the **current** LEAP docs; do not cargo-cult old manifest snippets.

The IME should avoid dictation in password/sensitive fields where appropriate.

Inspect `EditorInfo.inputType` and Android IME security guidance.

Never retain password-field surrounding text.

---

# 25. IME onboarding

After installing an IME, Android requires the user to enable/select it.

Provide a small launcher/settings Activity with:
- status: models installed / not installed
- test microphone
- STT engine selection
- cleanup model selection
- button to open Android input-method settings
- button/instructions to switch keyboards
- benchmark results

This Activity is useful even when the main product is an IME.

The app should not launch into a mysterious blank screen.

---

# 26. Configuration toggles to build early

A developer/settings screen should expose:

## STT engine
```text
Moonshine Tiny Streaming
Moonshine Small Streaming
Moonshine Medium Streaming
Android On-Device SpeechRecognizer
```

Medium can be hidden until integrated.

## Cleanup
```text
None
LFM2.5-230M
LFM2.5-350M
```

## Cleanup mode
Start with one mode:
```text
Natural cleanup
```

Later:
```text
Minimal
Natural
Concise
```

Do not build multiple prompts before the base model is benchmarked.

---

# 27. FluidVoice relationship

FluidVoice is useful as **product/architecture inspiration**, not as the Android codebase.

Repository:
https://github.com/altic-dev/FluidVoice

Why not port it literally:
- macOS-specific application architecture
- Swift
- Apple audio/UI/accessibility APIs
- Apple-specific model/runtime paths
- Android IME behavior is fundamentally different

Also note licensing:

As of 2026-02-23, current FluidVoice is GPLv3. Older published versions were Apache 2.0.

If code is copied from the current FluidVoice project, GPL obligations become relevant.

For this project:
- prefer independent Android implementation
- borrow interaction ideas/concepts
- inspect algorithms/orchestration where useful
- avoid copying large source sections unless intentionally accepting GPLv3 for the project

FluidVoice's proprietary/custom enhancement model is not something we can simply port and reuse.

---

# 28. Suggested repository structure

Keep it simple.

```text
local-flow-android/
├── README.md
├── AGENT_CONTEXT.md
├── app/
│   ├── build.gradle.kts
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/.../
│       │   ├── MainActivity.kt
│       │   ├── ime/
│       │   │   └── LocalFlowImeService.kt
│       │   ├── pipeline/
│       │   │   ├── DictationPipeline.kt
│       │   │   ├── PipelineMetrics.kt
│       │   │   └── PipelineState.kt
│       │   ├── stt/
│       │   │   ├── SpeechToTextEngine.kt
│       │   │   ├── MoonshineSttEngine.kt
│       │   │   └── AndroidSpeechRecognizerEngine.kt
│       │   ├── cleanup/
│       │   │   ├── CleanupEngine.kt
│       │   │   ├── LiquidCleanupEngine.kt
│       │   │   └── NoOpCleanupEngine.kt
│       │   ├── model/
│       │   │   └── ModelManager.kt
│       │   └── settings/
│       │       └── ...
│       └── res/
├── eval/
│   ├── dictation_cases.jsonl
│   └── README.md
└── scripts/
    ├── build-debug.sh
    ├── install-debug.sh
    └── logs.sh
```

Do not split into multiple Gradle modules until there is a concrete benefit.

---

# 29. Recommended first milestones

## Milestone 0 — toolchain

Agent must demonstrate:

```bash
./gradlew assembleDebug
adb devices
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

and launch a hello-world Activity on the Pixel 7.

Deliver:
- reproducible README setup instructions
- no manual mystery steps left undocumented

## Milestone 1 — Moonshine smoke test

Normal Activity:
- request microphone permission
- start/stop transcription
- display raw text
- log latency
- work offline

Do not integrate LLM yet.

## Milestone 2 — Liquid smoke test

Normal Activity:
- load LFM2.5-230M
- text box accepts raw transcript manually
- button produces clean transcript
- log load time, TTFT, total generation time, memory if practical
- work offline after model is present

## Milestone 3 — joined pipeline

```text
microphone
→ Moonshine
→ LFM2.5-230M
→ cleaned text
```

UI displays raw + clean text and all timing metrics.

This is the first major go/no-go checkpoint.

## Milestone 4 — model A/B

Benchmark:
- Moonshine Tiny vs Small
- LFM 230M vs 350M
- Android built-in on-device STT vs Moonshine Small

Choose defaults based on the Pixel 7, not theory.

## Milestone 5 — IME

Add `InputMethodService`.

Voice-only IME:
- start
- stop
- processing indication
- commit clean text
- cancel
- basic errors

## Milestone 6 — daily-driver polish

- model warm lifecycle
- undo
- model setup UI
- robust process recreation
- audio interruptions
- Bluetooth mic
- empty-result handling
- long utterances
- sensitive input fields
- keyboard switch affordance

---

# 30. Go/no-go benchmark criteria

Before spending time on UI polish, collect actual Pixel 7 results for at least 20 normal utterances.

Record:

```text
model load time
peak-ish process memory
STT tail latency
cleanup TTFT
cleanup total latency
end-to-end tail latency
subjective cleanup quality
```

Questions to answer:

1. Is Moonshine Small accurate enough?
2. Is Android built-in STT better on this specific Pixel?
3. Does LFM2.5-230M correctly handle false starts?
4. Is 350M materially better?
5. Does the warm end-to-end latency feel instant enough?
6. Does sustained use make the Pixel uncomfortable/hot?
7. Does airplane-mode use work reliably?

If LFM2.5-230M is weak:
- try 350M
- improve prompt
- add few-shot examples only if necessary
- investigate a task-specific fine-tune later

Do **not** jump immediately to a multi-billion-parameter model.

---

# 31. Potential implementation branches

## Branch A — recommended

```text
Moonshine Small Streaming
→ LFM2.5-230M LEAP
→ IME
```

Expected best balance.

## Branch B — smallest

```text
Moonshine Tiny Streaming
→ LFM2.5-230M
```

Use if battery/thermal/latency strongly favor it and recognition quality is still acceptable.

## Branch C — accuracy

```text
Moonshine Medium Streaming
→ LFM2.5-350M
```

Use if Pixel 7 performance remains good.

## Branch D — Pixel-optimized

```text
Android createOnDeviceSpeechRecognizer()
→ LFM2.5-230M
```

Potentially excellent because Google owns the STT runtime/model.

Must be tested rather than assumed.

## Branch E — heavier STT

```text
Parakeet 0.6B INT8 / sherpa-onnx
→ LFM2.5-230M
```

Only if Moonshine recognition quality is clearly insufficient.

## Branch F — direct audio-language model

Liquid has LFM2.5 Audio models around 1.5B that can consume audio directly.

Interesting future experiment:

```text
audio
→ audio-language model
→ cleaned text
```

Do not use as V1 on the Pixel 7 unless evidence shows it is superior. A separate streaming STT + tiny cleanup model is easier to debug and probably more thermally friendly.

---

# 32. Things NOT to do in V1

Do not:
- build a complete replacement QWERTY keyboard
- use cloud APIs
- implement account/login
- implement subscriptions
- optimize for Play Store distribution
- support ten languages
- fine-tune a model before benchmarking prompts
- write a custom C++ runtime before trying official Android SDKs
- implement accessibility-based text insertion
- implement always-on listening
- implement elaborate VAD behavior before tap-to-stop works
- insert live provisional text into third-party apps
- create a complex dependency-injection framework
- spend days on visual design before model latency is measured

---

# 33. Testing checklist

## Basic app
- fresh install
- microphone permission accepted
- microphone permission denied
- model download succeeds
- download interrupted/restarted
- airplane mode after download
- app process killed/restarted

## Speech
- 2-second utterance
- 10-second utterance
- 60-second utterance
- silence
- background noise
- fast speech
- filler-heavy speech
- self-correction
- names
- technical vocabulary

## IME
- Messages
- Gmail
- browser text field
- Notes/Keep-like app
- multiline field
- single-line field
- cursor in middle of existing text
- keyboard switching
- screen rotation
- host app backgrounded
- incoming call/audio interruption
- Bluetooth headset microphone
- password field

## Offline/privacy
- airplane mode
- no network permissions except those required for model setup/downloader
- inspect logs for accidental transcript persistence

---

# 34. Developer ergonomics

The coding agent should leave behind scripts so the human does not need to remember Android incantations.

Example:

`scripts/build-debug.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
./gradlew assembleDebug
echo "APK: app/build/outputs/apk/debug/app-debug.apk"
```

`scripts/install-debug.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

`scripts/logs.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
adb logcat | grep --line-buffered LocalFlow
```

Adjust for macOS tool availability; avoid requiring GNU-only utilities without documenting Homebrew dependencies.

---

# 35. README expectations

The repository README should explain, from zero:

## On Mac
1. install Android Studio
2. clone repository
3. open repository
4. let Gradle sync
5. connect Pixel
6. verify `adb devices`
7. build/run

## On Pixel
1. enable Developer options
2. enable USB debugging
3. authorize Mac
4. install app
5. grant microphone permission
6. download models
7. enable the new keyboard in Android settings
8. select keyboard
9. dictate

Also document the pure command-line route.

---

# 36. Useful official references

## Android

Android Studio:
https://developer.android.com/studio

Install Android Studio:
https://developer.android.com/studio/install

Run on physical device:
https://developer.android.com/studio/run/device

Developer options:
https://developer.android.com/studio/debug/dev-options

Create an IME:
https://developer.android.com/develop/ui/views/touch-and-input/creating-input-method

InputMethodService:
https://developer.android.com/reference/android/inputmethodservice/InputMethodService

SpeechRecognizer:
https://developer.android.com/reference/android/speech/SpeechRecognizer

adb:
https://developer.android.com/tools/adb

Command-line builds:
https://developer.android.com/build/building-cmdline

Build APK/release:
https://developer.android.com/build/build-for-release

## Moonshine

Repository:
https://github.com/moonshine-ai/moonshine

Documentation:
https://moonshine-voice.readthedocs.io/

The repository contains runnable Android examples. Begin there.

## Liquid AI

LEAP quick start:
https://docs.liquid.ai/deployment/on-device/sdk/quick-start

Liquid models:
https://www.liquid.ai/models

LFM2.5-230M:
https://www.liquid.ai/blog/lfm2-5-230m

LFM2.5-350M:
https://docs.liquid.ai/lfm/models/lfm25-350m

## FluidVoice inspiration

https://github.com/altic-dev/FluidVoice

Current FluidVoice is GPLv3. Treat it as architecture/product inspiration unless intentionally accepting the license implications of copying source.

---

# 37. Agent operating instructions

The coding agent should behave experimentally rather than assuming benchmark claims transfer to the Pixel 7.

For every major dependency:
1. check current official documentation
2. use the latest stable compatible version
3. pin it in Gradle
4. record the version in README
5. get the vendor's sample working before writing custom wrappers

Prefer a working vertical slice over architectural elegance.

When blocked by an SDK:
- isolate the failing component
- build the vendor sample
- confirm whether the problem reproduces there
- only then replace the runtime

Do not silently switch to cloud APIs.

Do not silently use a larger model.

Do not change the offline/privacy requirement.

Keep commits small and milestone-oriented.

---

# 38. First concrete task for the coding agent

Start here.

1. Create a Kotlin Android project targeting the Pixel 7 with `minSdk >= 31`.
2. Confirm the project builds on macOS.
3. Confirm `adb devices` sees the Pixel.
4. Install and launch the app on the Pixel.
5. Add a simple benchmark Activity.
6. Integrate the current official Moonshine Android Transcriber sample/library.
7. Get **Moonshine Small Streaming English** microphone transcription working.
8. Show raw text and measure finalization latency.
9. Verify it works in airplane mode.
10. Commit this as the first working milestone.
11. Only then add Liquid LEAP and LFM2.5-230M cleanup.

The first meaningful output from the agent should therefore be:

```text
Pixel 7 microphone
→ Moonshine Small Streaming
→ raw transcript displayed locally
```

not a polished keyboard.

After that succeeds, the next meaningful output is:

```text
Pixel 7 microphone
→ Moonshine Small Streaming
→ LFM2.5-230M
→ cleaned transcript
```

Then build the IME.

---

# 39. Definition of V1 success

V1 is successful when:

- the app installs on the Pixel 7
- the user can select it as an Android input method
- tapping the mic starts local dictation
- tapping stop produces a transcript
- local cleanup removes common filler/false starts and fixes writing
- the final text is inserted into the current app
- normal use works with airplane mode enabled after model setup
- warm latency is acceptable for daily use
- the device does not become unreasonably hot during ordinary dictation
- there is a clear way to cancel and switch keyboards
- build/install instructions are documented well enough that a non-Android-specialist Mac user can rebuild the APK later

That is enough.

Everything else is V2.
