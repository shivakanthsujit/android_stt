# S1-mini v1 local host performance: BF16, F16, and Q4_K_M

Date: 2026-08-21

## Outcome

S1-mini by Superwhisper is fast enough on the Apple M2 host to justify a later Pixel runtime
probe. Across the project's 69-case seed + held-out cleanup screen, Q4_K_M completed requests in
110.2 ms median, 1.87× faster than the same-runtime F16 control at 206.0 ms. Its pooled native
llama.cpp decode median was 141.17 tokens/s versus 64.85 tokens/s for F16, a 2.18× speedup.

The actual BF16 reference weights were also measured—not mislabeled F16 GGUF. Under the
publisher's documented Transformers CPU path, BF16 completed the 69-case screen in 2,147.6 ms
median. That makes Q4_K_M 19.48× faster in this cross-runtime host comparison. Runtime
differences, prompt caching, streaming behavior, and memory allocation make this useful product
evidence but not an isolated quantization microbenchmark.

This pass is performance-only. It did not score expected answers, semantic safety, or guardrail
behavior and therefore does not qualify S1-mini for deployment. The Pixel was not attached, so no
Android latency, thermal, power, or compatibility claim is made.

## Project 69-case performance screen

The project screen combines `cleanup_cases.jsonl` (24 cases) and
`cleanup_cases_heldout_v1.jsonl` (45 cases). Warmup was excluded and every case received three
sequential measured requests, for 207 requests per artifact.

| Artifact and runtime | Median TTFT | Median total | p90 total | Maximum total | Native decode median |
|---|---:|---:|---:|---:|---:|
| Q4_K_M GGUF, llama.cpp | 31.8 ms | 110.2 ms | 140.0 ms | 224.2 ms | 141.17 tok/s |
| F16 GGUF, llama.cpp | 32.5 ms | 206.0 ms | 264.1 ms | 381.4 ms | 64.85 tok/s |
| BF16 safetensors, Transformers CPU | 1,703.5 ms | 2,147.6 ms | 2,549.6 ms | 5,130.7 ms | not cross-runtime comparable |

Q4_K_M is 1.87× faster than F16 at median total and 1.89× faster at p90 total in the same
llama.cpp runtime. It is 19.48× faster than the documented BF16 CPU path at median total. The
three valid empty completions for `heldout-015` have total latency but no first output text, so
pooled TTFT uses 204 non-empty requests rather than all 207.

| Suite | Runtime | Median TTFT | Median total | p90 total |
|---|---|---:|---:|---:|
| 24-case seed | Q4_K_M | 31.5 ms | 122.8 ms | 156.6 ms |
| 24-case seed | F16 | 31.9 ms | 231.6 ms | 304.6 ms |
| 24-case seed | BF16 | 1,384.2 ms | 1,896.6 ms | 2,581.7 ms |
| 45-case held-out | Q4_K_M | 32.2 ms | 106.9 ms | 128.9 ms |
| 45-case held-out | F16 | 32.9 ms | 199.8 ms | 242.9 ms |
| 45-case held-out | BF16 | 1,760.5 ms | 2,193.0 ms | 2,546.8 ms |

Q4_K_M peak sampled llama-server RSS was 4.927 GiB on the seed suite and 4.926 GiB on held-out;
F16 was 5.880 and 5.887 GiB. BF16 Transformers peaked at 1.549 GiB in each separately launched
suite. These remain runtime-allocation measurements, not comparable model-only footprints.

Secondary diagnostics retained from the canonical JSON:

| Suite/runtime | Ready or load | Ready RSS | Peak RSS | Output tokens median/total | Client-derived decode median/p10 |
|---|---:|---:|---:|---:|---:|
| Seed Q4_K_M | 1,160.6 ms | 4.880 GiB | 4.927 GiB | 13 / 897 | 140.49 / 124.50 tok/s |
| Seed F16 | 1,374.9 ms | 5.825 GiB | 5.880 GiB | 13 / 897 | 65.08 / 60.65 tok/s |
| Seed BF16 | 328.6 ms | 0.423 GiB | 1.549 GiB | 13 / 897 | unavailable |
| Held-out Q4_K_M | 1,063.9 ms | 4.880 GiB | 4.926 GiB | 11 / 1,359 | 141.42 / 135.93 tok/s |
| Held-out F16 | 1,183.8 ms | 5.884 GiB | 5.887 GiB | 11 / 1,338 | 64.65 / 58.65 tok/s |
| Held-out BF16 | 292.3 ms | 0.422 GiB | 1.549 GiB | 11 / 1,338 | unavailable |

