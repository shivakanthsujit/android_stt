# S1-mini LEAP Pixel tuning matrix

Date: 2026-08-22 JST (run IDs are UTC on 2026-08-21)

## Result

Select explicit two CPU threads, a 2,560-token context, cache off, and mmap on for the S1-mini
LEAP path. The exact official 484,219,808-byte Q4_K_M GGUF remained fixed at SHA-256
`3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634`.

In the matched traced comparison, the selected configuration reduced median TTFT from 1,122 to
723 ms, median total latency from 1,694.5 to 1,391.5 ms, p90 total from 4,178 to 3,371 ms, peak PSS
from 1,327,967 to 1,188,541 KiB, and inference compute energy from 5.814469 to 5.227675 J/call.
Those are reductions of 35.56%, 17.88%, 19.32%, 10.50%, and 10.09%, respectively. Both traced
runs started at thermal status 0 and reached status 1.

The 32 and 64 MiB memory-cache arms each reported zero cached prompt tokens across all 60 measured
calls. They therefore provide no demonstrated prefix reuse and are rejected. Disk caching remained
disabled with zero requested disk entries; each enabled arm allowed four memory entries, each
request used a fresh conversation, and mmap remained enabled throughout.

## Protocol and parity

The Pixel 7 (`panther`, Android 17) loaded the model once per run, executed one warmup, and used the
20-case evaluation-only personal-v3 transcript workload. Full arms used three measured repeats,
giving 60 measured calls; the initial smoke used one repeat and 20 measured calls. Measured work
was repeat-major, with the warmed case rotated to the end of each pass so identical full prompts
were not adjacent. Every accepted run began at thermal status 0.

All twelve valid runs had:

- exact first-repeat raw-output parity on 20/20 cases against the full implicit/4,096/cache-off
  control;
- zero unstable cases across measured repeats, zero blank outputs, zero cap hits, and zero
  fallbacks;
- `STOP` on every generation, 91–158 prompt tokens, 78 fixed prompt/template tokens, and the exact
  input-relative requested output caps;
- 11/20 raw strict exact, 12/20 normalized exact, and 54/61 preserved literal anchors; and
- mmap enabled and complete, single-valued runtime metadata.

The implicit LEAP control resolved to one CPU thread on this device. Explicit arms resolved to
their requested two, three, or four threads.

## Untraced matrix

Times and memory values below come directly from the retained summaries. `CPU` is median process
CPU time; `decode` is median reported generation throughput. All full arms contain 60 measured
calls except the smoke, which contains 20.

