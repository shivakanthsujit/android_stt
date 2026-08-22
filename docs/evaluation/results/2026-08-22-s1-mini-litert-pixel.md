# S1-mini LiteRT-LM Pixel CPU/GPU probe

Date: 2026-08-22
Device: Google Pixel 7 (`panther`), Android 17/API 37
Runtime: LiteRT-LM Android 0.16.1

## Outcome

Reject this LiteRT-LM artifact as a production replacement for tuned LEAP. The exact S1-mini
blockwise-32 INT4 bundle loads and generates on both Pixel CPU and Mali/OpenCL GPU, but neither arm
wins the user-shaped workload.

On the ten-case English representative fixture, CPU lost all 10 paired latency comparisons. Its
median total latency was 7,559.5 ms versus 1,379.0 ms for the thermal-clean LEAP reference
(+448.2%), and median post-call PSS was 1,571,406.5 KiB (+42.4%). GPU also lost all 10: median
total was 2,633.5 ms (+91.0%) and median PSS was 2,680,072 KiB (+142.9%). GPU TTFT was close to
LEAP, 714.5 versus 675.5 ms (+5.8%), but decode/total latency and memory reject the arm.

The isolated benchmark remains research tooling. The production keyboard and tuned LEAP engine
were not changed.

## User-shaped input contract

The final comparison uses ten project-authored English transcripts with no expected outputs or
private/evaluation text. Eight cases are 18–26 raw tokens and two are 51/53, for a median of 22.
They cover messages, reminders, a short list, uncertainty, a natural correction, a formatting
request, names/numbers, and brief journal entries.

An earlier non-representative Unicode stress row was explicitly excluded at the owner's request
and is not used in this verdict or any metric. Future cleanup-model testing should remain aligned
with the English personal dictation workload.

The Android probe verifies the exact 436,596,864-byte artifact SHA-256 before load. Every request
uses a fresh conversation, byte-exact system/control/Qwen prompt rendering,
`enable_thinking=false`, greedy sampling, context 4,096, and the product cap
`ceil(1.3 * raw_tokens + 32)`. Requests are sequential; there is no request batching or microphone
access. LiteRT-LM exposes no Android tokenizer/token-ID API, so the recorded prompt count is
explicitly source-tokenizer evidence (`78 + raw_tokens`), while rendered prompt bytes are directly
verified on device.

## Runtime evidence

The release APK is ARM64-only, debug-signed, has no Android permissions, and packages only the
official LiteRT-LM JNI library. CPU logs show XNNPACK delegation. GPU logs prove OpenCL loaded and
all main prefill/decode graphs delegated through `LITERT_CL`:

- prefill 128/256/512/1,024/1,152: 1,298/1,298 nodes delegated per graph;
- decode: 1,244/1,244 nodes delegated;
- external embedder: XNNPACK CPU;
- sampler: the optional OpenCL sampler library is absent from the official AAR, so sampling falls
  back to the statically linked C implementation.

This is genuine Mali/OpenCL model execution, not silent whole-engine CPU fallback. Both runs began
and ended at Android thermal status 0. LiteRT-LM native benchmark counters are disabled by ordinary
`EngineConfig`; the probe therefore uses the first non-empty asynchronous response chunk for wall
TTFT and callback completion for wall total latency. Filler-only output has no first-token value.

The first smoke-load samples were 3,143 ms CPU and 8,474 ms GPU. The representative runs reused
their backend cache and loaded in 1,601 ms CPU and 4,541 ms GPU. Load figures are labeled by cache
state and are not mixed with per-request latency.

## Representative results

The LEAP column uses repeat 0 from the existing thermal-clean, same-fixture user-shaped reference.
This was not a new counterbalanced same-session rerun, but the regressions are too large to justify
advancing to sustained or power testing.

| Metric, median | LEAP t2/ctx2560 | LiteRT CPU | CPU delta | LiteRT GPU | GPU delta |
|---|---:|---:|---:|---:|---:|
| Total latency | 1,379.0 ms | 7,559.5 ms | +448.2% | 2,633.5 ms | +91.0% |
| TTFT | 675.5 ms | 3,764.5 ms | +457.3% | 714.5 ms | +5.8% |
| Process CPU | 2,655.5 ms | 14,733.5 ms | +454.8% | 1,301.5 ms | -51.0% |
| Post-call PSS | 1,103,466 KiB | 1,571,406.5 KiB | +42.4% | 2,680,072 KiB | +142.9% |
| Native heap | 1,113,230,736 B | 1,132,993,056 B | +1.8% | 292,564,696 B | -73.7% |

GPU's lower process CPU/native heap does not offset its GPU-backed resident memory and total
latency. CPU/GPU maximum PSS was 1,575,278/2,682,965 KiB. No arm reached thermal status 1.

## Output review

LiteRT and LEAP raw text matched exactly on 1/10 cases: the formatted grocery list. Most differences
were missing final periods. Names, numbers, time conversion, uncertainty, and the long messages
were otherwise preserved. Both LiteRT arms reduced the correction case to the final address but
dropped LEAP's final word `instead`; this remains understandable. CPU alone introduced the awkward
phrase `water the balcony, herbs`; GPU produced the intended `water the balcony herbs`.

These are research differences, not a runtime rejection filter. The personal-use app continues to
insert every non-empty, non-capped cleanup generation. They do show that the converted artifact is
not raw-output interchangeable with the current Q4 runtime. No thinking markup, loop, malformed
response, crash, or thermal event occurred in the representative run.

## Reproducibility

| Artifact | SHA-256 |
|---|---|
| LiteRT-LM bundle | `8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403` |
| Official Android AAR | `e407719c1a29f2685fcb6aa3feea0b9f7155fe316c66dae053c1b5b2f54cda73` |
| Release APK, 28,687,212 bytes | `6873d1ca1977ae40b31e55ded9d546db242fcd5e4efb56a33388b3993ead16e9` |
| English representative fixture | `af81edc3092744d78bdbe75daf8f0f6a1ffa4c78403131fb4ea4c51756f190ae` |
| CPU raw result | `970d58f8ff01b9e5fdf30b681e9581cf6cb758f6098d66d7361e441061cba185` |
| CPU summary | `2f3ab6ce722362c0a6194bd76d9c31bdbb4aefbed364d1d98e565a68e1d866fd` |
| CPU logcat | `f9af620236adbb7677a51b3eae14f47879a32aa877d69968ffac71796c7974f9` |
| GPU raw result | `6ffe9fb47b05764b71463fb66ff7af9ecb5817b2df8d7c78454a7cdfe54dc4af` |
| GPU summary | `5f56485027725bfb75699c0c1796250af7c923691d975ebc8832cc8fad310784` |
| GPU logcat | `32d33d7dd73b7b205f7b2b433b3708d6f1a80f3053b8b5c0a01545248f08ab7d` |

Raw results, APKs, logs, and model bytes remain ignored outside Git. After evidence handoff, the
owner authorized uninstalling the isolated benchmark package. Removing its approximately 427 MiB
of app files plus 635 MiB of compiled CPU/GPU cache recovered 1,062,396 KiB (about 1.01 GiB).
The host/Dante evidence remains retained; the production keyboard package was verified present
after teardown.

## Decision

Retain tuned LEAP (`cpuThreads=2`, context 2,560, mmap on, cache off). Do not convert a second
2,560-context LiteRT artifact or run power/sustained arms: the first exact 4,096-context artifact
already misses total-latency and memory gates by margins too large for context-cache reduction to
plausibly reverse. Do not integrate LiteRT-LM into the production APK.
