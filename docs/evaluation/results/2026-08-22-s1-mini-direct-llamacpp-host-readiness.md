# S1-mini direct llama.cpp Android host readiness

Date: 2026-08-22

Status: superseded by completed Pixel CPU comparison; direct runtime rejected

## Outcome

Order 4 now has a collision-isolated Android benchmark implementation that exercises the exact
selected S1-mini Q4_K_M GGUF through a project-owned, pinned llama.cpp CPU runtime. The host build,
schema, prompt golden, transcript-only staging, native interface, result validation, and Pixel
runner are ready. An owner-approved initial Pixel smoke proved device-side template/token parity,
runtime provenance, deterministic repeat behavior across two independent short runs, and the
selected Pixel ARM backend. The later owner-approved device campaign closed matched LEAP/host
parity, the natural cap path, repeated stress and user-shaped performance, and sustained thermal
evidence. Direct CPU was rejected; see `2026-08-22-s1-mini-direct-llamacpp-pixel.md`.

This checkpoint installed only the separate benchmark APK and staged the exact GGUF plus three
project-authored non-evaluation smoke strings in its app-private storage. It did not use the
microphone, convert a model, use a smaller quantization, or change the production LEAP engine.

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
| JNI source | SHA-256 `8a49979b770705d40987cc552295a2f5cac83388c0aa3194996f2b59046ae3ee` |
| Release APK | 18,701,319 bytes; SHA-256 `8931caef1a33acc84c9eb173d4d09d986f71ea0f6816716e3a3e93ce05b1bfad` |
| Stripped JNI DSO | 131,936 bytes; SHA-256 `5239a148be50160102d7f67397e81c27808a10f1af19b6cc206cb1756c1f3733` |

The ignored build-evidence directory is
`.cache/integration/llamacpp-builds/20260821T180352Z-llamacpp-b10450-android-release/`.
Its `build-manifest.json` SHA-256 is
`b0fbfdc3ea95d6c51a25256549325e9b85d3eb6f2bceff4304108021bf9a9f51`.
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

## Pixel smoke evidence

The owner approved the device session. The runner verified the one authorized Google Pixel 7
`panther` at serial `33040DLH20004E`, ARM64, the exact APK/model hashes, and thermal status 0 before
starting inference. Configuration was context 2,560, generation/batch threads 2/2, batch/ubatch
512/512, mmap on, flash attention off, GPU layers zero, one warmup, and one measured pass through
three project-authored cases.

The first completed run, `20260821T180154Z`, exposed a scorer-only provenance error: the native
library correctly reported semantic `llama_version=0.1.0-dev`, while the scorer incorrectly
expected `b10450` in that field. Its four inference rows were retained at SHA-256
`8311354d0d8a1a44c4b868bf9b0a5ed504849925a28389a5664710d69b448b2b` and were not silently
discarded. The runtime/result contract was corrected to record semantic version, build number
`10450`, commit `ece963f41`, and target `Android aarch64` independently.

Corrected run
`20260821T180425Z-s1-direct-c2560-gt2-bt2-b512-u512-mm1-fa0-g0` passed the strict scorer:

- all four warmup/measured rows and all three unique cases exactly match the host golden's raw
  token IDs, rendered prompt bytes, and prompt token IDs;
- prompt-token count minus raw-token count is exactly 78 on every row; raw/prompt/cap counts are
  3/81/36, 11/89/47, and 1/79/34;
- all generations ended on EOG, none reached its cap, and the filler-only case produced the valid
  empty generation expected by the publisher contract;
- outputs, token IDs, and finish states match the retained first run on 4/4 rows; one repeat per run
  is not a substitute for the later repeated stability matrix;
- the Pixel selected `libggml-cpu-android_armv8.2_2.so`, reporting NEON, ARM FMA, FP16 vector
  arithmetic, DOTPROD, and REPACK; and
- post-inference thermal status remained 0 for every row.

Smoke-only measurements were 996 ms model load, 507.0 ms median nonblank TTFT, 601.1 ms measured
median total, 486.0 ms median prompt evaluation, 27.85 decode tokens/s median, 1,161,540 KiB maximum
post-call PSS snapshot, and 1,108,342,032 bytes maximum post-call native-heap snapshot. These three
cases and single measured pass are contract smoke evidence, not a LEAP performance comparison.

Retained corrected artifact hashes:

| Artifact | SHA-256 |
|---|---|
| transcript-only cases | `4db5eadbd5020feb90385a8bcc86a7d8c9db65b5d0bc7c0b82e51b5fab357bbc` |
| run manifest | `7795cd8ae834a18a23f3c51a87445a816c4851c01609da34f9c618fc11950424` |
| raw JSONL | `a9c87772dfa911afc9cf6ea2d2c478952c91f56b7cf68c21532d58834c683fb1` |
| scorer summary | `72906c79413da1542b778f7c37290b4b6a215c3f3700658ef8f28a67a3831406` |

## Closed by the Pixel comparison

The later campaign retained the Unicode spacing difference, proved natural cap termination 6/6,
and matched direct versus LEAP prompt counts, caps, and raw outputs 30/30 on a user-shaped corpus.
The bounded CPU matrix and a fresh confirmation found no repeatable 15% median speed win and
observed latency/CPU/thermal regressions, so LEAP remains production. llama.cpp's perf getter still
reports an internal minimum `n_eval=1` for immediate EOG; the separately recorded completion count
is authoritative. PSS/native-heap values remain post-call snapshots rather than within-call peaks.

Full final evidence and retained artifact hashes are in
`docs/evaluation/results/2026-08-22-s1-mini-direct-llamacpp-pixel.md`. Blind-v2 was not used.
