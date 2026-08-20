# S1-mini v1 exact-contract Pixel 7 benchmark

Date: 2026-08-21

## Outcome

S1-mini v1 Q4_K_M runs successfully on the Pixel 7 through LEAP 0.10.9's Android llama.cpp
backend, and the Android path reproduces the publisher inference contract. At explicit user
direction it is now the preferred ordinary on-device cleanup model, replacing Sotto B as the
integration default. After this benchmark, the owner explicitly adopted a personal-use runtime
policy that accepts every non-empty, non-token-capped generation; the semantic findings below remain
historical research evidence rather than insertion gates.

On the active 20-case personal-v3 workload, raw S1 output is acceptable on 19/20 cases under the
user's control-aware calibration, versus 15/20 for the former local Sotto B baseline. The fixed
publisher control says `Structure: prose`; cases 014 and 017 ask for lists inside the transcript,
so prose output is not treated as an Android failure under this configuration. The remaining real
failure is case 011, which retains the superseded family-group recipient before the corrected
Maya-only instruction. Raw strict exactness remains 11/20, correction success is 2/3, and 54/61
literal anchors are preserved. All 60 measured outputs are stable across repeats, and both dictated
question/command cases remain text rather than being answered.

The runtime cost remains the main product caveat. In the thermal-clean traced run,
median TTFT/total latency is 975.5/1,576 ms, p90 total is 3,840 ms, and long-form median total is
4,025.5 ms. Peak PSS is 1,293,620 KiB. The 60 inference slices consume 389.567 J of compute-rail
energy, or 6.493 J/call at 3.159 W average. A matching untraced run that started at thermal status
0 crossed to status 1 after 27/60 measured calls and reached 1,665 ms median, 4,294 ms p90, and
7,052 ms maximum total latency. This sustained drift is product evidence, not a clean warm-latency
selection.

For comparison, Sotto B epoch 2 measured 481 ms median direct total, 2.69 J/call, and 669,140 KiB
peak PSS on the same Pixel. S1 improves relaxed acceptability by two cases but is about 3.3× slower
at traced median total, 2.4× higher compute energy per call, and 1.9× higher peak PSS. It also
remains behind hosted Luna's 20/20 direct acceptability. The user selected S1 despite this cost
because cleanup quality is the current priority and the intended interaction can tolerate it; this
selection is an integration preference, not a claim that raw S1 passed every deployment gate.

## Publisher contract and parity

The debug-only runner uses:

- the exact system prompt at `docs/evaluation/prompts/s1-mini-v1-system.txt`, SHA-256
  `6ecb6800f96b00cf612631552eff606a829feb2be8449fa95f9f150713b89327`;
- the exact control line
  `[Styling: semi-formal] [Structure: prose] [Context: general]`;
- the GGUF-embedded Qwen3 chat template with `enableThinking=false`, which emits the trained empty
  thinking prefix;
- greedy decoding with `temperature=0`;
- no reasoning-budget override; and
- `max_new_tokens = ceil(1.3 × raw transcript tokens + 32)` for every request.

The host preparation path reads only `id`, `raw`, and categories. Publisher `tokenizer.json`
counts match llama.cpp `/tokenize` on 20/20 personal inputs. Across the complete 69-case seed +
held-out screen, Pixel and Mac raw-token counts and requested output caps match 69/69. The
production engine derives the cap from LEAP's exact templated prompt count minus the measured
fixed prompt/template count; a Pixel runtime assertion independently matched the publisher-
tokenizer-prepared cap on all 45 held-out requests.

Raw Pixel and Mac Q4 text matches exactly on 66/69 cases: 24/24 seed and 42/45 held-out. The three
backend decoder differences are `Deploy only to local.` versus `Deploy to local.`, removal of a
malformed retained correction fragment on heldout-039, and one comma after `You know`. There are
no token-count, cap, system prompt, control line, template, thinking, or decoding-option
differences. This is strong evidence against an Android integration-configuration bug, while also
showing why raw-output semantic review and fallback remain necessary across runtimes. LEAP reports
completion statistics without the terminal token; this does not affect the requested cap or text.

