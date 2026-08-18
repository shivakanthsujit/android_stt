# GPT-5.6 Luna versus Sotto B epoch 2 on Pixel

Date: 2026-08-18

Status: direct and Parakeet-fed comparison complete

Policy: `docs/evaluation/PERSONAL_CLEANUP_ACCEPTANCE.md` version 1

## Decision

GPT-5.6 Luna is the clear quality leader for the active personal workflow. It reaches 20/20
acceptable on direct cleanup and 17/20 acceptable after the measured Parakeet outputs, versus
15/20 and about 13/20 for local Sotto B epoch-2 Q4_K_M. Luna applies all three corrections and all
three explicit formatting directives in both scopes. Sotto applies only 1/3 corrections and none
of the formatting directives.

Neither candidate passes the project's raw deployment gate:

- Sotto has two direct raw semantic failures and retains the same correction defects in the joined
  run. Guardrail fallback cannot qualify it.
- Luna is safe on all 20 direct inputs, but on joined case 012 it changes Parakeet's protected
  `ICO` token into a first-person contraction. This changes who performs the action instead of
  recovering the intended name. The guardrail flags the row, but raw-output safety still fails.

Luna therefore becomes the leading optional hosted/personal candidate, not a qualified automatic
cleanup backend. It also trades away offline privacy and availability. Sotto B remains a local
research/runtime result and must not replace the public integration placeholder.

## Fixed candidates and data

- STT: pinned `parakeet.cpp` 0.5.0 TDT/CTC 110M Q4_K, unchanged.
- Local cleanup source: clean-base Sotto B epoch 2,
  `dante:/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty/checkpoint-542`.
- Source `model.safetensors`: 708,984,464 bytes; SHA-256
  `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6`.
- Pixel cleanup artifact: Q4_K_M, 229,310,336 bytes; SHA-256
  `02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0`.
- Hosted cleanup: API alias `gpt-5.6-luna`, Chat Completions streaming,
  `reasoning_effort=none`, `stream_options.include_usage=true`, temperature 0.1, seed 23, frozen
  `baseline_rules` prompt, Android output caps, and raw-output scoring.
- Direct corpus: evaluation-only personal conversation v3, 20 cases, SHA-256
  `667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`.
- E2E audio: the existing 20 Qwen3-TTS Ryan v3 clips, 184.48 seconds total. These are synthetic
  plumbing and lexical-regression fixtures, not human-dictation qualification.
- Hosted E2E input: the exact post-filler `model_input` from the measured Parakeet run, joined with
  the cleanup rather than spoken-surface anchor contract; SHA-256
  `027819989c3a7a31d83028a31f978f5c25c13d213084dbb880540f130300b78b`.

The checkpoint, GGUFs, raw personal results, projected API inputs, audio, and traces remain ignored
outside Git. No evaluation text, expected output, model result, VoiceInk prompt, or blind-v2
material was used for training, demonstrations, retrieval, preferences, or checkpoint selection.

## Direct transcript-to-cleanup quality

Local Pixel quality uses the first output and timing uses three measured repeats per case after one
model warmup. Luna uses one sequential request per case. Relaxed acceptability is the primary manual
semantic metric; strict and literal-anchor scores remain surface-sensitive diagnostics.

| Metric | GPT-5.6 Luna API | Sotto B epoch-2 Pixel Q4_K_M |
|---|---:|---:|
| User-acceptable | **20/20** | 15/20 |
| Strict exact | **11/20** | 8/20 |
| Literal anchors | **54/61** | 46/61 |
| All-anchor cases | **14/20** | 10/20 |
| Correction semantic success | **3/3** | 1/3 |
| Formatting directive success | **3/3** | 0/3 |
| Raw semantic-safety failures | **0/20** | 2/20 |
| Guardrail flags / fallbacks | 6/20 flags | 1/20 cases, 3/60 fallback calls |

Luna's nine strict differences are equivalent number/time/currency surfaces, curly apostrophes,
an accepted pronoun surface, and the user-accepted collapse of duplicated emphasis. It preserves
names, facts, exclusivity, negation, uncertainty, and dictated questions while applying every
correction and formatting directive. The non-dated API alias is not immutable: this canonical run
is 11/20 strict and 54/61 anchors, versus 12/20 and 55/61 in the earlier retained run, although both
are 20/20 acceptable.

