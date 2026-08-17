# Local Flow for Android

Local Flow is a Pixel-first, fully local dictation project. The current milestone is an ordinary
Android benchmark app that records microphone speech, transcribes it with **Moonshine Small
Streaming English**, displays the raw transcript, and reports end-of-speech finalization latency.

This intentionally comes before the cleanup language model and Android keyboard. Keeping the first
milestone as a normal Activity makes microphone/model integration measurable before IME lifecycle
work is introduced.

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
- command-line build, install, log, and toolchain-check scripts

Not implemented yet:

- Liquid LFM2.5 cleanup
- joined STT → cleanup pipeline
- Android `InputMethodService`

See [ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md](ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md) for the
product plan and milestone sequence.

## Privacy and networking

Audio and transcripts are processed on the phone. They are not uploaded and the app contains no
analytics or cloud transcription fallback.

The app has network permission only because the first **Load model** action downloads Moonshine's
model assets. Moonshine Small Streaming English 0.1.2 is currently about 158 MiB. The model is kept
under the app's no-backup files directory, survives app updates, and is removed by clearing app data
or uninstalling the app.

After one successful load, the normal transcription path should work in airplane mode. The offline
acceptance check is documented below.

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

AGP 8.13.2 and target API 36 are kept intentionally because they match the current Moonshine sample
and Liquid LEAP 0.10.9 Android requirements for the next milestone.

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

## First-run benchmark flow

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

## Airplane-mode acceptance check

Do this only after **Load model** has completed once while online:

1. Force-stop Local Flow.
2. Enable airplane mode and leave Wi-Fi disabled.
3. Reopen Local Flow.
4. Tap **Load model**. It should load from local app storage without a download failure.
5. Run at least three dictations and confirm final transcripts appear.
6. Force-stop and reopen the app once more while still offline, then repeat a dictation.

Clearing Local Flow's storage or uninstalling it removes the model and makes an online first load
necessary again.

## Tests

Run local unit tests and build verification:

```bash
. ./scripts/android-env.sh
./gradlew testDebugUnitTest assembleDebug
```

Device microphone quality, finalization latency, cache behavior, and airplane-mode operation require
the physical Pixel 7; they cannot be established by JVM unit tests.

## Vendor references

- Moonshine repository: <https://github.com/moonshine-ai/moonshine>
- Moonshine Android quick start: <https://moonshine-voice.readthedocs.io/en/latest/quickstart/>
- Moonshine 0.1.2 release: <https://github.com/moonshine-ai/moonshine/releases/tag/v0.1.2>
- Android physical-device setup: <https://developer.android.com/studio/run/device>
- Android command-line builds: <https://developer.android.com/build/building-cmdline>
- Liquid LEAP Android quick start (next milestone):
  <https://docs.liquid.ai/deployment/on-device/sdk/quick-start>
