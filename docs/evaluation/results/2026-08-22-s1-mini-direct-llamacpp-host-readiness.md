# S1-mini direct llama.cpp Android host readiness

Date: 2026-08-22

Status: host implementation and reproducible Release build complete; no Pixel install, Android
generation, output-parity result, or performance claim yet

## Outcome

Order 4 now has a collision-isolated Android benchmark implementation that can exercise the exact
selected S1-mini Q4_K_M GGUF through a project-owned, pinned llama.cpp CPU runtime. The host build,
schema, prompt golden, transcript-only staging, native interface, result validation, and future
Pixel runner are ready. Device-side template/token parity, raw-output parity, selected Pixel ARM
backend, stability, latency, memory, energy, and thermal evidence remain pending a fresh
owner-approved device session.

This checkpoint did not install an APK, invoke ADB, convert a model, use a smaller quantization, or
change the production LEAP engine.

## Isolated runtime boundary

- Android application ID: `dev.localflow.llamacppbenchmark`.
- The APK has no LEAP, Moonshine, or Parakeet dependency. Its ordinary llama/ggml SONAMEs are safe
  only because it is a separate application/process.
- Architecture: ARM64 only; min SDK 31; compile/target SDK 36.
- Native build: Release; Kotlin release is debug-signed and debuggable for benchmark staging, while
  JNI debugging is disabled.
- CPU only for the first comparison: GPU layers zero; CUDA, HIP, Metal, Vulkan, OpenCL, RPC, SYCL,
  WebGPU, Hexagon, BLAS, OpenMP, llamafile, and `GGML_NATIVE` are disabled.
- Runtime CPU selection packages seven Android ARM variants. Because modern Android can leave DSOs
  inside an unextracted APK, the JNI layer probes the packaged sonames through the Android linker,
  applies the pinned runtime's own `ggml_backend_score`, registers only the highest supported CPU
  variant, and records its exact library name.
- KleidiAI is disabled in this first arm because this llama.cpp revision would fetch an additional
  external source archive. Enabling it would be a separately pinned runtime arm, not an implicit
  build change.

## Fixed identities

| Artifact | Identity |
|---|---|
| S1-mini GGUF | 484,219,808 bytes; SHA-256 `3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634` |
| llama.cpp | commit `ece963f41b0b02d7a0d61436ae365762c073a4c8`; tree `f59cbdf04f233655507cc98ee9f704b71bfd1403`; build `b10450` |
| llama.cpp Git archive | 171,663,360 bytes; SHA-256 `d0927d84cda1b6f613a0c953da5bb490d8960546ee3fb15a23810d89f6137f8b` |
| Android NDK | `28.0.13004108` |
| Android CMake package/binary | `3.31.6` / `3.31.6-g38307f9` |
| Prompt golden | 3,412 bytes; SHA-256 `a4aa17028124311985afcbd4145bb8569b18c4ff0284f933e75c335dc1d496ec` |
| CMake configuration | SHA-256 `b1879d46fe236a704e60dbae5d10ac6398db9b9ae7fd4ac6c3804229f602cf7a` |
| JNI source | SHA-256 `bf7c83e0b8f0d1d78287aa88e995ba73d7a252c7a964a06af036c3fd2f100b74` |
| Release APK | 18,700,783 bytes; SHA-256 `922dade851572d7a72e1ac36802e9c061862712773acbf756dafe89db7379ad6` |
| Stripped JNI DSO | 131,400 bytes; SHA-256 `2d599c96e1caef721ba9086252d486ac5c2dec184d6f15e403fae5ae1ad8c390` |

The ignored build-evidence directory is
`.cache/integration/llamacpp-builds/20260821T175500Z-llamacpp-b10450-android-release/`.
Its `build-manifest.json` SHA-256 is
`e13e6ed271e96a8ca7a249fbd47a8cee40735ab70f37f68c3575d41fe618d5bc`.
The manifest records every packaged native-library hash plus the resolved CMake cache, configure
command, and Android Gradle native build model. Model weights, native binaries, and build caches
remain outside Git.

## Exact S1 contract implemented

- The system prompt and publisher control line are byte-fixed.
- The GGUF-embedded template is rendered through pinned llama.cpp Minja with
  `enable_thinking=false`; the assistant prefix ends in `<think>\n\n</think>\n\n`.
- Raw transcript tokenization is `add_special=false, parse_special=true`; prompt tokenization is
  `add_special=true, parse_special=true`.
- The fixed empty-transcript template is required to contain exactly 78 tokens.
- Generation is greedy, stops on model EOG, excludes EOG from completion count, and reports a cap
  only after emitting exactly `ceil(1.3 * raw_tokens + 32)` tokens.
- One persistent model/context owner serves a single benchmark worker. KV metadata and performance
  counters are cleared between requests without zero-filling the backing allocation.
- Every row retains raw text, exact rendered prompt and token IDs, raw output, completion IDs,
  finish state, monotonic native timestamps, native prompt/decode performance, process CPU, PSS,
  native heap, thermal status, complete build/runtime metadata, and selected ARM backend.
- The staged cases file accepts only `id`, `raw`, and `categories`. Expected outputs and other
  evaluation fields are rejected and never sent to the app.

The three-case host prompt golden contains only project-authored smoke strings, including Unicode;
it contains no cleanup expected output. The Android runtime must reproduce its rendered bytes and
token IDs before any performance run is accepted.

## Host verification

- `:llamacpp-benchmark:testReleaseUnitTest :llamacpp-benchmark:assembleRelease`: passed, 13 tests.
- Python preparation/scorer/build/runner suite: passed, 21 tests.
- Shell syntax, Python compilation, and `git diff --check`: passed.
- APK compression integrity, 16 KiB zip alignment, and APK Signature Scheme v2 verification:
  passed.
- APK contains only ARM64 native libraries. It includes all seven expected CPU variants,
  `libggml-base.so`, `libggml.so`, `libllama.so`, `libllama-common.so`, the JNI DSO, and one
  `libc++_shared.so`; no LEAP, Moonshine, or Parakeet library is present.
- The JNI DSO exports exactly the six intended JNI entry points. Its dynamic dependencies are the
  isolated APK's llama/ggml stack plus Android/system libraries.

The build emitted only two unused-helper warnings from pinned Minja headers. They do not change
the generated binary contract and are retained as upstream-source warnings.

## Device gate still required

The next session must begin with an explicit owner approval immediately before device work. The
Pixel runner requires an explicit `ANDROID_SERIAL`, exactly one authorized matching Google Pixel,
ARM64, the exact model/APK, an explicit non-evaluation transcript-only performance corpus, and
thermal status 0. It retains partial/error artifacts and does not silently retry.

The first device step is a one-case/short-corpus smoke that proves model load, exact prompt golden,
token IDs, output cap, greedy EOG/cap handling, and selected backend. Only after this gate should a
non-evaluation shape/length corpus tune threads, batch threads, batch/ubatch, and flash attention.
Personal-v3 and the committed cleanup suites may be used only after tuning is frozen for declared
regression/parity evidence; blind-v2 remains prohibited. A direct runtime earns production
consideration only after matched LEAP output, latency, p90, memory, energy, and thermal evidence.
