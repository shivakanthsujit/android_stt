# Pixel 7 Parakeet STT probe

Date: 2026-08-18
Device: Google Pixel 7 (`panther`, serial `33040DLH20004E`)
Decision: advance Q4_K Parakeet as the provisional deployment candidate. Its single additional
word error is outweighed at this stage by materially lower latency, CPU time, measured energy,
memory, and model size. Keep F16 as the quality reference and do not replace the live Moonshine
path until Q4_K passes a dictation-focused and streaming/finalization evaluation.

## Scope

This is a deterministic probe, not the published LibriSpeech `test-clean` score and not a final
dictation qualification. It contains 24 clips from 12 speakers, selected as the first two
utterances from the first 12 speakers in the pinned Hugging Face `test-clean` row order. Each
engine received the same decoded 16 kHz mono float PCM, with one warm-up and three measured runs
per clip. WAV decoding, ADB transfer, and model load are outside the inference interval.

- Selection ID: `first-2-utterances-from-first-12-speakers-in-hf-test-row-order-v1`
- Manifest SHA-256: `7c90de45a130caf4ceb2f5215be114bd9daaa34e95549958440ccb7a95cc187f`
- Hugging Face dataset revision: `71cacbfb7e2354c4226d01e70d77d5fca3d04ba1`
- Official LibriSpeech `test-clean.tar.gz` MD5: `32fa31d27d2e1cad72775fee3f4849a9`
- Scoring: Unicode NFKC, case folding, punctuation-to-space conversion, then word-level
  Levenshtein substitutions/insertions/deletions. Punctuation and case are not included in WER.

The clean runs began at Android thermal status 0 with no competing foreground/background app
consuming meaningful CPU. The F16 and Q4_K runs remained at status 0. Moonshine reached status 1.

## Clean Pixel results

| Engine | Model bytes | WER | S / I / D | Median | p90 | p99 | Max | Corpus speed | Peak PSS | Thermal | Unstable cases |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Moonshine Small Streaming 0.1.2 | about 158 MiB download | 3.54% (21/593) | 9 / 9 / 3 | 1,233.7 ms | 3,033.3 ms | 4,046.4 ms | 4,061.1 ms | 6.46× realtime | 816,828 KiB | 1 | 8 raw / 7 normalized |
| `parakeet.cpp` 0.5.0 TDT/CTC 110M F16 | 267,452,544 | **1.69% (10/593)** | 8 / 1 / 1 | 1,034.5 ms | 2,388.1 ms | 3,571.8 ms | 3,772.7 ms | 7.94× realtime | 525,408 KiB | 0 | **0 / 0** |
| `parakeet.cpp` 0.5.0 TDT/CTC 110M Q4_K | 131,387,520 | 1.85% (11/593) | 9 / 1 / 1 | **717.0 ms** | **1,798.4 ms** | **2,541.5 ms** | **2,694.9 ms** | **11.31× realtime** | **392,342 KiB** | 0 | **0 / 0** |

The load measurements were warm/post-push file-cache measurements and are not cold-start claims:
Moonshine 996.1 ms, F16 169.0 ms, and Q4_K 103.0 ms.

Relative to clean Moonshine, F16 reduced word errors by 52.4%, median latency by 16.1%, p90 by
21.3%, corpus RTF by 18.6%, and peak PSS by 35.7%. Q4_K was faster than F16 on all 24 per-case
medians; its median per-case ratio was 0.695. It cut F16 median latency by 30.7%, p90 by 24.7%,
maximum latency by 28.6%, peak PSS by 25.3%, and model bytes by 50.9%.

## CPU, GPU, and energy