For GGUF, “Ready or load” is process start to healthy llama-server. For BF16, it is tokenizer plus
model deserialization to `model.eval()` and is lazy/memory-mapped. The two columns must not be
treated as equivalent cold-load measurements. “Client-derived decode” divides output tokens by
the post-first-text interval and is retained as an approximate JSON diagnostic; the pooled native
llama.cpp timing above is the authoritative same-runtime decode comparison. The BF16 harness does
not emit a comparable decode-rate statistic.

## Personal-v3 canonical measurements

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

All three variants were stable on all 89 cases across all three repeats. BF16 matched F16 on
267/267 requests across the 69-case project screen plus personal-v3. Q4_K_M matched BF16/F16 on:

- 72/72 seed requests (24/24 cases);
- 129/135 held-out requests (43/45 cases), differing on all repeats of `heldout-006` and
  `heldout-039`;
- 48/60 personal-v3 requests (16/20 cases), differing on all repeats of `personal-v3-008`,
  `personal-v3-013`, `personal-v3-014`, and `personal-v3-020`;
- 201/207 requests (97.1%) on the 69-case project screen and 249/267 (93.3%) across all 89 cases.

Because this pass deliberately did not inspect expected answers or judge semantics, those six
deterministic case differences are not classified as accuracy loss, improvement, or harmless
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

The corpora and SHA-256 identities were:

- `cleanup_cases.jsonl`: `1cf4335b7679c81ca55c9d1cd4b9d25ee69a37dcecfff72f3c03740cd53573b9`;
- `cleanup_cases_heldout_v1.jsonl`:
  `cc1dfb4033b0336bface23f56e993fef894c5db87c57d137ffee188ce6ea2d71`;
- `cleanup_personal_conversation_v3.jsonl`:
  `667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`.

The harness reads only each row's `id` and `raw`; committed reference/expected fields are neither
read nor scored. Blind-v2 and the STT/audio suites were not used.

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
- BF16 console log SHA-256: `5e949033418adba5b2b99fc15b53ade230134558327fa83b5c225c12869270e7`;
- seed GGUF JSON SHA-256: `a462d29d60999667b354a8cb7b0e4fd5d8cdbf7fd71e1347735b7ee5b99b60b7`;
- seed BF16 JSON SHA-256: `a5bb29abef2c3d385bd2cee575da815f91da43041b58c7dad4b0b13bb31b147f`;
- held-out GGUF JSON SHA-256: `dbcd1d5c26fdf5dcb5d9d8f8f9f79ed73606d6551189bb6621dec0c1e831158c`;
- held-out BF16 JSON SHA-256: `00c5d3d5977a6f4cdec898d498752359d32df0928ae9a5a9c5860b3e4cd7e29a`;
- seed Q4/F16 server-log SHA-256:
  `a116417ae4c5be2e18d21710b21418aa3ef403c365a29d494807c0529fef7347` /
  `386290997f72a8a51db787864f4856243cc3e64264fff8267a2e6082ca5844d6`;
- held-out Q4/F16 server-log SHA-256:
  `3b981726368924a7dc27cdf4c56a21f67a8c0854dd26fefe88adfaa90d280f8f` /
  `c79bf5f80bb272e51accb20cc228db9bc9abe6d53940a91aaba782ca326d1175`.

The reproducible harnesses are `scripts/benchmark-s1-mini.py` and
`scripts/benchmark-s1-mini-bf16.py`. The initial restricted-sandbox attempt could not bind the
local server or query process RSS and is excluded; the canonical run was repeated unchanged with
the required local process permissions. A later user-interrupted seed attempt is also excluded.
The first held-out attempt then stopped on a harness validation error when filler-only
`heldout-015` validly returned an empty string. The corrected harness retains a zero-token
completion, has a regression test for the publisher-documented behavior, and the held-out suite
was rerun from a fresh path without changing inference configuration.

## Next evidence

When the Pixel returns, first select or implement an Android runtime that can reproduce the empty
thinking prefix and exact control contract. Then measure Q4_K_M on-device latency, RSS/PSS,
thermal state, and energy without inferring results from this Mac. BF16 Pixel feasibility remains
open; neither the Transformers host result nor the F16 GGUF control demonstrates an Android BF16
path.

Semantic comparison of the six differing Q4 cases is intentionally deferred until a quality
benchmark is requested. That later pass must retain raw-output safety review and cannot let a
guardrail fallback qualify the model.