The staged artifact is the official 484,219,808-byte `s1-mini-q4_k_m.gguf`, revision
`8eab4779866f477ae6e7f237ca45fc2c65153f50`, SHA-256
`3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634`. The host and device hashes
were both verified before inference. BF16 Pixel feasibility remains untested.

## Personal-v3 raw review

The nine strict mismatches classify under `PERSONAL_CLEANUP_ACCEPTANCE.md` plus the user's explicit
control-aware calibration as follows:

- acceptable surface/conservative differences: retained `Well` on cases 005 and 010, a harmless
  comma on 008, conservative false-start retention on 013, same-unit `€84` rendering on 016, and
  collapsed duplicated `really` on 018;
- unacceptable correction failure: case 011 retained `Send this to the family group` before the
  corrected Maya-only instruction; and
- control-conflict cases 014 and 017: the transcript asks for bullet/numbered lists while the fixed
  model-card control explicitly selects `Structure: prose`. Their prose outputs are acceptable for
  this configured profile and are not counted as Pixel deployment failures.

Guardrails were deliberately not applied in this S1 benchmark. The 19/20 result is raw-model
acceptability under that calibration; fallback does not turn the remaining correction failure into
a passing raw-model result.

## Preferred joined pipeline verification

The ordinary app now pins `s1-mini-q4_k_m.gguf` and its SHA-256, uses app-private model storage on
Android 17, and runs the same system prompt, control line, embedded template, thinking flag,
temperature, and per-input cap as the benchmark. No deterministic filler preprocessor is inserted
before S1. Sotto remains available only as a historical/debug engine.

The final file-fed Pixel run `20260820T182349Z-joined-file` processed all 20 personal-v3 audio
cases through the shipping Parakeet → S1 engine. Median STT/cleanup/pipeline totals were 725.0 ms,
1,927.5 ms, and 2,664.5 ms; cleanup p90 was 4,605 ms, peak PSS was 1,589,901 KiB, and thermal status
reached 1. Raw and guarded strict/normalized target counts agree at 8/20 and 9/20. Exactly one
guardrail fallback remains: case 011's genuinely retained superseded recipient. Four initial false
fallbacks exposed sentence-boundary correction parsing, list-colon tokenization, and capitalized
ordinal handling defects; focused regressions were added and the rerun reduced fallbacks from five
to one without weakening name, value, negation, uncertainty, or must-not-answer checks.

## Pixel measurements

Device: Google Pixel 7 `panther`, serial `33040DLH20004E`, Android 17, ARM64. Each evidence run
loaded the model once, ran one warmup, then processed the cases sequentially. No STT or microphone
was involved.

| Run | Trace | Calls | Start/max thermal | Load | Median TTFT | Median total | p90 total | Max total | Peak PSS |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| `20260820T173136Z` | Perfetto | 60 | 0 / 0 | 1,809 ms | 975.5 ms | 1,576 ms | 3,840 ms | 4,759 ms | 1,293,620 KiB |
| `20260820T174033Z` | none | 60 | 0 / 1 | 1,556 ms | 1,100.5 ms | 1,665 ms | 4,294 ms | 7,052 ms | 1,354,678 KiB |

The traced run's short-case median is 1,503 ms and long-form median is 4,025.5 ms. Its median
reported generation rate is 11.21 tokens/s. The untraced run's short/long medians are 1,645 and
4,303.5 ms; its median generation rate is 10.52 tokens/s. A prior untraced pass immediately after
the power run also reached thermal status 1 and is excluded from selection rather than silently
restarted under different settings.

Perfetto inference-slice energy for 60 calls:

| Rail grouping | Total | Per call |
|---|---:|---:|
| Compute | 389.567 J | 6.493 J |
| CPU | 282.006 J | 4.700 J |
| Memory/fabric | 106.899 J | 1.782 J |
| GPU | 0.662 J | 0.011 J |

GPU energy is 0.17% of inference compute energy; this is a CPU inference path, not Pixel GPU/NPU
acceleration.

## Reproducibility

The benchmark implementation is `S1MiniPixelBenchmarkEngine.kt`,
`prepare-s1-mini-pixel-cases.py`, and `run-s1-mini-pixel-benchmark.sh`. It stages transcript-only
cases in debug app-private storage, which is required by Android 17's external-app-data behavior.

