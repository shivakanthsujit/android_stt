# Local Flow for Android

Local Flow is a Pixel-first, fully local dictation project. The ordinary Android testing app now
captures microphone speech for the selected **Parakeet TDT/CTC 110M Q4_K** model and automatically
passes its final transcript to the public **Sotto LFM2.5-350M Q4_K_M** cleanup fine-tune. This is an
integration build: Sotto has known semantic failures and is not a deployment-qualified cleanup
model. The raw transcript, complete model output, guarded result, and stage timings stay visible so
the pipeline can be exercised while a better cleanup checkpoint is trained.

Keeping these stages independently measurable in a normal Activity makes model quality, latency,
offline behavior, and microphone lifecycle observable before Android keyboard work is introduced.

## Current milestone

Implemented:

- Android 12+ (`minSdk 31`) Kotlin app, packaged for `arm64-v8a`
- retained Moonshine Small and generic Liquid benchmark engines with their original model download,
  progress, cache, and offline-reuse paths
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
- completed native-prompt BF16 screen of the public Sotto LFM2.5-350M cleanup checkpoint; it is
  stronger than generic LFM but remains a no-go because it changed protected facts/text and
  frequently retained superseded corrections
- a debug-only, file-fed Pixel STT harness with deterministic LibriSpeech audio, normalized WER,
  repeat latency, process CPU, PSS, thermal, and Perfetto CPU/GPU/memory rail energy scoring
- clean Pixel comparison of Moonshine Small and `parakeet.cpp` 110M F16/Q4_K; Q4_K is the
  provisional STT candidate at 1.85% probe WER, 0.72 s untraced median, and 235 J measured compute
  energy across the 72-call workload
- live microphone capture for Parakeet Q4_K with project-owned Start/Stop lifecycle and offline
  final inference after Stop; the selected model does not provide fabricated partial text
- reproducible BF16-to-GGUF/Q4_K_M export of the pinned public Sotto checkpoint and hash-checked
  staging into app-scoped device storage
- joined Parakeet → Sotto integration flow with automatic cleanup, raw/guarded output, STT tail,
  cleanup TTFT/total, and Stop-to-cleanup end-to-end tail
- command-line build, install, log, and toolchain-check scripts

Not implemented yet:

- a cleanup model that has passed the fixed quality/safety bar
- a dictation-focused STT qualification corpus; the current 24-clip read-speech probe is not a
  final product WER claim
- cache-aware Parakeet partial/streaming inference; the current joined build transcribes the
  complete captured utterance after Stop
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

The app retains network permission for the older Moonshine/Liquid benchmark paths, but the joined
Parakeet/Sotto build does not download a model at runtime. Both verified GGUFs are staged over ADB
into app-scoped external storage and all inference is local. Clearing app data or uninstalling the
app removes the staged files.

The joined path works in airplane mode as soon as both staged artifacts pass their local hash
checks. The older downloaded benchmark models also retain their previously verified offline cache
behavior.

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
| Joined-build STT | `parakeet.cpp` 0.5.0 TDT/CTC 110M Q4_K; final inference after Stop |
| STT quality reference | Parakeet TDT/CTC 110M F16; Moonshine Small retained as an evaluated baseline |
| Liquid LEAP | `ai.liquid.leap:leap-sdk:0.10.9` and `ai.liquid.leap:leap-model-downloader:0.10.9` |
| Cleanup baselines | LFM2.5-230M, 350M, and 1.2B-Instruct `Q4_K_M` (all rejected) |
| Joined-build cleanup | Public Sotto LFM2.5-350M, pinned HF revision, locally converted Q4_K_M; integration-only |
| Active cleanup training | Sotto LFM2.5-350M correction-repair experiment on the separate RTX A6000 machine |

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

## Joined Parakeet → Sotto integration flow

The model files are deliberately excluded from Git and the APK. The staging script expects the
selected Parakeet artifact at `.cache/stt-eval/models/tdt_ctc-110m-q4_k.gguf` and the converted
Sotto artifact at
`.cache/integration/models/sotto-gguf-mapped/sotto-cleanup-lfm25-350m-q4_k_m.gguf`. It rejects
anything except the pinned SHA-256 identities.

From a clean checkout, prepare the Parakeet source/model as described in the
[STT benchmark guide](docs/evaluation/STT_BENCHMARK.md), then package the pinned Android ARM64
runtime and shared JNI bridge:

```bash
./scripts/build-parakeet-android.sh
```

The Sotto export is reproducible from Hugging Face revision
`6df6f019170b8b55333c047b901886a51750a965`. Put that revision's model/config/tokenizer files under
`.cache/integration/models/sotto-hf`, check out Liquid's `leap-finetune` commit
`ee010f850a6f9e810aebbbc8e5d072675fcaece7` under `.cache/integration/leap-finetune`, install the
pinned `llama.cpp` 10450 and `uv` tools, then run:

```bash
./scripts/export-sotto-integration-gguf.sh
```

The exporter verifies every source file, applies the committed LFM2.5 tensor-name mapping, writes
a 711,483,232-byte F16 reference, and quantizes the 229,310,304-byte deployment GGUF. It refuses to
overwrite an existing export.