| Run ID | Role/configuration | Calls | Load ms | TTFT med / p90 ms | Total med / p90 / max ms | CPU med ms | Decode tok/s | Peak PSS KiB | Peak native bytes | Max thermal |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `20260821T160331Z-s1-mini-pixel-leap-timplicit-ctx4096-cache0mb` | smoke: implicit (resolved 1), 4,096, cache off | 20 | 9,622 | 959.5 / 1,481 | 1,555.5 / 3,502 / 4,282 | 1,576 | 11.470492 | 1,264,815 | 1,295,412,000 | 0 |
| `20260821T160616Z-s1-mini-pixel-leap-timplicit-ctx4096-cache0mb` | full control: implicit (resolved 1), 4,096, cache off | 60 | 2,310 | 1,124.5 / 1,727 | 1,706.5 / 3,954 / 4,878 | 1,737.5 | 10.869684 | 1,271,567 | 1,295,391,152 | 0 |
| `20260821T160911Z-s1-mini-pixel-leap-t2-ctx4096-cache0mb` | threads: explicit 2, 4,096, cache off | 60 | 2,227 | 778.5 / 1,214 | 1,425 / 3,587 / 4,290 | 2,754.5 | 13.411549 | 1,328,971 | 1,295,987,312 | 1 |
| `20260821T161347Z-s1-mini-pixel-leap-t3-ctx4096-cache0mb` | threads: explicit 3, 4,096, cache off | 60 | 1,959 | 720.5 / 1,002 | 1,390 / 3,475 / 5,024 | 3,955.5 | 13.819635 | 1,328,421 | 1,295,983,488 | 1 |
| `20260821T162413Z-s1-mini-pixel-leap-t4-ctx4096-cache0mb` | threads: explicit 4, 4,096, cache off | 60 | 1,602 | 525.5 / 773 | 1,369 / 3,693 / 5,116 | 4,933 | 13.856319 | 1,295,378 | 1,296,198,672 | 1 |
| `20260821T162853Z-s1-mini-pixel-leap-t2-ctx3072-cache0mb` | context: explicit 2, 3,072, cache off | 60 | 1,536 | 683.5 / 990 | 1,372 / 3,510 / 4,497 | 2,652 | 14.155416 | 1,251,104 | 1,171,655,552 | 1 |
| `20260821T164120Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb` | context: explicit 2, 2,560, cache off | 60 | 2,535 | 658 / 1,001 | 1,263 / 3,338 / 4,324 | 2,451.5 | 14.651648 | 1,197,759 | 1,112,908,880 | 1 |
| `20260821T164520Z-s1-mini-pixel-leap-t2-ctx2560-cache32mb` | cache: explicit 2, 2,560, 32 MiB | 60 | 1,496 | 679 / 1,003 | 1,357 / 3,414 / 4,765 | 2,603.5 | 13.694038 | 1,216,004 | 1,146,385,232 | 1 |
| `20260821T165004Z-s1-mini-pixel-leap-t2-ctx2560-cache64mb` | cache: explicit 2, 2,560, 64 MiB | 60 | 1,584 | 728.5 / 1,121 | 1,433 / 3,608 / 4,593 | 2,754 | 13.149641 | 1,213,581 | 1,158,415,296 | 1 |
| `20260821T165539Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb` | untraced confirmation: explicit 2, 2,560, cache off | 60 | 1,484 | 732.5 / 1,140 | 1,423.5 / 3,564 / 4,454 | 2,755 | 13.347420 | 1,188,251 | 1,113,476,112 | 1 |

The three- and four-thread arms improved median total latency over two threads by only 2.46% and
3.93%, while increasing median process CPU time by 43.60% and 79.09%. The four-thread p90 was also
2.96% worse than the two-thread p90. Two threads were selected as the better sustained-efficiency
point. At two threads, reducing context from 4,096 to 2,560 improved the primary untraced median
from 1,425 to 1,263 ms and reduced peak PSS from 1,328,971 to 1,197,759 KiB without changing any
output or violating the runtime context-cap assertion.

For the primary 2,560/cache-off arm, short-form and long-form median totals were 1,218.5 and 3,339
ms. The independent untraced confirmation measured 1,296.5 and 3,582.5 ms, showing material
run-to-run variance but preserving the same output and memory conclusion.

## Foreground-loss incident

The first 2,560/cache-off attempt,
`20260821T163347Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb`, lost the benchmark foreground and was
stopped. It is protocol-invalid and excluded from every comparison. The flushed partial contains
one warmup and 17 first-repeat measured rows; its final row has an anomalous 7,664 ms TTFT and
21,697 ms total while thermal status remained 0. The failure was retained rather than treated as a
completed run or silently merged with the clean rerun.

Retained partial:
`.cache/integration/results/invalid-partial-20260821T163347Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb.jsonl`
(18 lines), SHA-256
`a195cfa6a4477422f78a0c920b60c0bbd421835600680b5111efa0aba770b089`.

## Traced control and winner

