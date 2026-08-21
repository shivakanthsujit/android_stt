# S1-mini direct llama.cpp Pixel 7 comparison

Date: 2026-08-22

Status: Stage 2 CPU comparison complete; direct llama.cpp rejected as a production replacement

## Outcome

The collision-isolated, project-owned llama.cpp runtime did not earn a production swap. With the
exact same S1-mini Q4_K_M GGUF and publisher contract, its initial selected CPU configuration was
only 1.0% faster than tuned LEAP at median total latency on the frozen stress-weighted
non-evaluation corpus and used about 4.0% more peak PSS. A fresh-thermal confirmation of that same
direct configuration was 16.4% slower than the matched LEAP run. The result is too variable and
far below the required repeatable 15% median improvement with no p90, memory, energy, or thermal
regression.

A corrected user-shaped, LEAP-first/direct-second comparison confirmed the decision on the
ordinary workload: direct was 9.3% slower at median total latency, 7.2% slower at p90, used 8.8%
more median process CPU, and reached thermal status 1 while LEAP remained at 0. Direct used 1.8%
less median PSS, but that isolated memory difference cannot offset the latency/CPU/thermal losses.

Production therefore remains LEAP 0.10.9 with explicit two CPU threads, context 2,560, cache off,
and mmap on. No production runtime, prompt, model bytes, quantization, microphone path, or cleanup
insertion policy changed.

Every benchmark request contained exactly one cleanup transcript. llama.cpp's `n_batch` and
`n_ubatch` are internal prompt-token capacities for that one request; they are not concurrent
request batching. The model/context owner and benchmark worker remained single-threaded at the
request level, and all transcripts ran sequentially.

## Fixed scope and identities

- Pixel 7 `panther`, ARM64, Android SDK 37, serial `33040DLH20004E`.
- S1-mini Q4_K_M: 484,219,808 bytes; SHA-256
  `3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634`.
- Direct runtime: llama.cpp commit `ece963f41b0b02d7a0d61436ae365762c073a4c8`, build 10450,
  NDK `28.0.13004108`, CMake `3.31.6`, CPU only.
- Release APK: 18,701,319 bytes; SHA-256
  `8931caef1a33acc84c9eb173d4d09d986f71ea0f6816716e3a3e93ce05b1bfad`.
- Selected Pixel backend: `libggml-cpu-android_armv8.2_2.so`.
- Shared runtime invariants: context 2,560, mmap on, GPU layers zero, greedy decoding, embedded
  template with thinking disabled, exact publisher control, fixed 78-token prompt overhead, fresh
  KV state per request, and publisher cap `ceil(1.3 * raw_tokens + 32)`.

All accepted performance arms began at Android thermal status 0. The screen was explicitly put to
sleep between arms and each next arm waited for status 0. Android's status is coarse: later
thermal onset and large same-configuration run variance show that status 0 does not imply identical
skin temperature or headroom.

## Contract, host, and cap evidence

The initial direct Pixel smoke exactly matched the host golden's raw token IDs, rendered prompt
bytes, prompt token IDs, and output caps on every row. A pinned host `llama-server` run with the
same GGUF, template, greedy sampler, and per-input caps then matched the direct Pixel raw outputs on
3/3 smoke cases. The host server's `tokens_predicted` includes terminal EOG while the Android
completion count excludes it; this is a documented counter convention, not a generation mismatch.

A matched LEAP smoke used the same three transcript-only cases, one warmup, one measured pass,
context 2,560, two threads, cache off, and no microphone. Prompt-token counts and output caps
matched 3/3. Raw output matched 2/3: direct/host produced `Café东京`, while LEAP produced
`Café 东京`. The fixture has no expected answer, so this is recorded as a stable runtime output
difference rather than a quality judgment. It independently blocks an unreviewed silent runtime
swap.

The project-authored cap fixture has SHA-256
`f31c93c996ce4bce821e70da64bd56831459f7bc3250a5ae1438da8bd5a413df`. Its three synthetic
repetition inputs naturally reached caps 56, 53, and 57 through the unchanged greedy contract on
the pinned host. On Pixel, one warmup plus two measured repeats completed without errors; all 6/6
measured calls reported `finish_reason=token_cap`, completion count equal to the requested cap,
stable output/token IDs, fixed prompt delta 78, and thermal status 0. This proves the actual
personal-use capped-output fallback signal without lowering a cap, ignoring EOS, or changing
sampler behavior.

