# Personal-v3 relaxed cross-model comparison

Date: 2026-08-18
Policy: `docs/evaluation/PERSONAL_CLEANUP_ACCEPTANCE.md` version 1
Decision: GPT-5.6 Luna leads the hosted/personal-v3 comparison; Sotto B is the best local family

## Scope

This comparison re-reviews the raw outputs already generated for the fixed, evaluation-only
20-case personal-v3 corpus. It covers:

- the public Hugging Face Sotto SFT checkpoint
  `juanquivilla/sotto-cleanup-lfm25-350m` at revision
  `6df6f019170b8b55333c047b901886a51750a965`;
- all four public-refinement Experiment A epochs;
- all three clean-base Experiment B epochs; and
- the new GPT-5.4-mini, GPT-5.4, and GPT-5.6 Luna API results.

No model was rerun for this comparison. The local raw artifacts remain under
`/data/rise/android_stt/evaluations/personal-v3-20260818/`; the GPT raw artifacts remain under
ignored `build/evaluation-results/gpt-personal-v3/`. No HF/source-dev or blind-v2 evaluation was
run. The case-file SHA-256 is
`667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`.

Strict exactness remains visible, but relaxed user-calibrated acceptability is now the default
product metric. In particular, collapsing `really really` to one `really` is acceptable.
The policy-file SHA-256 is
`8e32790afbe8159d0f595a98b6b268804d59a4837b854bddc83042e60b47b97f`.

## Ranking

`Corrections` covers cases 002, 011, and 020. `Formatting` covers cases 014, 017, and 019. Local
latencies are single sequential BF16 A6000 observations; hosted latency includes network/service
time and is not a hardware-normalized comparison.

| Model | Runtime / origin | Relaxed acceptable | Strict exact | Corrections | Formatting | Median total |
|---|---|---:|---:|---:|---:|---:|
| **GPT-5.6 Luna** | OpenAI API | **20/20** | 12/20 | **3/3** | **3/3** | **649 ms** |
| GPT-5.4 | OpenAI API | **20/20** | 12/20 | **3/3** | **3/3** | 860 ms |
| GPT-5.4-mini | OpenAI API | 18/20 | 10/20 | 1/3 | **3/3** | 827 ms |
| Sotto B epoch 2 | local clean-base SFT | **15/20** | **8/20** | 1/3 | 0/3 | 287 ms |
| Sotto B epoch 3 | local clean-base SFT | **15/20** | **8/20** | 1/3 | 0/3 | **237 ms** |
| Sotto B epoch 1 | local clean-base SFT | **15/20** | 7/20 | 1/3 | 0/3 | 293 ms |
| Public Sotto HF SFT | Hugging Face public SFT | 14/20 | **11/20** | 0/3 | 0/3 | **228 ms** |
| Sotto A epoch 1 | local public-refinement SFT | 14/20 | 8/20 | 1/3 | 1/3 | 283 ms |
| Sotto A epoch 2 | local public-refinement SFT | 14/20 | 8/20 | 1/3 | 1/3 | 279 ms |
| Sotto A epoch 3 | local public-refinement SFT | 14/20 | 8/20 | 1/3 | 1/3 | 300 ms |
| Sotto A epoch 4 | local public-refinement SFT | 14/20 | 8/20 | 1/3 | 1/3 | 288 ms |

The relaxed metric reverses the earlier strict-only local ranking. All B epochs reach 15/20 and
edge the public HF SFT's 14/20 because B fixes case 002's time correction. B epoch 2 remains the
cleanest local tie-breaker on strict exactness and anchors; B epoch 3 has the lowest single-run
latency. This does not justify replacing the public Android placeholder: every B checkpoint still
retains the recipient correction, fails all three explicit formatting directives,
and retains the long-form five-to-ten-minute correction. Their broader retired/source safety
failures also remain.

