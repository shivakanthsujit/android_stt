# GPT-5.6 Luna versus Sotto B epoch 2: Pixel comparison

Date: 2026-08-18

Status: local direct and joined measurements complete; hosted joined run pending an authorized API
credential

Policy: `docs/evaluation/PERSONAL_CLEANUP_ACCEPTANCE.md` version 1

## Interim decision

The new Sotto B epoch-2 checkpoint is not a deployment candidate. Its Pixel Q4_K_M result remains
15/20 acceptable on direct cleanup, applies only 1/3 corrections, realizes 0/3 formatting
directives, and has raw semantic failures. In the Parakeet-fed run it is about 13/20 acceptable by
manual review; the failures include STT damage as well as the same correction and formatting gaps.
A guardrail fallback does not change that raw-model decision.

The existing GPT-5.6 Luna direct-text run remains the quality leader at 20/20 acceptable, 3/3
corrections, and 3/3 formatting. It is also interactive at 649 ms median total service latency.
The requested Luna cleanup of the exact Parakeet outputs has not been sent: this machine has no
`OPENAI_API_KEY`, and the only historical key located during the session is in macOS Trash. That
credential was not restored or used without explicit authorization. The E2E comparison is
therefore intentionally incomplete rather than reconstructed from different text.

## Fixed candidates and data

- STT: pinned `parakeet.cpp` 0.5.0 TDT/CTC 110M Q4_K, unchanged from the selected Pixel path.
- Local cleanup source: clean-base Sotto B epoch 2,
  `dante:/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty/checkpoint-542`.
- Source `model.safetensors`: 708,984,464 bytes; SHA-256
  `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6`.
- Pixel cleanup artifact: Q4_K_M, 229,310,336 bytes; SHA-256
  `02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0`.
- Hosted cleanup: API alias `gpt-5.6-luna`, Chat Completions streaming,
  `reasoning_effort=none`, temperature 0.1, seed 23, frozen `baseline_rules` prompt, Android output
  caps, and raw-output scoring.
- Direct corpus: evaluation-only personal conversation v3, 20 cases, SHA-256
  `667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`.
- E2E audio: the existing 20 Qwen3-TTS Ryan v3 clips, 184.48 seconds total. These are deterministic
  synthetic plumbing and lexical-regression fixtures, not human-dictation qualification.
- Projected hosted E2E cases: the exact post-filler `model_input` from the measured Parakeet run,
  SHA-256 `da06db852d91dedbbc121c60cf548f3e94d4f3d00e2ab4b5b786e0879d126a47`.

The checkpoint and raw personal results remain ignored outside Git. No committed evaluation text,
expected output, model result, VoiceInk prompt, or blind-v2 material was used for training,
demonstrations, retrieval, preferences, or checkpoint selection.

## Direct transcript-to-cleanup quality

Local Pixel metrics use the first output for case-level scoring and three measured repeats for
timing, after one model warm-up. Luna metrics are from the existing one-call-per-case sequential
API run. Relaxed acceptability is a manual semantic metric; strict and literal-anchor scores remain
reproducible diagnostics.

| Metric | GPT-5.6 Luna API | Sotto B epoch-2 Pixel Q4_K_M |
|---|---:|---:|
| User-acceptable | **20/20** | 15/20 |
| Strict exact | **12/20** | 8/20 |
| Normalized exact | not recorded in prior hosted summary | 9/20 |
| Literal anchors | **55/61** | 46/61 |
| All-anchor cases | **15/20** | 10/20 |
| Correction semantic success | **3/3** | 1/3 |
| Formatting directive success | **3/3** | 0/3 |
| Raw semantic-safety failures | 0/20 on active v3 | 2/20 |
| Guardrail flags / fallbacks | 5/20 flags | 1/20 cases, 3/60 calls |

Sotto's five rejected direct cases are 011, 014, 017, 019, and 020. Case 011 removes protected
exclusivity while mishandling the recipient correction; 014, 017, and 019 do not realize the
dictated bullet, numbered, and paragraph formatting; 020 retains the superseded five-minute
alternative. The guard catches 020 but misses 011. Output was stable across all three measured
repeats.

Relative to the checkpoint's earlier single BF16 A6000 run, Q4 preserves the same 15/20 manual
acceptability and 8/20 strict score but falls from 50/61 to 46/61 literal anchors. Most of that
anchor difference is equivalent word-versus-digit rendering, but the missing exclusivity in case
011 is substantive. Quantization therefore did not repair the product failures and cannot be
declared semantically neutral from literal diagnostics alone.

## Direct latency, speed, memory, and energy

| Metric | GPT-5.6 Luna API | Sotto B epoch-2 Pixel Q4_K_M |
|---|---:|---:|
| Calls measured | 20 | 60 |
| Model load | managed service | 728 ms |
| TTFT median / p95 / max | 514 / 765 / not recorded ms | **159 / 449 / 733 ms** |
| Total median / p90 / p95 / max | 649 / not recorded / 948 / 1,033 ms | **481** / 1,562 / 1,767 / 2,682 ms |
| Sequential throughput | not retained in prior direct summary | 1.43 calls/s summed service time |
| Decode rate | not exposed | 38.0 tokens/s median |
| Peak process PSS | not exposed | 669,140 KiB |
| Peak native heap | not exposed | 483,788,048 bytes |
| Max Android thermal status | not applicable | 0 (`NONE`) |
| Pixel inference compute energy | not applicable to Mac-origin API run | 161.62 J / 60 calls |
| Pixel compute energy per call | not measurable for API | 2.69 J |
| Pixel inference compute power | not measurable for API | 3.84 W |