Sotto's rejected cases remain 011, 014, 017, 019, and 020. It removes protected exclusivity while
mishandling the recipient correction, omits all three requested formats, and retains the
superseded five-minute alternative. The guard catches case 020 but misses case 011. Output is
stable across all measured repeats.

## Direct latency, speed, memory, energy, and cost

| Metric | GPT-5.6 Luna API | Sotto B epoch-2 Pixel Q4_K_M |
|---|---:|---:|
| Calls measured | 20 | 60 |
| Model load | managed service | 728 ms |
| TTFT median / p90 / p95 / max | 630 / 961 / 1,081 / 1,117 ms | **159** / 410 / 449 / 733 ms |
| Total median / p90 / p95 / max | 836 / **1,119 / 1,127 / 1,241 ms** | **481** / 1,562 / 1,767 / 2,682 ms |
| Sequential service throughput | 1.20 calls/s | 1.43 calls/s |
| Decode rate | not exposed | 38.0 tokens/s median |
| Peak process PSS | service-side not exposed | 669,140 KiB |
| Peak native heap | service-side not exposed | 483,788,048 bytes |
| Max Android thermal status | not applicable | 0 (`NONE`) |
| Pixel inference compute energy | not measurable for API | 161.62 J / 60 calls |
| Pixel compute energy per call | not measurable for API | 2.69 J |
| Pixel inference compute power | not measurable for API | 3.84 W |

Luna reports 2,388 input and 534 output tokens. At the captured standard rates of $0.20 per million
input and $1.20 per million output tokens, the direct run is $0.001118 paid-equivalent, or about
$0.000056 per request. API totals include Mac-to-service network/service time; local totals are
on-device inference. Neither is a hardware-normalized comparison.

## Audio-to-Parakeet-to-cleanup quality

All 20 clips complete through both cleanup backends. Parakeet is identical on both sides: 8/20
strict and 15/20 normalized STT exact. Final cleanup quality is:

| Metric | Parakeet → Luna | Parakeet → Sotto B Q4_K_M |
|---|---:|---:|
| User-acceptable final text | **17/20** | about 13/20 |
| Strict intended-cleanup exact | **9/20** | 6/20 |
| Literal anchors | **53/61** | not retained by joined scorer |
| Correction semantic success | **3/3** | 1/3 |
| Formatting directive success | **3/3** | 0/3 |
| Cleanup-model raw semantic failures | 1/20 | 2/20 |
| Guardrail flags / fallbacks | 4 flags | 2 fallbacks |

Luna's three final-text failures are:

- 012: Parakeet damages the protected names and Luna additionally reinterprets `ICO` as a
  first-person contraction. This is Luna's raw semantic failure; fallback preserves a still-wrong
  STT transcript and cannot qualify the model.
- 017: Parakeet changes `Aiko` to `ICO`; Luna preserves that error while correctly producing the
  numbered list.
- 019: Parakeet changes `Today` to `The day`; Luna preserves that error while correctly producing
  the paragraph break.

Luna also repairs a useful upstream edge case that Sotto misses: Parakeet's awkward recognition of
the 6:20 train time is normalized to the correct time. It applies the recipient and long-form
five-to-ten-minute corrections and every requested list/paragraph structure.

Sotto's seven final failures are 009, 011, 012, 014, 017, 019, and 020. They combine Parakeet
name/time damage with Sotto's recipient correction, long-form correction, and formatting gaps.

## End-to-end latency and speed

Luna pipeline time is the measured Pixel Parakeet inference plus the Mac-origin hosted request.
It excludes ADB/host transfer and does not represent a shipping Pixel network path. Local Sotto is
the contiguous Pixel pipeline.

| Metric | Parakeet → Luna | Parakeet → Sotto B Q4_K_M |
|---|---:|---:|
| Parakeet load | 109 ms | 109 ms |
| Cleanup load | managed service | 821 ms |
| STT median / p90 / p95 / max | 764 / 2,230 / 2,548 / 2,733 ms | same |
| Cleanup TTFT median / p90 / p95 / max | 706 / 1,812 / 1,864 / 2,500 ms | **393** / 692 / 805 / 805 ms |
| Cleanup total median / p90 / p95 / max | 941 / **1,873 / 2,082** / 2,859 ms | **784** / 2,064 / 2,418 / **2,489** ms |
| Pipeline median / p90 / p95 / max | 1,585 / **3,829 / 4,403** / 5,592 ms | **1,552** / 4,614 / 4,650 / **5,224** ms |
| Cleanup sequential throughput | 0.89 calls/s | about 0.96 calls/s |
| Audio / summed pipeline time | 4.25× realtime | 4.41× realtime |