## Frozen single-request stress corpus

The first performance fixture is project-authored, transcript-only, and contains no expected
output or evaluation data. Its SHA-256 is
`a05f56a5c845cec76c9b3baa1b0b7368fe4cc95e1591a67903e7265dbfbab1b4`. It freezes 12 cases:
four short, four medium, and four long, covering filler, punctuation, Unicode, paragraphs, and
unpunctuated prose. Exact raw-token ranges are 8–21, 39–56, and 126–164. The longest rendered
prompt is 242 tokens and the largest prompt-plus-output-cap-plus-EOG budget is 489, safely below
context 2,560.

This corpus deliberately overweights long work: 4/12 cases are 126–164 raw tokens. A post-tuning,
raw-input-only audit of personal-v3 found a median of 18 tokens, 16/20 cases at 13–28 tokens, and
only four longer cases at 46/62/70/80 tokens. The matrix below is therefore a useful sustained
decode/thermal stress profile, not the final estimate of ordinary owner latency. Direct was
slightly worse than LEAP on the stress corpus's short and medium subsets and benefited mainly on
its oversized long cases, so this weighting does not hide a direct-runtime win. A second
project-authored, user-shaped transcript-only fixture was therefore added for a matched
LEAP/direct confirmation without reopening CPU tuning or using private expected outputs.

Every arm ran one warmup and three repeat-major measured passes, for 36 measured sequential
requests. The first direct baseline and matched LEAP control each produced stable outputs on all
12 cases; prompt-token counts, output caps, and raw outputs matched 36/36.

## Same-GGUF baseline comparison

| Metric | Direct 2/2, 512/512, flash off | Tuned LEAP | Direct change |
|---|---:|---:|---:|
| Median total | 2,607.8 ms | 2,633.0 ms | -1.0% |
| p90 total | 7,942.9 ms | 8,413 ms | -5.6% |
| Median TTFT | 1,001.6 ms | 986.5 ms | +1.5% |
| p90 TTFT | 1,855.3 ms | 2,200 ms | -15.7% |
| Median process CPU | 5,013.5 ms | 5,071 ms | -1.1% |
| Median decode rate | 26.15 tok/s | 16.73 tok/s | +56.3% |
| Peak PSS | 1,173,733 KiB | 1,128,518 KiB | +4.0% |
| Peak native heap | 1,109,669,008 B | 1,113,759,456 B | -0.4% |
| First measured thermal 1 | call 33 | call 15 | later, but order-confounded |

Direct decode was materially faster, especially on long cases, but prompt evaluation and runtime
variance left total median effectively tied. The direct run occurred before the LEAP run; although
both runners required thermal status 0, residual temperature makes thermal onset and tail latency
directional rather than a clean causal runtime comparison. That uncertainty cannot rescue a
candidate which misses the median and memory gates.

No Perfetto energy trace was advanced for direct llama.cpp because it already failed the latency,
repeatability, PSS, and thermal selection gates. Energy evidence is required to select a candidate,
not to reject one that cannot reach the earlier advancement bar.

## User-shaped matched confirmation

The representative fixture has SHA-256
`48c2af5358951305bad1d87ecfbb26bcc206c72f783159affe4687aaf49878e3`. Its 10 authored
transcripts cover a short message, reminder, grocery list, uncertainty, a natural correction,
formatting request, ordinary names/numbers, and brief journal notes. Exact raw-token counts are
18–26 for eight cases and 51/53 for two cases; median is 22 and the largest context budget is 233
tokens. It contains only `id`, `raw`, and `categories` and copies no private-evaluation text or
expected output.

To counterbalance the earlier stress-run order, tuned LEAP ran first from thermal status 0. After
the screen-off cooldown returned the Pixel to status 0, direct 2/2 threads, 512/512, mmap on, flash
off ran second. Each runtime handled one warmup plus 30 measured sequential requests. Both were
stable; prompt-token counts, caps, and raw outputs matched 30/30, with no blanks or cap hits.

