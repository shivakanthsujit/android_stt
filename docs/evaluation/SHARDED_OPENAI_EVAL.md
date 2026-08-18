# Sharded OpenAI-compatible cleanup evaluation

Use `run-cleanup-openai-sharded.py` to keep one vLLM server busy with multiple independent HTTP
clients. Assignment is `SHA-256(case_id) modulo N`, so shards are deterministic, disjoint, and do
not move when the case file is reordered. Each client owns a collision-free JSONL file. The
launcher merges only after every client exits successfully. To avoid thousands of synchronized
terminal writes during high-throughput runs, it reports each shard's first, every 100th, and final
case by default; change this with `--progress-every` or use `0` for quiet operation.

For the current direct-source adapters, use the exact training interface:

- system: committed `training/config/cleanup-instruction-v2.txt`;
- user: `Transcript:\n{raw}`;
- `temperature=0.0`;
- Qwen `enable_thinking=false`; and
- raw model output selected for scoring. Guardrail output is recorded separately and cannot turn a
  raw semantic failure into a passing checkpoint.

The following is one command from the repository root. Keep generated results outside Git:

```bash
python3 scripts/run-cleanup-openai-sharded.py \
  --model sotto-qwen3-0.6b-e1-seed23 \
  --base-url http://127.0.0.1:8000/v1 \
  --cases docs/evaluation/cleanup_cases.jsonl \
  --output-dir /data/rise/android_stt/evaluation/retired-seed-shards \
  --output /data/rise/android_stt/evaluation/retired-seed-results.jsonl \
  --clients 8 \
  --prompt-variant cleanup_instruction_v2 \
  --temperature 0 \
  --request-extra docs/evaluation/request_extras/qwen-no-thinking.json \
  --resume
```

Use a new output directory and merged path for `cleanup_cases_heldout_v1.jsonl`. Publisher
validation files produced by `prepare_direct_source_validation.py` have the same required schema,
so pass their outside-Git JSONL path to `--cases` unchanged. The authoring-side runner rejects case
paths containing `blind` and records marked with a blind split; do not use it for blind-v2.

Hosted GPT-5.4-family endpoints require `--output-token-field max_completion_tokens`. Keep the
default `max_tokens` for local OpenAI-compatible servers that implement that field.
For quota-bounded hosted runs, `--token-progress-seconds N` prints cumulative API-reported input
and output usage across flushed shards. Use `--token-offset-input` and `--token-offset-output` for
earlier same-pool traffic, then set `--max-campaign-tokens` to terminate all clients and preserve
their resumable shard prefixes before the account ceiling. `--output-cap-policy publisher` matches
the checkpoint source-dev allowance; the default `android` keeps the production 16–96-token cap.

`--resume` is safe on the first launch and on a retry. It validates every completed row against the
case-file hash, evaluation fingerprint, source index, shard assignment, and completed-prefix order
before appending. It refuses incomplete JSON, config drift, duplicates, and reassignment rather
than repairing or deleting evidence. A failed client leaves every shard file in place and skips
the merge.

The merger validates all case fields and result fields, requires one consistent evaluation
fingerprint, rejects duplicates/missing cases/wrong-shard rows, and writes the final JSONL in
source-file order. It also requires raw output, raw-scoring mode, guardrail selection, TTFT, and
total latency on every row. To validate or redo only the merge:

```bash
python3 scripts/merge-cleanup-openai-shards.py \
  --cases /outside/git/publisher-validation.jsonl \
  --shard-count 8 \
  --input /outside/git/shards/shard-00-of-08.jsonl \
  --input /outside/git/shards/shard-01-of-08.jsonl \
  --input /outside/git/shards/shard-02-of-08.jsonl \
  --input /outside/git/shards/shard-03-of-08.jsonl \
  --input /outside/git/shards/shard-04-of-08.jsonl \
  --input /outside/git/shards/shard-05-of-08.jsonl \
  --input /outside/git/shards/shard-06-of-08.jsonl \
  --input /outside/git/shards/shard-07-of-08.jsonl \
  --output /outside/git/publisher-validation-results.jsonl
```

Neither launcher nor merger overwrites outputs. Change the result path if a validated merged file
already exists. Increase `--clients` while vLLM throughput improves; client count does not alter
decoding, output bounds, or case membership correctness. On the current Qwen3-0.6B LoRA/A6000
publisher workload, a full-corpus sweep found 64 clients fastest among 16, 32, 64, and 128. Treat
64 as the current default, not a universal constant: sequence lengths, output lengths, model size,
and GPU can move the optimum.

## Reproducibility boundary

Deterministic sharding guarantees case membership, assignment, resume validation, and merge order;
it does not make GPU inference batch-invariant. The pinned vLLM 0.8.5 server can choose slightly
different greedy tokens as continuous-batching composition changes, even with temperature zero and
a request seed. The measured publisher exact counts were 4,750, 4,746, 4,744, 4,739, 4,739, and
4,745 across the initial 16-client run and final 16/32/64/64-repeat/128-client runs, versus 4,751
from sequential Transformers inference. Every run still contained exactly 6,921 cases, zero empty
outputs, and 48 cap hits. Each vLLM run differed from sequential output on 110–124 rows; the two
64-client repeats differed from each other on 75 rows despite sharing the same 4,739 exact count.
The aggregate exact-rate range is narrow (68.47–68.63% for vLLM versus 68.65% sequential), but the
runs are not interchangeable at the case level. The committed 24- and 45-case diagnostics did
match sequential inference bit-for-bit.

Use one pinned backend and concurrency for checkpoint comparisons. For this workload, use the
64-client vLLM profile consistently and repeat any borderline comparison; do not compare a
sequential score directly with a vLLM score. Current vLLM documents that default online inference
is not reproducible across batching and provides batch invariance in newer releases, with a
performance cost. That feature is absent from the pinned CUDA-12.4-compatible v0.8.5 release, so
adopting it requires a separately pinned newer environment and a fresh throughput/correctness
sweep. See <https://docs.vllm.ai/en/stable/usage/reproducibility/> and
<https://docs.vllm.ai/en/stable/features/batch_invariance/>.