The two pipelines are effectively tied at median latency. Luna has the better p90/p95 tail despite
a slower median cleanup call; Sotto has the better maximum. Service/network variance and the
missing real phone handoff mean the Luna E2E numbers are an engineering estimate, not a final
mobile measurement.

## Device memory and power

| Measured item | Result |
|---|---:|
| Local joined peak process PSS | 920,517 KiB |
| Local joined peak native heap | 727,687,008 bytes |
| Local Sotto cleanup compute energy | 3.37 J/utterance at 3.24 W |
| Parakeet STT compute energy | 3.81 J/utterance at 3.63 W |
| Local attributed STT + cleanup | 7.18 J/utterance |
| Max local joined thermal status | 0 (`NONE`) |

Hosted Luna adds no cleanup model or 229 MB GGUF to device storage, but the exact Pixel memory of a
shipping network client was not measured. The prior Parakeet-only probe peaked at 392,342 KiB PSS
on a different audio workload; it is context, not a matched Luna E2E memory result.

Cloud power has no defensible numeric comparison. OpenAI does not expose per-request server energy,
and these requests originated on the Mac, so Pixel radio/network energy is also absent. The only
measured Luna-side device stage is the shared Parakeet STT energy. Do not call either candidate an
energy winner from these data.

## Hosted usage and paid-equivalent cost

The canonical usage-enabled 40 requests report:

| Scope | Input tokens | Output tokens | Paid-equivalent cost |
|---|---:|---:|---:|
| Direct Luna | 2,388 | 534 | $0.001118 |
| E2E cleanup Luna | 2,375 | 534 | $0.001116 |
| Canonical total | 4,763 | 1,068 | $0.002234 |

An earlier 40-call instrumentation pass completed before streamed usage was enabled. It used the
same inputs, and its completion caps total 1,805 tokens, so its paid-equivalent cost is at most
$0.003119. The full 80-request session is therefore at most $0.005353 at standard rates. The user's
complimentary/shared-data dashboard, not this calculation, is authoritative for actual billing and
data-sharing attribution. A real personal deployment must use the intended private project/key.

## Reproducibility identities

- Luna request-extra configuration:
  `12f869439a7657bc9980c9feabcb1f70c17f1ed0b11dcc40de4edde48912414b`
- Direct Luna result:
  `76d5da132656775bfe9dca4284f1c09d1ebe92aab0365344a3f9c984b174c1f7`
- Hosted E2E case projection:
  `027819989c3a7a31d83028a31f978f5c25c13d213084dbb880540f130300b78b`
- E2E Luna result:
  `dcd91a2baf0d843458e3be29742ef69ece0845ec06ddca36e6e3cb9bd0932666`
- Combined E2E timing summary:
  `b88050098689975a00b5bb3edc6b9085bd89b9c9a60e5f13804a60d74238308d`
- Direct local result / summary / power summary:
  `828a945c94f1c8b9a17ab21d44ce3d17d133c2f3eaa67dfd531d2c8ab7a22e90`,
  `1053d5fe0341da89bc463f3dcb6a60241e1a7ac36157c0d60f3c5a25e32d5d18`, and
  `aa67b7bb757b8c756ec4bb7e54e7ac3b24fa456ecae274f9962065c7ddfa90f4`.
- Joined local result / summary / STT power / cleanup power:
  `0471a0083e291b7e974563c0479300ca2177f67198314474c41a0c0e3bf78d78`,
  `c355f398c18f76ea44ca0ba82a36150506707c1beb8eea76041eddfb9bfa93e1`,
  `06288157ef45928767749d950fae7733861e6d2ae0d663bc55e27a30b31b0cf3`, and
  `4e5006a7cd0622b47da001e65b5eeb7c652507331f5747d3fa52dc9ef0ff44cc`.

Raw results, traces, audio, model/checkpoint files, credential material, and projected personal API
input remain ignored. This committed report contains only aggregate metrics, case IDs, failure
classes, short protected-token identifiers needed to explain safety, and cryptographic identities.