The public HF SFT is also the only model in this table with a current Android Q4_K_M integration
artifact. In the separate Parakeet→Sotto Pixel file-fed run it reached 10/20 normalized intended
cleanup matches at 645 ms median cleanup time. That is end-to-end pipeline evidence with STT input,
not a direct-text quality or hardware-normalized latency comparison. No A/B checkpoint was
quantized or integrated. Luna's 649 ms hosted median is therefore promising but trades offline
privacy and availability for its 20/20 relaxed direct-text result.

## Pixel integration handoff

- Hosted candidate: API model slug `gpt-5.6-luna`; there is no local Luna checkpoint.
- Best local checkpoint under the default relaxed personal-v3 ranking: B epoch 2 at
  `dante:/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty/checkpoint-542`
  (`model.safetensors` SHA-256
  `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6`).

The checkpoint stays on `dante` and is intentionally not committed. It can be copied directly
from that host for the experimental Pixel build. This handoff identifies the best local v3
comparison candidate; it does not override the safety findings above or qualify it for release.

## Relaxed failure matrix

Only outputs rejected by the default relaxed policy appear here. A check means the model family
handled the case acceptably.

| Case | Required behavior | Public HF SFT | A1–A4 | B1–B3 | GPT-5.4-mini | GPT-5.4 | Luna |
|---|---|---:|---:|---:|---:|---:|---:|
| 002 | remove superseded `six` time | fail | ✓ | ✓ | fail | ✓ | ✓ |
| 011 | remove superseded family-group recipient | fail | fail | fail | fail | ✓ | ✓ |
| 013 | preserve past-tense `felt` | ✓ | fail | ✓ | ✓ | ✓ | ✓ |
| 014 | realize and consume bullet-list directive | fail | fail | fail | ✓ | ✓ | ✓ |
| 016 | preserve euro currency unit | ✓ | fail | ✓ | ✓ | ✓ | ✓ |
| 017 | realize and consume numbered-list directive | fail | ✓ | fail | ✓ | ✓ | ✓ |
| 019 | realize and consume paragraph-break directive | fail | fail | fail | ✓ | ✓ | ✓ |
| 020 | remove superseded five-minute alternative | fail | fail | fail | ✓ | ✓ | ✓ |

Case 018 does not appear: punctuation, preserving both `really` tokens, or collapsing them to one
are all acceptable under the default policy. Equivalent word/digit/time/currency surfaces,
typographic apostrophes, harmless lead-ins, and conservative same-meaning framing are likewise not
failures.

## Result identities

The local hashes are unchanged from the original checkpoint matrix. GPT hashes are from the new
sequential API runs.

| Model | Result SHA-256 |
|---|---|
| Public HF SFT | `d2204aa4561a562637113e15ad671e2b44b306f5179c0f0e91cb0064d71a5a13` |
| A epoch 1 | `f503fd02e20b9cd7b458c5eeaa0fd5a46a6727c9d1a8ea64cf62916427356869` |
| A epoch 2 | `cf76f095dfb63898cd01c58675909afb690d5a0b2267a7706daae89215722907` |
| A epoch 3 | `45e02c65fbbcd868d0ac1b7aef7d5279df0c75ad2507b5ef72321b927efc1249` |
| A epoch 4 | `c5a37e662f2acfd793d5e204d779a2bb32b743c3c0884bf0ca8d3a6f719e4ed0` |
| B epoch 1 | `d0572dfb87dffedb751d18f57e51ab356f31d7054bc646c227a82b8d9554b3b9` |
| B epoch 2 | `758a21a5656fbddec3e193b0cd68d680f9a606fc31a84a6a42ad29f1d35045ed` |
| B epoch 3 | `20a9577350f0d34b98197f96b4989f644740fb27a4edb93596cc0ebffe201828` |
| GPT-5.4-mini | `5567e5a4a18608ccb113df1d2850dd6b2e070ba3a389b0e9f1406d82a9eeda6b` |
| GPT-5.4 | `b72e68f93b2a5784c141acdbba9357caa81126f56b3b3f3ea89e38f902db15f9` |
| GPT-5.6 Luna | `b40f13efd5a407da51da35bff53cb38250c8f2f236a9416a6c3083ec613e76e4` |

Raw output, rather than guardrail fallback, remains the acceptance source.