A second matched set of runs added exact process CPU time around every model call and Perfetto
hardware power-rail tracing. App async trace markers restrict the energy calculation to the 72
measured inference calls, excluding WAV decoding, PSS sampling, JSON writing, UI work, and the one
warm-up. Energy is integrated from the Pixel's on-device power rail monitors. These rails are
downstream of the battery and remain meaningful while USB is attached; raw battery charge/current
is confounded by USB supply and is not used for the model comparison. See the official
[Perfetto power data-source documentation](https://perfetto.dev/docs/data-sources/battery-counters#odpm).

| Engine | Process CPU | Median average cores | Inference interval | CPU rail | GPU rail | Memory/fabric rail | Compute energy | Avg compute power | Energy / audio-second | Peak PSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Moonshine | 696.9 s | 3.79 | 216.190 s | 262.733 J | 0.528 J | 104.069 J | 367.330 J | 1.699 W | 1.551 J | 792.4 MiB |
| Parakeet F16 | 725.7 s | 7.30 | 100.023 s | 276.313 J | 0.268 J | 29.996 J | 306.577 J | 3.065 W | 1.295 J | 507.5 MiB |
| Parakeet Q4_K | **553.3 s** | 6.66 | **83.875 s** | **205.895 J** | **0.097 J** | **29.065 J** | **235.057 J** | **2.802 W** | **0.993 J** | **378.0 MiB** |

Against F16, Q4_K used 23.8% less process CPU time, 23.3% less compute-rail energy, 8.6% less
average compute power, and 25.5% less peak PSS. Against Moonshine it used 20.6% less CPU time,
36.0% less compute energy, and 52.3% less peak PSS. Moonshine's average watts were lower because it
used fewer cores, but it ran much longer and therefore consumed more total energy.

GPU use was negligible: 0.268 J for F16 and 0.097 J for Q4_K, below 0.1% of their compute-rail
energy. This matches the build configuration: the current `parakeet.cpp` Android runtime enables
the CPU backend and disables Vulkan/CUDA/Metal. No Tensor GPU or TPU acceleration is being claimed.

Perfetto tracing affected wall latency, especially for Moonshine, so the first clean untraced table
remains the latency comparison. The traced runs are used for CPU time and energy. F16 began at
thermal status 0 and 33.8 °C; Q4_K began at status 0 and 34.8 °C after the user accepted the small
temperature difference. Both reached status 1. Q4_K retained its efficiency advantage despite the
warmer start.

## Quality audit

F16 and Q4_K produced identical normalized output on 23 of 24 clips. The only difference was a
proper-name error: F16 preserved `Hidalgo`, while Q4_K produced `Hadalgo`. That single substitution
accounts for the Q4_K increase from 10 to 11 word errors. Name preservation remains a required
dictation gate, but the 23% energy/CPU reduction, 25% memory reduction, 31% clean median-latency
reduction, and 51% model-size reduction justify using Q4_K as the provisional candidate while F16
remains the diagnostic quality reference.

Several remaining Parakeet errors are sensitive to the reference's archaic spelling or tokenization
(`befal`/`befall`, `every one`/`everyone`, and `bedimmed`/`be dimmed`). Both variants also made the
same genuine lexical/name errors on `Toledans` and `Timaeus`. A dictation corpus with protected
names, numbers, paths, versions, and technical terms is required before selection.

Moonshine sometimes emitted a leading `Yeah.`, introduced segmentation-related duplicate words,
and varied across repeats. Its conversion of spoken number words to digits is semantically useful
but is penalized by this deliberately simple WER normalization. Raw punctuation/case behavior and
numeric semantic equivalence therefore need separate scoring in the dictation qualification set.

## Contaminated run exclusion

An earlier F16 run (`20260818T050958Z-parakeet-f16`) produced the same 1.69% WER but contained one
345,843 ms inference for a 2,990 ms clip. The user was actively using the phone, Gmail later showed
sustained one-core CPU use, memory pressure was high, and the run eventually reached thermal status
1. That run is retained locally for diagnosis but excluded from latency comparison. After the phone
was released, Gmail was force-stopped without clearing its data; the clean F16 maximum was
3,772.7 ms and the same output remained deterministic.

## Reproducibility

- `parakeet.cpp`: v0.5.0 commit `1bfbebfaaf493866f49597cd3b7901959d395c60`
- ggml submodule: `e705c5fed490514458bdd2eaddc43bd098fcce9b`
- Parakeet C API ABI: 6
- Android NDK: `28.0.13004108`; CMake: `3.31.6`; Android API: 31; ABI: `arm64-v8a`
- F16 GGUF SHA-256: `7f9a6376edde6a74592ace48b2ebdc27a1ac972d0be9dfcc29e668d99381faf1`
- Q4_K GGUF SHA-256: `2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf`
- Statically isolated `libparakeet.so` SHA-256:
  `2106f9745b23dc116c2a3d67b1813890bbb8dc2dabd4fc1e60098938cde6a147`
- JNI bridge SHA-256:
  `b556abf75517683409c19b5fe573d0ea5d1e1a4342c28f56ecf46ff2e8ffa29f`
- Android ARM64 OpenMP runtime SHA-256:
  `7998fffd575ef7c17aecafe456e41d84abc4bbf09437dee1755d8963fe36e6ae`
- Clean raw-result SHA-256: F16
  `1eb1517e7233987f05e7e5a1b9acdc5bbcce61a66c68385de35a3832b64b8960`, Q4_K
  `05dd461c9650f175abc433e11ca608ae565d75e36e0c4d33338a13428f594dbd`, Moonshine
  `a368e00ddcd348c325c14bef44e9ca80c08daa4ab8075827d4a1226c43a9ee2e`
- Energy-run raw-result SHA-256: F16
  `f4fffc57aa992e9e83a2e456b13151332b8bfd0c7d55e6f76066fe41f4ed133d`, Q4_K
  `36db175860b8bb8e37498f7404d1802fc109a5b2b21d2b7072fbeeceabb1e05f`, Moonshine
  `5264c8aea0570b318c9c91bf7a984ef91ab726491ab81d87a9498cce99d6b162`
- Perfetto power-trace SHA-256: F16
  `70e3d9dba53f2c9aafa26840a7898830f6566c6b6d9ca18c6165e53cb1f6ae99`, Q4_K
  `5ea0f1d439a3b527707776d2c998154a6a3b9b70924e45628fa170104f555427`, Moonshine
  `a852639b1cda1efe7cfa157e8c30ae243ea3b7317bf1db21e51cd8afae1dfade`
- Perfetto trace processor: v57.2, published binary SHA-256
  `98a41b80e9f60da0373d64aff6455681f8c26b7c391ae5736324a5b11e3dacc2`

Raw audio, models, native build outputs, and raw JSONL results remain under ignored paths and are
not committed. The aggregate report contains enough hashes to identify the exact local evidence.

## Next qualification

1. Keep Q4_K as the provisional deployment candidate and F16 as the non-quantized quality
   reference. Reopen the choice if Q4_K shows systematic name/number/technical-token regression.
2. Add file-fed dictation audio covering names, numbers, corrections, commands/questions, technical
   terms, pauses, and long-form speech; score protected-token preservation separately from WER.
3. Integrate Parakeet's streaming/end-of-utterance path behind `SpeechToTextEngine` and measure
   partial-result responsiveness plus Stop-to-final latency with the microphone lifecycle unchanged.
4. Recheck cold model load, sustained thermal behavior, and offline reuse before replacing the
   provisional Moonshine engine.