Luna used 2,388 input and 535 output tokens. At the 2026-08-18 standard Luna rates of $0.20 per
million input tokens and $1.20 per million output tokens, the direct 20-case run is about $0.00112,
or $0.000056 per similarly sized request. API usage reports tokens rather than an authoritative
bill; account billing remains the source of truth.

There is no honest energy winner across these two columns. Local rails cover Pixel CPU, GPU, and
memory/fabric compute. OpenAI does not report per-request server energy, and the prior hosted run
originated on the Mac, so it also provides no Pixel radio-energy measurement.

## Audio-to-Parakeet-to-local-cleanup result

All 20 clips completed. Parakeet loaded in 109 ms and Sotto loaded in 821 ms. Parakeet reached
8/20 strict and 15/20 normalized STT matches. Local raw cleanup reached 6/20 strict and 8/20
normalized intended-cleanup matches; the guarded result was identical on those metrics with two
fallbacks.

Manual review accepts about 13/20 final raw cleanup outputs. The seven rejected cases are:

- 009: Parakeet changes the intended 6:20 time.
- 011: cleanup retains superseded recipient content and falls back.
- 012: Parakeet damages protected personal names.
- 014: cleanup omits required bullet formatting.
- 017: Parakeet damages a name and cleanup omits numbered formatting.
- 019: cleanup omits the requested paragraph break.
- 020: cleanup retains the superseded five-minute alternative and falls back.

This separates the bottlenecks: Parakeet remains strong on ordinary normalized text but needs
human/multi-speaker protected-name and number qualification, while Sotto independently continues
to fail correction and formatting behavior.

| Local joined metric | Result |
|---|---:|
| Audio duration | 184.48 s |
| STT median / p90 / max | 764 / 2,230 / 2,733 ms |
| Cleanup median / p90 / max | 784 / 2,064 / 2,489 ms |
| Cleanup TTFT median / p90 / max | 393 / 692 / 805 ms |
| Pipeline median / p90 / max | 1,552 / 4,614 / 5,224 ms |
| Cleanup decode rate | 22.0 tokens/s median |
| Peak process PSS | 920,517 KiB |
| Peak native heap | 727,687,008 bytes |
| Max thermal status | 0 (`NONE`) |

The direct cleanup decode rate falls from 38.0 to 22.0 tokens/s when Parakeet and Sotto are resident
together, consistent with higher memory pressure. The joined process peaks near 899 MiB PSS versus
about 653 MiB for cleanup alone.

## Joined Pixel power

| Measured stage | Calls | Duration | Compute energy | Per utterance | Average compute power |
|---|---:|---:|---:|---:|---:|
| Parakeet STT | 20 | 20.99 s | 76.19 J | 3.81 J | 3.63 W |
| Sotto cleanup | 20 | 20.85 s | 67.50 J | 3.37 J | 3.24 W |
| Sum of attributed stages | 20 pipelines | 41.84 s | 143.69 J | 7.18 J | not additive |

The complete 57.29-second joined trace measured 175.60 J on CPU/GPU/memory compute rails and
277.83 J across all available rails. Those wider figures include loading, orchestration, display,
cellular/modem, WLAN, and other overlapping device activity and must not be presented as pure
inference energy. GPU attribution was negligible because both current inference paths are CPU-only.

## Remaining hosted E2E run

Once an authorized key is available, run Luna on the projected 20-case file without changing the
prompt or cases. Combine those hosted cleanup timings with the exact measured Parakeet times. The
result must be labeled as Pixel Parakeet inference plus a Mac-origin hosted request: it excludes
ADB/host handoff and Pixel network/radio energy. Review every raw output and report correction,
formatting, protected-name/number behavior, strict/normalized scores, latency, token usage, and
paid-equivalent cost. Do not infer cloud power draw from the local rails.

## Reproducibility identities

- Direct local result:
  `828a945c94f1c8b9a17ab21d44ce3d17d133c2f3eaa67dfd531d2c8ab7a22e90`
- Direct local summary:
  `1053d5fe0341da89bc463f3dcb6a60241e1a7ac36157c0d60f3c5a25e32d5d18`
- Direct local power summary:
  `aa67b7bb757b8c756ec4bb7e54e7ac3b24fa456ecae274f9962065c7ddfa90f4`
- Existing direct Luna result:
  `b40f13efd5a407da51da35bff53cb38250c8f2f236a9416a6c3083ec613e76e4`
- Joined local result:
  `0471a0083e291b7e974563c0479300ca2177f67198314474c41a0c0e3bf78d78`
- Joined local summary:
  `c355f398c18f76ea44ca0ba82a36150506707c1beb8eea76041eddfb9bfa93e1`
- Joined STT power summary:
  `06288157ef45928767749d950fae7733861e6d2ae0d663bc55e27a30b31b0cf3`
- Joined cleanup power summary:
  `4e5006a7cd0622b47da001e65b5eeb7c652507331f5747d3fa52dc9ef0ff44cc`

Raw results, traces, audio, model files, checkpoint files, and projected personal API input remain
ignored. This committed report contains only aggregate metrics, case IDs, failure classes, and
cryptographic identities.
