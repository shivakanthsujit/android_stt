# vLLM serving for cleanup evaluation

This path serves one pinned Qwen base plus the completed Sotto LoRA to many concurrent evaluation
clients. It is separate from the training environment and keeps every large package/cache under
`/data/rise/android_stt/vllm`; the nearly full home filesystem receives only the requested source
clone at `/home/shiva/vllm`.

## Pins and safety boundary

- vLLM checkout: release `v0.8.5`, commit
  `ba41cc90e8ef7f236347b2f1599eec2cbb9e1f0d`. This release pins Torch 2.6.0, matching the
  host's verified CUDA 12.4/Torch 2.6 stack, and its Qwen3 implementation declares LoRA support.
  The clean source checkout independently records the reviewed implementation; the environment
  installs the exact `vllm==0.8.5` release wheel with Python 3.10, Transformers 4.51.3, and
  CUDA 12.4 PyTorch wheels from the committed `training/vllm/uv.lock`.
  The installer fails if the checkout moves or is dirty. For research provenance, the clone was
  first inspected at main commit `017e9f4448b700e85ee16023287b025693c72b9e` before pinning the tag.
- Base: `Qwen/Qwen3-0.6B` revision
  `61641f84fa567ab7b58e216b4930d2fe28bfd045`, loaded from the already verified local snapshot.
- Adapter: `direct-sotto-qwen3-0.6b-e1-seed23-20260817T124158Z/final-adapter`, model SHA-256
  `22736a4d4aff8b5788386a80d643296874c3b54dd980404e7196a5665023fa2b`.
- Served adapter model name: `sotto-qwen3-0.6b-e1-seed23`.
- The server binds only `127.0.0.1`, disables request-payload and Uvicorn access logging, and does
  not enable runtime LoRA loading. It must not be pointed at blind-v2.

The setup follows vLLM's recommendation to use a fresh `uv` environment and install a prebuilt
wheel with uv: <https://docs.vllm.ai/en/latest/getting_started/installation/gpu/#pre-built-wheels>.
The explicit CUDA 12.4 backend prevents uv from selecting the cloned main branch's newer CUDA 12.9
stack.

## Install and start

Do not overlap this server with training or the old sequential publisher evaluator. The launcher
refuses to start while `nvidia-smi` reports another CUDA compute process unless the operator gives
the explicit override intended for controlled sharing.

```bash
./scripts/training/setup_vllm_env.sh

/data/rise/android_stt/vllm/env/bin/python \
  scripts/training/serve_vllm_checkpoint.py --print-command

/data/rise/android_stt/vllm/env/bin/python \
  scripts/training/serve_vllm_checkpoint.py \
  2>&1 | tee /data/rise/android_stt/vllm/server.log
```

In another shell:

```bash
python3 scripts/training/smoke_vllm_server.py
```

Clients use `http://127.0.0.1:8000/v1` and model
`sotto-qwen3-0.6b-e1-seed23`. Every request must include
`"chat_template_kwargs":{"enable_thinking":false}` to match training. v0.8.5 exposes this
request field but predates the current server-wide `--default-chat-template-kwargs` option. The
sharded runner owns the required request extra; the smoke client verifies it.

## Throughput rationale

The current profile uses one A6000, BF16, 90% GPU-memory utilization, a 4,096-token request limit,
256 sequence slots, a 16,384-token scheduler budget, chunked prefill (the V1 default), and automatic
prefix caching. vLLM recommends `max_num_batched_tokens > 8192` for throughput with small models on
large GPUs; the fixed cleanup instruction also gives prefix caching useful shared prompt blocks.
See <https://docs.vllm.ai/en/stable/configuration/optimization/#performance-tuning-with-chunked-prefill>.
Keep tensor/data parallel size at one: this host has one GPU and the 0.6B base already fits easily.
Both request-payload logging and per-request Uvicorn access logging are disabled to avoid logging
overhead and multi-thousand-line server logs during full evaluations.

The LoRA is registered at startup with `--enable-lora --lora-modules`; clients select it via the
normal OpenAI `model` field, as documented at
<https://docs.vllm.ai/en/stable/features/lora/#serving-lora-adapters>. `--generation-config vllm`
prevents repository generation defaults from silently changing the evaluation's request-level
decoding parameters.

Treat 16,384 tokens and 256 sequences as an initial throughput profile, not a universal optimum.
Benchmark the full real evaluation at several client concurrency levels and watch vLLM's
preemption metric/logs. If preemption appears, lower concurrency or the scheduler limits; if the
GPU remains underutilized without preemption, increase client concurrency before changing server
memory settings. The measured Qwen3-0.6B publisher sweep selected 64 clients: source-to-validated-
merge wall time was 91, 87, 83, and 84 seconds at 16, 32, 64, and 128 clients respectively. The
64-client intervals reached about 18.1k prompt tokens/s and 1.43k generated tokens/s without
waiting requests or preemption.

## Qwen3.5 follow-up

`Qwen/Qwen3.5-0.8B` is a multimodal hybrid model even when the workload contains only text. It is
not supported by the pinned v0.8.5 environment. The cloned latest main revision required Torch
2.13/CUDA 12.9, beyond this host's currently verified driver/runtime combination, so do not upgrade
the working server in place. Build a separately pinned environment after a compatible driver and
CUDA preflight. For that future adapter, add `--language-model-only`: vLLM says this skips the
vision encoder and frees memory for KV cache, and the official Qwen3.5 throughput recipe uses it
together with prefix caching. Sources:
<https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3.5.html#text-only> and
<https://docs.vllm.ai/en/stable/models/supported_models/#multimodal-language-models>.

Do not add MTP speculative decoding to the throughput profile. The Qwen3.5 guide describes it as a
low-concurrency latency optimization that reduces throughput under high concurrency. Expert
parallelism and data parallelism likewise do not apply to the dense 0.8B model on this one-GPU
host. Continue to use `--default-chat-template-kwargs '{"enable_thinking": false}'` so serving
matches the non-thinking training template.
