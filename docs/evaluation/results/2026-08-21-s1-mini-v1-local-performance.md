# S1-mini v1 local host performance: BF16, F16, and Q4_K_M

Date: 2026-08-21

## Outcome

S1-mini by Superwhisper is fast enough on the Apple M2 host to justify a later Pixel runtime
probe. Under the publisher's llama.cpp configuration, Q4_K_M completed the 20-case workload in
167.5 ms median, 1.84× faster than the same-runtime F16 control at 308.9 ms. Its native llama.cpp
decode median was 139.25 tokens/s versus 62.64 tokens/s for F16, a 2.22× speedup.

The actual BF16 reference weights were also measured—not mislabeled F16 GGUF. Under the
publisher's documented Transformers CPU path, BF16 completed requests in 1,720.9 ms median. That
makes Q4_K_M 10.28× faster in this cross-runtime host comparison. Runtime differences, prompt
caching, streaming behavior, and memory allocation make this useful product evidence but not an
isolated quantization microbenchmark.

This pass is performance-only. It did not score expected answers, semantic safety, or guardrail
behavior and therefore does not qualify S1-mini for deployment. The Pixel was not attached, so no
Android latency, thermal, power, or compatibility claim is made.

## Canonical measurements

Host: MacBook Air `Mac14,2`, Apple M2 (4 performance + 4 efficiency cores), 16 GB RAM, macOS
26.5.2 build 25F84. Warmup was excluded. Each value below covers 20 raw transcripts × 3 sequential
repeats.

| Artifact and runtime | Median TTFT | Median total | p90 total | Native decode median | Peak sampled RSS |
|---|---:|---:|---:|---:|---:|
| Q4_K_M GGUF, llama.cpp | 29.7 ms | 167.5 ms | 513.1 ms | 139.25 tok/s | 4.954 GiB |
| F16 GGUF, llama.cpp | 30.7 ms | 308.9 ms | 995.0 ms | 62.64 tok/s | 5.899 GiB |
| BF16 safetensors, Transformers CPU | 1,088.8 ms | 1,720.9 ms | 3,983.6 ms | not cross-runtime comparable | 1.555 GiB |

Long-form cases 015, 018, 019, and 020 were intentionally retained:

| Runtime | Short-case median total | Long-form median total |
|---|---:|---:|
| Q4_K_M GGUF | 149.5 ms | 533.0 ms |
| F16 GGUF | 287.7 ms | 1,080.5 ms |
| BF16 Transformers CPU | 1,645.9 ms | 4,158.7 ms |

Same-runtime Q4_K_M versus F16:

- median total latency: 45.8% lower, or 1.84× faster;
- p90 total latency: 48.4% lower, or 1.94× faster;
- native decode rate: 2.22× faster;
- server health readiness: 1,814.7 ms versus 2,227.3 ms;
- peak sampled server RSS: 0.945 GiB lower, a 16.0% reduction.

The GGUF RSS values are deliberately not model-weight-only footprints. With no undocumented
tuning, llama-server selected four slots, a 40,960-token context per slot, and unified KV. That is
the exact-config server footprint measured here and explains why it is much larger than either
GGUF file. It must not be used as a Pixel estimate. The BF16 process used PyTorch's default four
CPU threads; its 278.8 ms deserialization-to-ready value is lazy/memory-mapped and is not
comparable to llama-server health readiness. Peak RSS during real inference is the meaningful BF16
memory observation.

## Raw-output agreement, not quality scoring

Both BF16 and F16 were stable on 20/20 cases across all three repeats, and BF16 matched F16 on
60/60 requests. Q4_K_M matched BF16/F16 on 48/60 requests (80%). The 12 differing requests were
the three repeats of four cases: `personal-v3-008`, `personal-v3-013`, `personal-v3-014`, and
`personal-v3-020`.

Because this pass deliberately did not inspect expected answers or judge semantics, those four
deterministic differences are not classified as accuracy loss, improvement, or harmless
variation. A later quality pass must make that determination before any model-selection claim.

## Publisher configuration preserved

