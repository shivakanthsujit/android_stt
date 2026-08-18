# Hosted GPT cloud API evaluation

This is a separate optional cloud/API benchmark campaign. It measures whether OpenAI's hosted
GPT-5.4 models are useful for the owner's personal dictation workflow. It does not change, replace,
or supply data to the local cleanup-model training research plan.

## Isolation and data policy

- On 2026-08-18, the user explicitly authorized sending both committed cleanup corpora to the
  OpenAI API for evaluation: `cleanup_cases.jsonl` and `cleanup_cases_heldout_v1.jsonl`.
- The user subsequently authorized applying the same hosted evaluation to the checkpoint
  harness's public/synthetic source-dev split. Raw source rows and outputs remain outside Git.
- These corpora and their model outputs remain evaluation-only. Never use them as local-model
  training rows, demonstrations, retrieval context, preference pairs, prompt-tuning evidence, or
  checkpoint-selection data.
- Never send blind-v2 through this campaign. The existing optimization-side runner refuses blind
  paths and records raw output separately from guardrail evidence.
- The test project intentionally shares API inputs and outputs with OpenAI to qualify for the
  account's complimentary-token offer. Do not send personal, sensitive, confidential, or
  proprietary transcripts with this shared-data key.
- Keep API credentials out of Git and result files. A later personal-use deployment must use the
  owner's separate non-sharing project/key and must be evaluated as a distinct privacy setting.

## Fixed comparison

- Models: `gpt-5.4-mini-2026-03-17` and `gpt-5.4-2026-03-05`.
- Endpoint: OpenAI Chat Completions API, standard/default service tier.
- Prompt: frozen `baseline_rules` cleanup prompt.
- Decoding: `reasoning_effort=none`, temperature `0.1`, seed `23`, streaming enabled.
- Output bound: the Android-equivalent input-derived 16–96 token cap, sent as
  `max_completion_tokens`.
- Evidence: raw-output scoring, parallel Android guardrail decision, exact/preservation/safety
  metrics, token counts, TTFT, total response time, and attempt count.
- Full quality set after the billing check: all 24 seed cases and all 45 heldout-v1 cases, in source
  order, for each model. This is 69 requests per model and 138 total.

Run the sequential profile first because it represents one live dictation request and gives clean
per-request latency. After quality passes, measure a separately labeled concurrent profile for
throughput; do not mix concurrent latency with the sequential product-latency result. Re-run a
small warm subset when assessing cache/warm behavior, and report sample size rather than treating
four-request pilot maxima as percentile estimates.

## Staged quota check

The first stage is four older seed cases per model: `cleanup-004`, `cleanup-013`, `cleanup-018`,
and `cleanup-022`. Stop after those eight successful requests and have the user confirm that Usage
shows the data-sharing incentive service tier while Costs remains unchanged. Do not start the full
138-request comparison until that confirmation.

The pilot consumed 482 tokens for GPT-5.4-mini and 475 for GPT-5.4. `tiktoken` 0.14.0 resolves both
dated models to `o200k_base`; an API-calibrated chat-framing count exactly reproduces the pilot's
418 reported input tokens and counts 7,134 input tokens for all 69 requests per model. Projecting
the pilot's average output lengths gives about 8,238 total tokens for mini and 8,117 for full. The
configured output caps sum to 1,583 tokens per model.

The Chat Completions response reports token usage, not dollars. At the captured standard prices,
assuming no cached-input discount, the pilot corresponds to $0.0025015. The projected-output cost
for both complete 69-case runs is $0.04290; even if every response consumes its complete output
cap, the total is about $0.05405. Actual cost/free attribution must come from the Usage and Costs
dashboard and the complete runs' API-reported token usage.

Pilot evidence: [2026-08-18-gpt54-api-pilot.md](results/2026-08-18-gpt54-api-pilot.md).

## Completed extensions

After the user confirmed complimentary attribution, both 69-case runs completed sequentially. The
campaign then reused the public/synthetic 8,519-row source-dev split from the checkpoint harness:
all rows for mini and a deterministic 1,500-row source-stratified GPT-5.4 sample sized below the
250k daily pool. The sharded launcher now reports API token totals and supports an automatic
campaign-token cutoff. Publisher-dev cap repair was limited to seven GPT-5.4 truncations; the user
directed that completed mini remain untouched.

Final evidence and the scoped retired/personal-v3 decisions are in
[2026-08-18-gpt54-api-screen.md](results/2026-08-18-gpt54-api-screen.md).

## Personal-v3 extension

After personal-v3 became the active product regression, the user explicitly authorized sending
that 20-case internal suite to the OpenAI API and paying for the run. The two dated GPT-5.4 models
were rerun and `gpt-5.6-luna` was added. This extension did not rerun the HF/publisher source-dev
split, the retired 69 cases, or blind-v2. All three used the same sequential, streaming,
`baseline_rules`, `reasoning_effort=none`, temperature 0.1, seed 23, raw-scoring, Android-cap
profile. Complete results and raw-output review are in the final screen linked above.