| Metric | Tuned LEAP | Direct llama.cpp | Direct change |
|---|---:|---:|---:|
| Median total | 1,486.0 ms | 1,624.0 ms | +9.3% |
| p90 total | 2,843 ms | 3,048.0 ms | +7.2% |
| Median TTFT | 741.5 ms | 813.0 ms | +9.6% |
| p90 TTFT | 975 ms | 1,018.7 ms | +4.5% |
| Median process CPU | 2,870.0 ms | 3,122.5 ms | +8.8% |
| p90 process CPU | 5,471 ms | 5,862 ms | +7.1% |
| Median PSS | 1,108,521 KiB | 1,088,479 KiB | -1.8% |
| Peak PSS | 1,108,976 KiB | 1,092,359 KiB | -1.5% |
| First measured thermal 1 | none | call 28 | worse |

Direct lost 28/30 paired total-latency requests. Its per-repeat median disadvantage grew from 4.4%
to 6.0% to 11.8%, while LEAP stayed thermal 0. This profile is much closer to the owner's actual
dictation shape than the long-form stress matrix and directly rejects a C++ runtime speed claim for
the product workload.

The direct model-load sample was an anomalous 9,548 ms versus 1,949 ms for LEAP and roughly 1 s in
the other direct runs. Load occurs outside the per-request values above. One sample is insufficient
to attribute the spike, so it is retained and reported but not used as a stable runtime claim.

## CPU tuning results

All values below are the scorer's 36-request aggregates. `First T1` is the first measured request
whose post-call Android thermal status was 1.

| Direct configuration | Median / p90 total | Median TTFT | Decode | Median CPU | Peak PSS | First T1 | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| gen 2, batch threads 2, 512/512, flash off | 2,607.8 / 7,942.9 ms | 1,001.6 ms | 26.15 tok/s | 5,013.5 ms | 1,173,733 KiB | 33 | baseline |
| gen 3 | 3,168.7 / 9,548.8 ms | 1,182.2 ms | 21.32 tok/s | 7,870.0 ms | 1,102,494 KiB | 10 | reject |
| gen 4 | 3,522.7 / 10,521.3 ms | 1,187.8 ms | 19.69 tok/s | 10,950.5 ms | 1,177,036 KiB | 9 | reject |
| batch threads 4 | 2,717.2 / 8,514.3 ms | 692.5 ms | 23.16 tok/s | 6,478.5 ms | 1,144,147 KiB | 10 | reject |
| batch/ubatch 512/256 | 3,042.0 / 8,631.1 ms | 1,098.2 ms | 24.61 tok/s | 5,848.5 ms | 1,129,792 KiB | 10 | reject |
| batch/ubatch 256/256 | 2,708.5 / 8,833.3 ms | 1,033.8 ms | 25.33 tok/s | 5,200.0 ms | 1,139,646 KiB | 11 | reject |
| flash attention on | 2,405.5 / 9,061.4 ms | 878.5 ms | 28.47 tok/s | 4,608.0 ms | 1,118,101 KiB | 10 | reject |
| baseline confirmation | 3,065.5 / 9,198.8 ms | 1,134.4 ms | 24.55 tok/s | 5,882.0 ms | 1,159,156 KiB | 10 | no repeatable win |

Generation threads 3 and 4 preserved output/token parity 36/36 but regressed sustained median
total by 23.6% and 31.2%, raised process CPU by 60.8% and 108.8%, and moved thermal onset to calls
10 and 9. Six/eight generation threads were therefore not run.

Four batch threads improved prompt evaluation about 31%, but decode slowed 17%, sustained total
regressed 2.5%, CPU rose 29%, and thermal onset moved to call 10. Batch threads 6/8 were not run.

The 512/256 and 256/256 settings only change internal buffers for one prompt; they never group
requests. Both preserved output/token parity 36/36. They reduced native heap about 14%, but
sustained total regressed 16.8% and 4.4%, respectively, and thermal onset moved to calls 10/11.
The 128-token arms were outside the advancement band and were not run.

