# Local Flow for Android

Local Flow is a Pixel-first, fully local dictation project. The ordinary Android benchmark app can
record microphone speech and transcribe it with **Moonshine Small Streaming English**. The active
milestone qualifies or trains a task-specific cleanup model against fixed direct-text corpora
before joining speech recognition and cleanup. The working offline STT path is provisionally
adequate for prototyping; cleanup is the current blocker.

Keeping these stages independently measurable in a normal Activity makes model quality, latency,
offline behavior, and microphone lifecycle observable before Android keyboard work is introduced.

## Current milestone

Implemented:

- Android 12+ (`minSdk 31`) Kotlin app, packaged for `arm64-v8a`
- explicit Moonshine Small Streaming selection (not Moonshine's Medium default)
- first-run model download with progress
- cached, on-device transcription on later offline runs
- tap Start / tap Stop microphone flow; the microphone exists only during active dictation
- provisional and final raw transcript display
- monotonic recording-duration and STT-tail metrics
- transcript-free `LocalFlow` diagnostic logs
- Liquid LEAP 0.10.9 cleanup model download, progress, cache reuse, unload, and generation metrics
- editable direct-text cleanup with raw pre-guard output and conservative output fallbacks
- a 24-case, multi-prompt cleanup batch runner with JSONL export and deterministic host scoring
- completed Pixel 7 evaluations of LFM2.5-230M, 350M, and 1.2B-Instruct `Q4_K_M`; all are no-go
  results, with 230M retained as the latency baseline and 1.2B as the capability baseline
- a deterministic baseline, fresh 45-case regression suite, runtime-neutral streaming runner, and
  completed host screen of Granite 350M, Qwen3 0.6B, Gemma 270M, Qwen3.5 0.8B, and Gemma 1B; all
  generic candidates are no-go results
- reproducible specialized-model screening with pinned prompt/model/corpus/tool provenance
- command-line build, install, log, and toolchain-check scripts

Not implemented yet:

- a cleanup model that has passed the fixed quality/safety bar
- joined STT → cleanup pipeline
- Android `InputMethodService`

See [ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md](ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md) for the
product plan and milestone sequence.

For a concise new-session handoff, current progress, decisions, device evidence, and the ordered
work queue, start at [docs/project/README.md](docs/project/README.md). A session running on the
separate RTX A6000 training machine must start at
[TRAINING_MACHINE_HANDOFF.md](TRAINING_MACHINE_HANDOFF.md) after reading the root
[AGENTS.md](AGENTS.md).

## Privacy and networking

Audio and transcripts are processed on the phone. They are not uploaded and the app contains no
analytics or cloud transcription fallback.

The app has network permission only because the first load of each selected Moonshine or Liquid
model downloads its assets. Moonshine Small Streaming English 0.1.2 is currently about 158 MiB.
Downloaded models are kept in app-private persistent storage, reused by later offline runs, and
removed by clearing app data or uninstalling the app.

After each model has loaded successfully once, its normal benchmark path should work in airplane
mode. The smaller cleanup matrices completed fully offline, and 1.2B passed a cached airplane-mode
load in 1.93 seconds.

## Pinned toolchain and dependencies

| Component | Version / setting |
|---|---|
| Android Studio | Quail 3 / 2026.1.3 Patch 1 or compatible |
| Android Gradle Plugin | 8.13.2 |
| Gradle | 8.13 (wrapper) |
| Kotlin Android plugin | 2.3.20 |
| JDK | 17 |
| compileSdk / targetSdk | 36 / 36 |
| Android Build-Tools | 35.0.0 (AGP 8.13 default) |
| minSdk | 31 |
| ABI | arm64-v8a |
| Moonshine Voice | `ai.moonshine:moonshine-voice:0.1.2` |
| STT model | English Small Streaming, architecture 4 |
| Liquid LEAP | `ai.liquid.leap:leap-sdk:0.10.9` and `ai.liquid.leap:leap-model-downloader:0.10.9` |
| Cleanup baselines | LFM2.5-230M, 350M, and 1.2B-Instruct `Q4_K_M` (all rejected) |
| Active cleanup candidate | None; VoiceInk 2B probe rejected, sub-1B task-specific training next |

AGP 8.13.2 and target API 36 are kept intentionally because they match the current Moonshine sample
and Liquid LEAP 0.10.9 Android requirements.

## One-time Mac setup

The project is set up for Apple Silicon Homebrew paths. Install the tools:

```bash
brew install --cask android-studio
brew install --cask android-commandlinetools
brew install openjdk@17
```

Install the required Android SDK packages:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
sdkmanager --sdk_root="$HOME/Library/Android/sdk" \
  "platform-tools" \
  "platforms;android-36" \
  "build-tools;35.0.0"
yes | sdkmanager --sdk_root="$HOME/Library/Android/sdk" --licenses
```

Alternatively, open this repository in Android Studio and use **Settings → Languages & Frameworks
→ Android SDK** to install Android SDK Platform 36, Build-Tools 35.0.0, and Platform-Tools. Set the
Gradle JDK to the installed JDK 17 if Android Studio does not select it automatically.

Verify the command-line environment:

```bash
./scripts/check-toolchain.sh
```

## Pixel 7 setup

1. On the phone, open **Settings → About phone** and tap **Build number** seven times.
2. Open **Settings → System → Developer options** and enable **USB debugging**.
3. Connect the Pixel to the Mac with a data-capable USB cable.
4. Accept the RSA authorization prompt on the phone.
5. Run `./scripts/check-toolchain.sh` and confirm the device status is `device`, not
   `unauthorized`.

macOS does not need a separate Pixel USB driver.

## Build, install, and run

Build the debug APK:

```bash
./scripts/build-debug.sh
```

The APK is written to:

```text
app/build/outputs/apk/debug/app-debug.apk
```

Build and install/update it on the connected Pixel:

```bash
./scripts/install-debug.sh
```

Launch it from the Pixel app drawer as **Local Flow**, or from the terminal:

```bash
adb shell am start -n dev.localflow.dictation/.MainActivity
```

Filtered diagnostic logs:

```bash
./scripts/logs.sh
```

The app deliberately does not write transcript text to logs.

## First-run speech benchmark flow

1. Make sure the Pixel has internet access.
2. Open Local Flow and tap **Load model**.
3. Keep the app open while the roughly 158 MiB model downloads and loads.
4. Tap **Start dictation** and grant microphone permission when Android asks.
5. Speak, then tap **Stop dictation**.
6. Inspect the raw transcript and metrics.

The loaded speech model stays in memory between dictations for low restart latency. The microphone
does not: the app creates and starts Android's `AudioRecord` only after **Start dictation**, then
stops it immediately when **Stop dictation** is tapped. Final transcription drains only audio that
was already captured; it does not keep the microphone open while finalizing.

`STT tail` is measured from the Stop tap (the V1 proxy for speech end) until Moonshine supplies the
final flushed transcript. All timing uses `SystemClock.elapsedRealtimeNanos()`.

## Cleanup-only evaluation status

The cleanup harness accepts editable text directly, so cleanup models can be compared without STT
errors or microphone timing contaminating the result. The fixed evaluation uses 24 cases and
multiple prompt variants, records pre-guard and final output, and scores strict matches plus
preservation and safety signals.

- LFM2.5-230M `Q4_K_M`: no-go; best prompt was 3/24 exact with 96.7% anchor preservation and a
  661 ms median total generation time.
- LFM2.5-350M `Q4_K_M`: no-go; best prompt was 1/24 exact with 77.0% anchor preservation and one
  observed meaning-changing negation failure.
- LFM2.5-1.2B-Instruct `Q4_K_M`: no-go; best prompt reached 13/24 exact but changed meaning, answered
  dictated content, lost technical details, and failed all self-corrections. Cached load was 1.93 s;
  post-run memory was about 901 MiB PSS (922,265 KiB).
- The cross-family host screen also rejected Granite 350M, Qwen3 0.6B, Gemma 270M, Qwen3.5 0.8B,
  and Gemma 1B. Gemma 1B was closest at 32/45 raw exact but still produced three semantic/safety
  failures.
- The first specialized probe was the author's VoiceInk Qwen3.5-2B Q4_K_M checkpoint, evaluated
  locally with its exact training prompt. Its fine-tune license is undeclared, so it was never a
  distributable app dependency.

The VoiceInk screen is complete and is also a no-go: 38/69 raw exact, 149/163 anchors, only 2/10
explicit corrections exact, six retained superseded corrections, three meaning/fact changes, and
one answered dictated instruction. It is not an automatic training-label source.

Cleanup is therefore not joined to STT. The active phase prepares a leakage-isolated 0.6B/0.8B
task-specific cleanup experiment for the separate training machine. This Mac is used only for data
tooling, model inference, and evaluation; no training job is run here. Formal STT comparison is
deferred until cleanup is no longer the demonstrated bottleneck.

See [the test log](docs/project/TEST_LOG.md) and
[static result summaries](docs/evaluation/results/) for the durable evidence.

## RTX A6000 vLLM evaluation

The training machine has a separate, locked vLLM 0.8.5 / CUDA 12.4 environment for serving the
pinned Qwen3-0.6B base and a startup-loaded LoRA. One local server can feed multiple deterministic
evaluation clients; shard assignment, strict resume checks, and validated source-order merging are
built into the launcher. Large environments, model artifacts, shards, and raw results stay under
`/data/rise/android_stt/`, outside Git.

Start with [the vLLM serving guide](docs/training/VLLM_SERVING.md), then use
[the sharded evaluation guide](docs/evaluation/SHARDED_OPENAI_EVAL.md). The client always sends
Qwen's non-thinking chat-template option and records raw output for qualification; guardrail output
is parallel evidence and cannot turn a raw semantic failure into a passing checkpoint. The runner
refuses blind evaluation paths and records per-row source, shard, corpus-hash, and configuration
fingerprints for reproducibility.

## Airplane-mode acceptance check

Do this separately for each benchmark model, only after its first load has completed while online:

1. Force-stop Local Flow.
2. Enable airplane mode and leave Wi-Fi disabled.
3. Reopen Local Flow.
4. Load the selected model. It should load from local app storage without a download failure.
5. Run the relevant speech or direct-text benchmark and confirm a result appears.
6. Force-stop and reopen the app once more while still offline, then repeat the benchmark.

Clearing Local Flow's storage or uninstalling it removes the model and makes an online first load
necessary again.

## Tests

Run local unit tests and build verification:

```bash
. ./scripts/android-env.sh
./gradlew testDebugUnitTest assembleDebug
```

Device microphone quality, finalization latency, cleanup quality/latency, cache behavior, and
airplane-mode operation require the physical Pixel 7; they cannot be established by JVM unit tests.

## Vendor references

- Moonshine repository: <https://github.com/moonshine-ai/moonshine>
- Moonshine Android quick start: <https://moonshine-voice.readthedocs.io/en/latest/quickstart/>
- Moonshine 0.1.2 release: <https://github.com/moonshine-ai/moonshine/releases/tag/v0.1.2>
- Android physical-device setup: <https://developer.android.com/studio/run/device>
- Android command-line builds: <https://developer.android.com/build/building-cmdline>
- Liquid LEAP Android quick start:
  <https://docs.liquid.ai/deployment/on-device/sdk/quick-start>