| Metric | Implicit / 4,096 / cache off | Explicit 2 / 2,560 / cache off | Change |
|---|---:|---:|---:|
| Run ID | `20260821T170539Z-s1-mini-pixel-leap-timplicit-ctx4096-cache0mb` | `20260821T171127Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb` | — |
| Model load | 1,577 ms | 1,498 ms | -5.01% |
| Median TTFT | 1,122 ms | 723 ms | -35.56% |
| Median total | 1,694.5 ms | 1,391.5 ms | -17.88% |
| p90 / max total | 4,178 / 6,656 ms | 3,371 / 4,777 ms | p90 -19.32% |
| Short / long median total | 1,646 / 4,293 ms | 1,268.5 / 3,419.5 ms | -22.93% / -20.35% |
| Median process CPU | 1,728 ms | 2,686.5 ms | +55.47% |
| Median decode | 10.198998 tok/s | 13.592823 tok/s | +33.28% |
| Peak PSS | 1,327,967 KiB | 1,188,541 KiB | -10.50% |
| Peak native heap | 1,295,974,128 bytes | 1,113,447,856 bytes | -14.08% |
| Inference duration, 60 slices | 135.719623 s | 107.264011 s | -20.97% |
| Inference compute energy | 348.868137 J / 5.814469 J/call | 313.660480 J / 5.227675 J/call | -10.09% |
| Inference CPU energy | 238.820163 J / 3.980336 J/call | 218.697300 J / 3.644955 J/call | -8.43% |
| Inference memory/fabric energy | 109.507154 J / 1.825119 J/call | 94.420395 J / 1.573673 J/call | -13.78% |
| Inference GPU energy | 0.540820 J / 0.009014 J/call | 0.542785 J / 0.009046 J/call | +0.36% |
| Inference average compute power | 2.570506 W | 2.924191 W | +13.76% |
| Start / max thermal | 0 / 1 | 0 / 1 | unchanged |

The selected arm uses more instantaneous compute power and process CPU time but finishes sooner,
so total CPU and compute energy fall. GPU energy is unchanged noise-level activity and does not
indicate GPU inference.

## Reproducibility hashes

The prepared transcript-only cases used by every run have SHA-256
`467ae06c7a321578e6f1c746e4d744f76a15ae4c76976b218a1bd30b7f457ad4`.

| Run ID | Raw result SHA-256 | Summary SHA-256 |
|---|---|---|
| `20260821T160331Z-s1-mini-pixel-leap-timplicit-ctx4096-cache0mb` | `ece23fb493c8cc938afbcd7a017189cab060355d3a13b607554961176e8f0c94` | `5ad3b642c3879402969465c5ffd5fba1185a35f794e017f8c5c627ba9714df20` |
| `20260821T160616Z-s1-mini-pixel-leap-timplicit-ctx4096-cache0mb` | `b2b31420194d1a22adebe1563f8b3d9ac8d72eba0b18a4623801ae9674266636` | `acf00099bbee19e0b11cb2a2d42d6ced35692d6bb8e72d563b731c830c7901eb` |
| `20260821T160911Z-s1-mini-pixel-leap-t2-ctx4096-cache0mb` | `08bf1dead0c74dfca7a027cdd23b3d76402aa021acbb4b7d91a637c65924ce2c` | `c2d07fc23e55a246ac52ef2aeaef6742c43d09333d46050805eea28af3b490f2` |
| `20260821T161347Z-s1-mini-pixel-leap-t3-ctx4096-cache0mb` | `20018078bd5b0ac3a5c5c1e8f033441d4a9989ced3363970ce3028c29df87f16` | `130eeb8073e011a944b971f71ab0d72728e2c503ec5c06c536332956a8b58e8b` |
| `20260821T162413Z-s1-mini-pixel-leap-t4-ctx4096-cache0mb` | `4eedb8b4c231f9fc885a1af7057e5d185107782dc4ec41a8ba0905da9bfc995d` | `127856dbd555f4bd95ea853437bac457a0ec7204c8a2abdb77d1095f17bc9abb` |
| `20260821T162853Z-s1-mini-pixel-leap-t2-ctx3072-cache0mb` | `db05bf32246eb0b2249ca6b0d329cd78999f5cfb2958ea69689106cc98dde6fc` | `09c9bec537afff5c3d469ee82de37c76e64a12ef7ac4fb09fac698afb32741f6` |
| `20260821T164120Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb` | `1a53b4f4226976cd4c16d4d93da1cb7d5ceb6c78080b9037602e636bfa784f7a` | `c69af252f4d94219923b8353292ba8a10c1f06e11732ddf958ade44f07322456` |
| `20260821T164520Z-s1-mini-pixel-leap-t2-ctx2560-cache32mb` | `40b3be09363a7da01a9d269e77e7c9c144463dd158170e1d713071dd60ac4b5d` | `c788177ab04de9c5cb630b1b5e7a69c2caa027449942ceaf828c9c443b786215` |
| `20260821T165004Z-s1-mini-pixel-leap-t2-ctx2560-cache64mb` | `3f244679e8a533b058e90509f97f40908303a5c94507ad73714606a0d6ca7c42` | `b9f7dae6754e7dcb357889cd4b8299fbd315d1bb3dae605792d51c6266a30c72` |
| `20260821T165539Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb` | `8b7339a0fa54b56ba64c6865d7bfa82cd4df6eb48dcec43faa00db13d0309f20` | `5015521c5a618f61d41d8e295ac9af2201f08b285c5814c5b4a7c349dc2e405a` |
| `20260821T170539Z-s1-mini-pixel-leap-timplicit-ctx4096-cache0mb` | `0cd310b7a71db1bbbe4b8c7d4728b72cc80f1a5b3beda10da05f6e2e7c432f41` | `d4b42fb4cdfe29a9c139050df1a972e977a3ae8faedd44fffd4c45134a07cd03` |
| `20260821T171127Z-s1-mini-pixel-leap-t2-ctx2560-cache0mb` | `8fed17e6551c43328e44e0452e2f23be9738ce56cc7624eeb503a92a918f04f0` | `577eab0b4bc18e13e666d379e9742732a4f16e82471f6ddcd78868c1860a6428` |