Canonical ignored artifact hashes:

- traced raw JSONL: `23d003da02ba58b8d1c487c2d5b0a5f6a4ccb24787bbf5ec936f8f47411143b8`;
- traced summary: `32792deb63fc9063d18dea7eb3692cba234f4573ac2e5c6c34e8afb65d751bcb`;
- power trace: `ac76736c7a3179019e45994ae42dea83262c86cfbe38609214cae7757c49db32`;
- power summary: `29bbedee36defb1f961c81c9257fc1836c48ec8cebdbe5d6668fa62e9f94e1a4`;
- sustained untraced raw JSONL: `9433cf8415722377f5f190870890ea46cf53567d0d87c107eb82414f4cdb5eb6`;
- sustained untraced summary: `a7b67b7d000c2147f6466cf419db06c5dfc747759cad372534543f85101f88b5`;
- Mac Q4/F16 parity JSON: `ea2f4b4a4b8c351dabfb6835e504148ac77ad6f1f0a32138e4d0356e1a4ac0aa`;
- prepared transcript-only cases: `467ae06c7a321578e6f1c746e4d744f76a15ae4c76976b218a1bd30b7f457ad4`;
  and
- seed Pixel raw/summary: `5dbf8a3be74ccc1d2d8f8893c14e190196d9bc5c2afb35026ec0e75a09d9d799` /
  `3ba9ae02813a906c235c3c1378a5ce583bb37ef5e5206a704ea644d36ff4ec90`;
- held-out Pixel raw/summary: `fb657e77a20064248a034c57902b7908bfd283accb446d7399e216cdeccd0bdf` /
  `54d0803af5d56659b9323abf5b96017e5b3108e6325dfef8a87a98c5e20a1959`;
- seed/held-out Mac parity JSON: `6bf83c315a20ba080bf4fb6da9450ead39e077c141363769e47d99708c408a94` /
  `e99a0639e1e8d4dd4ce43dff3ffc607c1ba7d04945e1dc76999db2b8d8b8440f`;
- final joined raw/summary: `88b0b2ea21d43607845d67969dcb967307224a359c660448f5fd7048132ecdec` /
  `e367d239f95f199e27876bd410b146bf73b9487529e08d3e187410b1bb1aa1c4`;
  and
- 88,046,129-byte debug APK: `2f9ca73eaf1b30e454ee381f510c75dc75cbab8692177375659a56a0dd640357`.

Benchmark-source SHA-256 values are
`dde698d2e988954da555dac575c4e51a08531452f86e2aa2c300b66046f2bdde` for the debug S1 engine,
`5a2e05d31bf87d05b62e1524c5a596fe1334e63d18feaa4ea8de5af8537b947e` for the benchmark
Activity, `a6f0cb30fc5718a8acf6be29a58804c0feb47a9b9559dbb842c25838d3a44b61` for case preparation,
`4fd7c7fceaf749924f61b52a92bc9239a40420202cc4609022a3018f4c56b61f` for the Pixel runner, and
`ca669f02099b8e873c8c279ba5d7988179bbf59115eb6be5283fe073d7c6de10` for the focused case-cap
tests, and `dc46399bc7111b5291a4b5120cd37af85f71b45258c1ed15be4b722f661303a3`
for the production S1 engine.

Android lint, unit tests, and debug assembly pass. The relevant Python S1 and Pixel benchmark tests
pass 16/16. Full script discovery passes 174/175; the sole failure is the already recorded macOS
`/var/folders` versus `/private/var/folders` temporary-path alias assertion, unrelated to this
benchmark.

## Decision and next evidence

Use S1-mini as the preferred on-device cleanup model. It gives the best selected local personal-v3
quality, and the full parity pass rules out silent loss of the publisher prompt/template/options on
Pixel. Preserve the measured latency, memory, energy, sustained thermal behavior, and remaining
recipient-correction failure as explicit product risks rather than hiding them behind the model
selection.

Do not tune on personal-v3. A later S1 decision requires the full raw semantic-safety review on
the retired diagnostics and a new evaluation version for any product-policy iteration. A different
Android acceleration/runtime study must reproduce this exact publisher contract and re-establish
raw-output parity before its performance can be compared.
