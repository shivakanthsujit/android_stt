# Sotto LFM personal-v3 checkpoint matrix

Date: 2026-08-18
Decision: public start is the strongest checkpoint on personal v3; no checkpoint qualifies for deployment

## Scope and provenance

This run evaluates the fixed, evaluation-only
`docs/evaluation/cleanup_personal_conversation_v3.jsonl` corpus (20 cases, SHA-256
`667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`) with raw BF16 model
output selected for scoring. The runner SHA-256 is
`9d5839fed0680f54715ab038b0505907d5f893dabf78a54811b3f1d1ab31fe9f`.

The remote evaluation changes were integrated at local merge `ab85a54`. The two newest remote
commits are `b0ed579` (personal voice regression and fast joined runner) and `cd77e76` (personal-v3
long-form checkpoint evaluation). V3 replaces the active technical stress workload with ordinary
personal messages, journals, lists, names/numbers, uncertainty, repetition, formatting directives,
and natural corrections. It removes phone-number dictation and adds four 3–5 sentence cases. Its
text, targets, outputs, and errors remain forbidden from training or repair generation.

Raw JSONL and per-run provenance remain outside Git under
`/data/rise/android_stt/evaluations/personal-v3-20260818/` (292 KiB). All eight files contain 20
records; no run hit the 900-token floor cap.

## Results

`Anchors` is the scorer's case-sensitive literal metric. Equivalent word-form numbers can therefore
be semantically safe while failing the strict target and anchor checks.

| Checkpoint | Weight SHA-256 | Result SHA-256 | Exact | Anchors | All-anchor cases | Guard flags | Median / p95 / max total |
|---|---|---|---:|---:|---:|---:|---:|
| Public start | `6e96eeffdcdd60f881e13eb2019b339b39d1a74951446f062e7e641a82f6422e` | `d2204aa4561a562637113e15ad671e2b44b306f5179c0f0e91cb0064d71a5a13` | **11/20** | **53/61** | **15/20** | 2 | **228 / 913 / 1,015 ms** |
| A epoch 1 | `af088344ef756bd535273f060326c2d5adea00cfde4c89f520f549199ff99c42` | `f503fd02e20b9cd7b458c5eeaa0fd5a46a6727c9d1a8ea64cf62916427356869` | 8/20 | 50/61 | 12/20 | 5 | 283 / 935 / 1,013 ms |
| A epoch 2 | `63b53a7e516e9e7bcf72019a6b9427fe4ebc8ed9fe87daba6cc72aa67c10cfed` | `cf76f095dfb63898cd01c58675909afb690d5a0b2267a7706daae89215722907` | 8/20 | 50/61 | 12/20 | 5 | 279 / 1,019 / 1,102 ms |
| A epoch 3 | `918ef3ebd5557fa2f61488106744fc659d1801b4b9df3d09b5b6474570e9db57` | `45e02c65fbbcd868d0ac1b7aef7d5279df0c75ad2507b5ef72321b927efc1249` | 8/20 | 50/61 | 12/20 | 5 | 300 / 999 / 1,161 ms |
| A epoch 4 | `3aee516270f5bcda44bb648dc3a939394fc1b67af20ecde76541f38b160dc822` | `c5a37e662f2acfd793d5e204d779a2bb32b743c3c0884bf0ca8d3a6f719e4ed0` | 8/20 | 50/61 | 12/20 | 5 | 288 / 1,093 / 1,124 ms |
| B epoch 1 | `e9d552f472374b51f8d59fe67623e0ae737ca9393a4b28d87341e9f5fab5de65` | `d0572dfb87dffedb751d18f57e51ab356f31d7054bc646c227a82b8d9554b3b9` | 7/20 | 46/61 | 10/20 | 2 | 293 / 1,117 / 1,265 ms |
| B epoch 2 | `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6` | `758a21a5656fbddec3e193b0cd68d680f9a606fc31a84a6a42ad29f1d35045ed` | **8/20** | **50/61** | **12/20** | 2 | 287 / 999 / 1,116 ms |
| B epoch 3 | `7e817690331e4d8f5e067ff8df1e499de1013567f70c8dbb976ce52820db6ffb` | `20a9577350f0d34b98197f96b4989f644740fb27a4edb93596cc0ebffe201828` | 8/20 | 47/61 | 11/20 | 2 | 237 / 1,119 / 1,234 ms |

All checkpoints score 1/4 exact on the long-form subset. Public-start total latency for cases
015/018/019/020 is 725/447/1,015/790 ms. A epoch 4 is 1,093/746/1,046/1,124 ms; selected campaign
B epoch 1 is 1,117/456/1,027/1,265 ms; B epoch 2 is 1,116/722/999/803 ms; and source leader B epoch
3 is 1,119/726/1,025/1,234 ms. These are single sequential A6000 observations, not sustained
performance measurements.

## Raw-output review

Every non-exact output and every safety-sensitive case was reviewed across all checkpoints.

- Public start has the best strict and preservation results. It makes no unsupported factual
  substitution in this suite, but it retains superseded content in all three explicit corrections.
  The guard catches cases 011 and 020 but misses case 002 after the model changes the number
  surfaces. It also leaves the list/paragraph directives unconsumed.
- All four A checkpoints make the same substantive currency substitution in case 016 and the
  guard does not reject it. They also change tense in case 013 (rejected) and correctly consume the
  numbered-list directive in case 017, which the guard incorrectly rejects. A remains a raw-safety
  no-go despite matching B's best exact count.
- B epoch 2 is the best fine-tuned checkpoint on this suite. It is strictly better than B epoch 1
  on exact match, anchors, and all-anchor cases, and it avoids A's unsupported currency change.
  B epochs 1–3 still retain the superseded recipient and long-form time correction and do not
  reliably consume formatting directives. B epoch 3 ties epoch 2 on exact match but loses three
  literal anchors.

The passing unit tests establish runner behavior and Python/Kotlin guardrail parity; they do not
establish semantic completeness. This run exposes two guardrail false-negative classes (retained
correction after numeric surface changes and currency-unit substitution) plus a false rejection of
valid numbered-list directive consumption. Those need separate policy/code changes and regression
tests before the guard can be relied upon for these cases.

## Conclusion

Personal v3 reverses the apparent ranking from the publisher-source and retired technical suites:
the public checkpoint beats every fine-tuned epoch by at least three exact cases and three literal
anchors. B epoch 2 is the strongest fine-tuned model on the revised product workload, while B epoch
1 remains only the earlier campaign selection under the pre-v3 safety-weighted criteria. Do not
replace the public Android placeholder with any fine-tuned checkpoint, and do not use v3 failures
as training examples. A future repair experiment needs independently authored training data and a
fresh evaluation version for any policy change.