Build and install the APK before staging its app-scoped model directory:

```bash
./scripts/install-debug.sh
./scripts/stage-integration-models.sh
adb shell am start -n dev.localflow.dictation/.MainActivity
```

In the app:

1. Tap **Load staged Parakeet** and **Load staged Sotto**.
2. Tap **Start dictation**, grant microphone permission, speak, and tap **Stop dictation**.
3. Parakeet transcribes the completed local capture, then Sotto cleanup runs automatically.
4. Inspect the raw transcript, complete unguarded Sotto output, guarded output, and stage metrics.

The models remain warm between utterances. The microphone does not: the app creates and starts
`AudioRecord` only after **Start dictation** and stops it synchronously at the Stop tap. The current
Parakeet model processes the already captured utterance as one offline batch and therefore exposes
no partial transcript. `STT tail` measures Stop-to-final transcript; `End-to-end tail` measures
Stop-to-cleanup completion. All timing uses `SystemClock.elapsedRealtimeNanos()`.

This flow is for integration testing, not model qualification. Public Sotto scored 42/69 strict
exact and 59/69 user-acceptable in its frozen screen, with ten relevant failures. Guardrail
fallback is visible defense in depth and cannot turn that checkpoint into a deployment candidate.
See the [integration build evidence](docs/evaluation/results/2026-08-18-parakeet-sotto-integration-build.json).

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

The publisher's task-tuned Sotto LFM2.5-350M checkpoint was also tested directly with its native
prompt and recommended greedy decoder. It reached 42/69 strict exact and 147/163 anchors and never
answered any of the 17 dictated questions/commands. User review found 59/69 acceptable for the
intended ordinary-conversation workload. The ten relevant failures are seven retained superseded
corrections, two retained repetitions, and one statement changed into a question. The next
experiment repairs those behaviors with a correction-weighted LFM training mixture before any
Android conversion or integration.
See [the full screen](docs/evaluation/results/2026-08-18-sotto-lfm25-350m-public-screen.md).

Public Sotto is therefore joined only as a replaceable integration placeholder. The deployment
quality gate is unchanged: raw model output still must pass semantic safety before a checkpoint can
ship. The active correction-repair experiment runs on the separate training machine. This Mac is
used only for data tooling, model conversion, inference, and evaluation; no training job is run
here.

## File-fed STT probe status

The initial fixed Pixel probe now compares Moonshine Small with `parakeet.cpp` 0.5.0 TDT/CTC 110M
F16 and Q4_K on 24 LibriSpeech `test-clean` clips, one warm-up, and three measured repeats. This is
a deterministic multi-speaker probe, not the official full-split score or a dictation
qualification.

- Moonshine: 3.54% WER, 1.23 s median, 3.03 s p90, 797.7 MiB peak PSS.
- Parakeet F16: 1.69% WER, 1.03 s median, 2.39 s p90, 513.1 MiB peak PSS.
- Parakeet Q4_K: 1.85% WER, 0.72 s median, 1.80 s p90, 383.1 MiB peak PSS.
- Q4_K differed from F16 on one word (`Hidalgo` → `Hadalgo`) but used 23.8% less process CPU time,
  23.3% less measured inference compute energy, 8.6% less average compute power, and 25.5% less
  memory in matched power runs. GPU rail use was negligible because the current build is CPU-only.

Q4_K is therefore the provisional deployment candidate; F16 remains the non-quantized quality
reference. The integration app now uses Q4_K in offline-on-Stop microphone mode, but streaming and
protected-token dictation quality still must pass before the final product choice. Full
methodology, hashes, caveats, and power results are in
[the Pixel Parakeet report](docs/evaluation/results/2026-08-18-pixel-parakeet-stt-probe.md), with
reproduction instructions in [the STT benchmark guide](docs/evaluation/STT_BENCHMARK.md).

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
fingerprints for reproducibility. Those guarantees cover evaluation membership and provenance, not
batch-invariant GPU generation: vLLM 0.8.5 showed small case-level output variation as concurrency
changed. Use the same pinned 64-client profile for checkpoint comparisons and repeat borderline
results; do not compare its score directly with sequential Transformers inference.

## Airplane-mode acceptance check

The joined models are ADB-staged and need no network. After staging both artifacts:

1. Force-stop Local Flow.
2. Enable airplane mode and leave Wi-Fi disabled.
3. Reopen Local Flow.
4. Load staged Parakeet and Sotto. Both should pass their local hash checks without a network.
5. Run one dictation and confirm the raw transcript and cleanup diagnostics appear.
6. Force-stop and reopen the app once more while still offline, then repeat the benchmark.

Clearing Local Flow's storage or uninstalling it removes both models; rerun the ADB staging script
after reinstalling.

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
- Liquid LEAP sideloaded model loading:
  <https://docs.liquid.ai/deployment/on-device/sdk/model-loading>
- Pinned public Sotto checkpoint:
  <https://huggingface.co/juanquivilla/sotto-cleanup-lfm25-350m/tree/6df6f019170b8b55333c047b901886a51750a965>
- `parakeet.cpp` runtime: <https://github.com/mudler/parakeet.cpp>