The configuration follows the [official S1-mini v1 model card](https://huggingface.co/superwhisper/s1-mini/tree/v1):

- exact required system prompt, stored at `docs/evaluation/prompts/s1-mini-v1-system.txt` with
  SHA-256 `6ecb6800f96b00cf612631552eff606a829feb2be8449fa95f9f150713b89327`;
- exact control line
  `[Styling: semi-formal] [Structure: prose] [Context: general]`;
- thinking disabled through `enable_thinking=false`;
- greedy decoding (`temperature=0` / `do_sample=False`);
- `max_new_tokens = ceil(1.3 × raw transcript tokens + 32)`;
- no `--reasoning-budget 0`, which the publisher explicitly warns changes the trained prefix;
- one transcript per request, all below the recommended roughly 1,000-token ceiling.

The GGUF server configuration was:

```text
llama-server --model <artifact> --jinja \
  --chat-template-kwargs '{"enable_thinking":false}' --temp 0
```

Host/port, model alias, and `--no-webui` were operational settings only. llama.cpp 10450 warns
that setting `enable_thinking` through `--chat-template-kwargs` is deprecated, but the option was
kept unchanged because it is the publisher's documented S1-mini v1 configuration. Transformers
4.57.6 similarly warns that `torch_dtype` is deprecated in favor of `dtype`; BF16 retained the
documented `torch_dtype="auto"` call, and all 311 loaded tensors were verified as
`torch.bfloat16`.

The corpus was `docs/evaluation/cleanup_personal_conversation_v3.jsonl`, SHA-256
`667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`. The harness reads only each
row's `id` and `raw`; committed reference/expected fields are neither read nor scored.

## Artifact and runtime identity

| Artifact | Revision | Bytes | SHA-256 |
|---|---|---:|---|
| BF16 `model.safetensors` | `65f84bcda1d13df582c4a8443c1c5aa53c0c66db` | 1,503,300,328 | `69d2057077ab4dc738aaaab75d2a8ffa141e3a09fb9d956198cfce46f381131a` |
| F16 `s1-mini-f16.gguf` | `8eab4779866f477ae6e7f237ca45fc2c65153f50` | 1,509,347,232 | `0370da4f1bae19e3150bcafa33c5d396c15f97bf25519540a3e013db5cc00af4` |
| Q4_K_M `s1-mini-q4_k_m.gguf` | `8eab4779866f477ae6e7f237ca45fc2c65153f50` | 484,219,808 | `3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634` |

The BF16 runtime was PyTorch 2.13.0 plus Transformers 4.57.6 on CPU. The GGUF runtime was
llama.cpp build 10450, commit `ece963f41`, with Metal acceleration. Downloaded weights, runtime
environment, raw outputs, and logs remain ignored and outside Git.

Canonical ignored evidence:

- GGUF JSON SHA-256: `8c8d2e720ad4e0815984716981503021370b23b0817bfa2aaa853cf2457f8a07`;
- Q4_K_M server log SHA-256: `6c558331211c6c4bd8c03630886dfef2929d0d32af125b82d79cdabab495cd9f`;
- F16 server log SHA-256: `60e0d01b8924701c9dcd41623149492b25a9dbf50d4bc012048cb9b507cb9f07`;
- BF16 JSON SHA-256: `fb7519084661c4ec210acb7972fb16202ee0f846f6de769e6f92c3330d8e53a2`;
- BF16 console log SHA-256: `5e949033418adba5b2b99fc15b53ade230134558327fa83b5c225c12869270e7`.

The reproducible harnesses are `scripts/benchmark-s1-mini.py` and
`scripts/benchmark-s1-mini-bf16.py`. The initial restricted-sandbox attempt could not bind the
local server or query process RSS and is excluded; the canonical run was repeated unchanged with
the required local process permissions.

## Next evidence

When the Pixel returns, first select or implement an Android runtime that can reproduce the empty
thinking prefix and exact control contract. Then measure Q4_K_M on-device latency, RSS/PSS,
thermal state, and energy without inferring results from this Mac. BF16 Pixel feasibility remains
open; neither the Transformers host result nor the F16 GGUF control demonstrates an Android BF16
path.

Semantic comparison of the four differing Q4 cases is intentionally deferred until a quality
benchmark is requested. That later pass must retain raw-output safety review and cannot let a
guardrail fallback qualify the model.
