# GPT-5.4 API cleanup pilot

Date: 2026-08-18
Status: complete pilot; user confirmed complimentary attribution and full screen completed

This is evidence for the separate cloud/API campaign in
`docs/evaluation/GPT54_CLOUD_API_EVALUATION.md`. It is not part of the local-LLM training campaign.
The four cases came only from the older committed seed suite; the initially proposed heldout pilot
was blocked before any request was sent. The user subsequently authorized sending both committed
corpora for the full API evaluation.

## Configuration

- Cases: `cleanup-004`, `cleanup-013`, `cleanup-018`, `cleanup-022`
- Models: `gpt-5.4-mini-2026-03-17`, `gpt-5.4-2026-03-05`
- Chat Completions, standard/default service tier, streaming
- frozen `baseline_rules` prompt; temperature 0.1; seed 23; `reasoning_effort=none`
- Android-equivalent cap through `max_completion_tokens`; raw-output scoring
- successful-call window: 2026-08-18 09:12 UTC

## Pilot result

| Model | Raw exact | Anchors | Guardrail would fallback | Input/output tokens | Median TTFT | Median total | Range total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GPT-5.4-mini | 2/4 | 9/9 | 1/4 | 418 / 64 | 932 ms | 1,156 ms | 561–2,060 ms |
| GPT-5.4 | 3/4 | 8/9 | 0/4 | 418 / 57 | 1,209 ms | 1,336 ms | 775–1,677 ms |

GPT-5.4-mini retained the superseded recipient in the explicit-correction case. Its other mismatch
was capitalization/punctuation on dictated request text. GPT-5.4 handled those cases but changed
the protected literal `precise shrinking` to title case. Four cases are too few for a model choice
or stable percentile claim; the pilot only establishes request compatibility, approximate usage,
and an initial latency range.

The API response reports tokens but no dollar-cost field. At the captured standard rates in
`model_page.md`, with no cached-input discount, the successful pilot corresponds to $0.0006015 for
GPT-5.4-mini and $0.0019000 for GPT-5.4, or $0.0025015 total if billed.

For the full harness, `tiktoken` 0.14.0 uses the registered `o200k_base` encoding for both dated
models. Its API-calibrated chat-framing calculation exactly matches the pilot usage and counts
2,494 input tokens for the 24 seed cases plus 4,640 for the 45 heldout-v1 cases: 7,134 input tokens
per model. Using the pilot's average output length, the estimated standard cost is $0.01032 for mini
and $0.03258 for full, or $0.04290 total. The hard output caps sum to 1,583 tokens per model, making
$0.05405 a conservative no-cache ceiling if every response hits its cap. The user must still
confirm the complimentary data-sharing tier in the dashboard before the full run.

## Reproducibility

- seed corpus SHA-256: `1cf4335b7679c81ca55c9d1cd4b9d25ee69a37dcecfff72f3c03740cd53573b9`
- runner SHA-256: `d3763c6e0291f754c702e1a96fafffe92d8825ccc01df2de99eace4379c1122b`
- request-extra SHA-256: `4a6761354f33f8111e4f12cbb29adac502cacfcb36f0b865835e109afe5fa48b`
- GPT-5.4-mini raw JSONL SHA-256:
  `19d61f2908ba698e33d6264d09e645f97a411d1e2da34c552da0b404d511c2ad`
- GPT-5.4 raw JSONL SHA-256:
  `6293b3581a1107174e98a13db51d2d55e92e83111d1ff9946024694b2f7aec23`

Raw JSONL and the request-extra file remain under ignored
`build/evaluation-results/gpt54-pilot/`; no API key is present in them.

The completed campaign is recorded in
[2026-08-18-gpt54-api-screen.md](2026-08-18-gpt54-api-screen.md).