Traced artifacts:

- control trace / power summary:
  `73feaa88d7fc58518f7a6ec1ab9888e28128f216f881c6afc52a5a56d1e5e0f3` /
  `47b83aecfa9bd8c82beb14d5913ce9a84bfb303b8029b7c011f49e6af8628d6f`;
- selected trace / power summary:
  `8505214f04272940e4c4131682dc6bec0b69f78b3bc85248afae0461ddf3679c` /
  `a115bda2719f57e2ae49db72b7edef1c6dc8c5042bc11a1b4e5819ee4e1d48e6`.

## Limitations

- This is one Pixel 7 and one 20-case synthetic/personal-conversation workload. It establishes
  same-model runtime behavior, not broad cleanup quality or another device's performance.
- Every full arm started at thermal status 0, but all full explicit-thread arms and both traced
  runs reached status 1. The tuning reduces energy and duration; it does not eliminate sustained
  thermal drift.
- Arms ran sequentially rather than in randomized order. The clean confirmation and matched traced
  comparison reduce, but do not remove, temporal, scheduler, background-service, and load-time
  variance.
- PSS/native heap are post-call sampled peaks, not allocator-residency decomposition. Model-load
  times vary substantially and the 9,622 ms first smoke load is a cold-path outlier.
- The memory-cache experiment used four entries and fresh conversations. Its zero
  `cached_prompt_tokens` result means this LEAP path did not reuse the fixed prefix under the tested
  schedule; it does not prove that every possible SDK cache topology is ineffective.
- The 2,560 context passed every benchmark request and the static 2,410-token worst-case contract,
  leaving 150 tokens of margin. Future prompt/template/output-cap changes must re-run that capacity
  assertion before retaining this context.
- The exact GGUF, prompt/template, greedy decoding, output cap, fresh-conversation isolation, and
  personal-use insertion policy did not change. Lower-bit quantizations were not tested.
- This closes only the supported LEAP-tuning stage. Direct llama.cpp and exact-checkpoint LiteRT-LM
  comparisons remain separate work.