Flash attention improved sustained median total 5.8% and peak PSS 4.7%, but regressed sustained p90
22.7%, moved thermal onset to call 10, and changed one case's punctuation consistently across all
three repeats. Its raw-output parity was 33/36. It failed both performance-tail and output gates.

The fresh-thermal baseline confirmation exactly matched the first baseline's outputs and token IDs
36/36, but its overall/sustained median totals were 17.6%/18.4% slower. Compared with matched LEAP,
the confirmation was 16.4% slower overall and 18.2% slower in sustained repeats. The direct CPU
path therefore has no repeatable latency advantage.

## Decision and next order

- Keep tuned LEAP as the production S1-mini runtime.
- Preserve the isolated direct APK, fixtures, runner, and raw evidence as a reproducible negative
  comparison; do not integrate a second llama/ggml stack into the production process.
- Do not expand CPU thread or token-buffer searches. The bounded matrix found clear stop points.
- Do not interpret internal `n_batch`/`n_ubatch` as product request batching; production cleanup
  remains one transcript at a time.
- Skip a direct Mali GPU build in this pass. It would be a separately compiled experimental
  runtime with additional driver and memory risk, while the project-owned CPU runtime already
  failed to justify ownership. Revisit only as an explicitly scoped experiment.
- Proceed to Stage 3: convert the exact pinned S1-mini BF16 checkpoint on the Linux RTX A6000 host
  to a metadata-verified blockwise-32 INT4/FP32 LiteRT-LM artifact. Do not use the GGUF, generic
  Qwen weights, channelwise/block-128 recipes, or smaller quantization.

## Retained artifact hashes

| Evidence | SHA-256 |
|---|---|
| matched LEAP smoke raw JSONL | `793c531f235c9499408bef20158b12946bbf1e861b4d203c4770c1ac0c382f87` |
| direct cap raw JSONL | `44f6ec86fd152b1efce43f832be2fab05f1be1d9416fbe852068636de2c47294` |
| direct cap summary | `84dfe180ff95c3e60861782f2c1132b3aa00702cf03dbb0ed39845ebad2f3bdf` |
| direct baseline raw JSONL | `9f37f3d89d60ac76f062216675bbca3df7dcf7f79ab67ac4126a43808c328394` |
| direct baseline summary | `4429f850c17e6ffaa5266f15fc9f49374d644e19c664bf0310c1e59bcbe46ba3` |
| matched LEAP performance raw JSONL | `0a0b9aaaafb3b0455986f3189c599f5308d38375d263458a43bce215ea742141` |
| generation-3 raw JSONL | `f3ab33961d5fb7a229d91f0c1ce4927f58e9d6fe8d353bc3c8305d94a4e54dae` |
| generation-4 raw JSONL | `0cc2813f83f9d988940d7de3f23b09e96e6438478b377ee71a22e69a0a4ea2b3` |
| batch-threads-4 raw JSONL | `e61df7352362ce4cde8fb8385006e8cfe9a2c757a3b05936a61bb5a6a438e07d` |
| 512/256 raw JSONL | `a789b584b57b0a5c842b230379f94f5d70485d447ce5ec5cb99b6874d38703af` |
| 256/256 raw JSONL | `122b014cabfed023141929b935d50fa02ce0b63959aaf53bbac92f7255fda430` |
| flash-on raw JSONL | `3318a60d7f4a84888764d826d956b9a4c89712aba198a786b980f69ade7d938d` |
| baseline confirmation raw JSONL | `6b082f2e7d5046ba168ace1ec4bd45c5f3520cb0f1ff3063051c0d401af1ed75` |
| representative LEAP raw JSONL | `7954f993e09efcd8490ec4a816a98c4f8f194e2f1d12da2ec043a1c519cca80a` |
| representative direct raw JSONL | `92e0b1a05ca235db6de41d0b918cd59679eda8c92869bd6b3fa3c8d311216045` |
| representative direct summary | `18f8a8842e7e4010c663125cb637d9c0f0b675af80bb321084c3dffd2bbddee0` |

Raw JSONL, summaries, manifests, model bytes, APKs, and build caches remain ignored outside Git.
Only the transcript-only fixtures, tooling, tests, and this summarized evidence are committed.
