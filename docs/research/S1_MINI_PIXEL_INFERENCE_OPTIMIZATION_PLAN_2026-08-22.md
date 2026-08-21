# S1-mini Pixel inference optimization plan

Date: 2026-08-22

Status: approved sequence, API/runtime audits, and Stage 1 host implementation complete; new Pixel
measurements not started

## Objective

Reduce S1-mini cleanup latency, memory, energy, and sustained thermal pressure on the Pixel 7 while
preserving the exact S1-mini by Superwhisper inference contract and the existing personal-use
insertion policy.

The work proceeds in three controlled stages:

1. optimize the existing Liquid LEAP path without changing the model artifact;
2. compare a pinned direct llama.cpp Android runtime using the exact same GGUF; and
3. convert the exact S1-mini BF16 checkpoint to LiteRT-LM INT4 and compare its CPU and GPU paths.

Do not test lower-bit GGUF quantizations. In particular, Q3, Q2, IQ3, and IQ2 experiments are out
of scope because their potential quality loss is not justified for this product. Stage 3's
block-32 INT4 representation is a separate runtime conversion at the same nominal four-bit weight
precision as the selected Q4_K_M baseline, not permission to introduce lower-bit model variants.

## Fixed reference

The immutable performance reference is the official 484,219,808-byte
`s1-mini-q4_k_m.gguf`, SHA-256
`3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634`, running through LEAP
0.10.9's Android llama.cpp CPU backend.

Thermal-clean traced Pixel 7 reference:

- model load: 1,809 ms;
- median TTFT: 975.5 ms;
- median total: 1,576 ms;
- p90 total: 3,840 ms;
- long-form median total: 4,025.5 ms;
- median decode: 11.21 tokens/s;
- peak PSS: 1,293,620 KiB; and
- compute energy: 6.493 J/call.

The untraced sustained reference reached thermal status 1 after 27 of 60 measured calls. Complete
baseline evidence is in
`docs/evaluation/results/2026-08-21-s1-mini-v1-pixel.md`.

## Invariants for every stage

- Use the exact pinned S1-mini checkpoint or a reproducible conversion of that checkpoint. A
  generic Qwen3-0.6B artifact is never an S1 substitute.
- Preserve the exact publisher system prompt, trained
  `[Styling: semi-formal] [Structure: prose] [Context: general]` control line, tokenizer, chat
  template, empty thinking prefix, `enable_thinking=false` behavior, greedy decoding, and
  `ceil(1.3 * raw transcript tokens + 32)` output cap.
- Keep cleanup final-only. Never run S1 on live Parakeet partials.
- Preserve sequential sentence/EOU-aware passes for completed transcripts and the maximum 1,000
  raw-token pass policy unless a separately documented context experiment lowers that limit.
- Keep the runtime policy unchanged: use every sanitized non-empty generation that did not reach
  its output cap, and fall back only for blank or capped output.
- Keep complete raw model output and exact model input available for research/debugging.
- Do not use blind-v2. The committed cleanup suites and personal-v3 remain evaluation-only and
  may be used only for declared parity, stability, quality, and performance measurement.
- Never use evaluation inputs, targets, outputs, or discovered errors as conversion calibration
  data, prompt demonstrations, retrieval context, fine-tuning data, or repair examples.
- Keep models, converted weights, native build outputs, caches, traces, and raw results outside
  Git. Commit only code, locked configuration, manifests, hashes, and reviewed reports.
- Start evidence-bearing Pixel runs at thermal status 0, exclude warmup, retain failures, and do
  not silently restart with changed settings.
- Do not touch or install on the Pixel merely to prepare host code. Ask the owner immediately
  before each new device benchmark/install session.

## Common benchmark contract

Every candidate must run through the same debug-only transcript benchmark boundary and report:

- artifact and runtime revisions plus file SHA-256;
- prompt-token count and requested output cap for every case;
- raw output, finish reason, completion tokens, and repeat stability;
- model load, TTFT, total latency, and decode throughput;
- process CPU time, peak PSS/native heap, and thermal status;
- Perfetto CPU/GPU/memory-fabric energy for finalists; and
- short versus long-form latency separately.

Run a fast host/device smoke before a full matrix. Use the existing non-blind 69-case regression and
personal-v3 only after configuration parity is established. Direct same-GGUF comparisons should
produce exact tokenization/cap parity and should normally produce exact raw text; investigate every
difference. A newly quantized LiteRT artifact may differ textually, so review every difference
against the floating-point S1 reference and the existing semantic diagnostics before performance
can influence selection. Guardrail or fallback output never hides a raw runtime/conversion
difference in research evidence.

A new runtime replaces the production path only when it:

1. preserves the contract and deterministic bounded generation;
2. has no unacceptable raw-output regression under the existing evaluation policy;
3. completes the full benchmark without crash, leak, cap, or malformed-output regression; and
4. provides a material measured product benefit in latency, memory, energy, or sustained thermal
   behavior that justifies its added maintenance and packaging cost.

## Stage 1 — optimize the existing LEAP path

Goal: find improvements available without changing either the S1 GGUF or the production runtime
dependency.

### 1A. Freeze and parameterize the benchmark

- [x] Preserve the current LEAP 0.10.9 / Q4_K_M / 4,096-context run as the default control.
- [x] Add debug-only configuration metadata for every tested context/cache/runtime option.
- [x] Assert before generation that `prompt_tokens + requested_max_output_tokens` fits the selected
  context for every pass.
- [x] Keep production defaults unchanged until a candidate finishes the complete gate.

### 1B. Context and KV-memory study

The current engine requests a 4,096-token context even though one pass is bounded to 1,000 raw
tokens and an input-relative output cap. The pinned GGUF tokenizer produces 78 fixed tokens for the
empty transcript template. The largest permitted pass therefore requires
`78 + 1,000 + 1,332 = 2,410` tokens. Context 2,560 leaves 150 tokens of margin; context 2,048 is
unsafe. Retain a runtime assertion rather than relying only on this static calculation.

- [x] Record the exact maximum templated prompt plus output-cap requirement.
- [ ] Compare 4,096 control versus safe 3,072 and 2,560 candidates.
- [ ] Measure load, TTFT, total, PSS, native heap, energy, and output parity.
- [ ] If a smaller context cannot preserve the 1,000-token pass contract, reject it rather than
  silently truncating input or output.

### 1C. Prefix/cache and conversation study

The system prompt, control line, template, and empty thinking prefix are fixed across utterances.
The current engine sets LEAP `cacheOptions = null` and creates a new conversation for each pass.
LEAP 0.10.9 exposes a public memory-only `EngineOptions.CacheOptions`; its convenience cache helper
must not be used because it enables disk caching and large default entry/memory limits. Retain fresh
conversations because LEAP conversation reuse appends the preceding transcript and answer to
history and would violate request isolation.

- [x] Inventory the exact LEAP 0.10.9 public cache API and its correctness/lifecycle semantics.
- [ ] Compare cache-off with explicit memory-only configurations of four entries / 32 MiB and four
  entries / 64 MiB, with zero disk entries and `diskDisabled=true`.
- [x] Record `GenerationStats.cachedPromptTokens` so a cache result proves how much prefix work was
  actually reused.
- [ ] Verify that no preceding transcript or generated output enters a later request.
- [ ] Compare conversation reuse only if it can reset to the identical single-turn prompt; never
  trade speed for cross-utterance context contamination.

### 1D. CPU execution settings

- [x] Inventory LEAP execution controls. `ModelLoadingOptions` exposes `cpuThreads`,
  `cacheOptions`, `contextSize`, and `useMmap`; it does not expose batch or ubatch sizing. Its
  implicit `CpuThreadAdvisor` recommendation is capped at four threads and falls back to two when
  topology cannot be read.
- [ ] At context 4,096/cache-off, compare explicit two, three, and four CPU threads against the
  implicit control and record the resolved configuration.
- [ ] Use the winning thread count for the context comparison, then the winning thread/context for
  the cache comparison so only one variable changes at a time.
- [ ] Benchmark only documented settings. Do not depend on reflection or private ABI mutation.
- [ ] Retain mmap unless a measured alternative materially improves the complete product profile.

### Stage 1 host runner

The debug runner now accepts only the approved matrix and rejects invalid settings before model or
device work:

```text
S1_MINI_LEAP_CPU_THREADS=implicit|2|3|4
S1_MINI_LEAP_CONTEXT_SIZE=4096|3072|2560
S1_MINI_LEAP_CACHE_MB=0|32|64
```

Defaults remain `implicit`, `4096`, and `0`. Every run ID includes all three values. Raw JSONL and
summaries include context, thread mode/count, cache limits, disk-disabled policy, mmap, fixed prompt
tokens, cached prompt tokens, and the SDK-resolved CPU thread count. Measured work is repeat-major
with the warmed case rotated to the end of each pass; identical full prompts are therefore 20 calls
apart in the default corpus instead of adjacent, preventing the four-entry cache arm from receiving
an unrealistic whole-transcript reuse advantage. The scorer remains backward compatible with
earlier results and rejects mixed, incomplete, or out-of-matrix runtime metadata.

LEAP's public cache object retains a legacy aggregate `maxEntries` field internally, but the test
arm sets `diskDisabled=true`, `maxEntriesDisk=0`, and only four memory entries at 32 or 64 MiB. The
authoritative no-disk flag and the requested zero disk-entry value are recorded in every row; the
SDK may internally resolve its legacy aggregate entry field to a nonzero default, but no disk cache
is enabled. Each request still uses a fresh conversation and a dedicated cache-directory namespace.

### Stage 1 exit

- [ ] Select and document the best exact-contract LEAP configuration, or record that LEAP exposes
  no useful safe tuning.
- [ ] Update the reference numbers used by Stages 2 and 3.
- [ ] Do not conflate memory-only improvement with generation speedup.

## Stage 2 — direct llama.cpp with the same GGUF

Goal: determine whether a pinned, project-owned llama.cpp Android build improves on LEAP while
holding the S1 Q4_K_M bytes constant.

### 2A. Isolated native benchmark app

- [ ] Create a minimal separate Android benchmark module/APK with no LEAP, Moonshine, or Parakeet
  native dependencies. This is the first same-GGUF probe and avoids duplicate `libllama.so`,
  `libggml*.so`, and exported ggml symbols in one process.
- [ ] Pin llama.cpp commit `ece963f41` / build 10450 for the first comparison because it is the
  runtime already used by the validated Mac S1 Q4 reference. Pin Android NDK `28.0.13004108`,
  CMake `3.31.6`, compiler flags, source SHA-256, native-library hashes, and APK hash. Treat a newer
  llama.cpp revision as a separate later arm.
- [ ] Build ARM64 Release with runtime-selected CPU variants, native/OpenMP/llamafile disabled,
  and tests/examples/server omitted. Record the exact resolved flags rather than relying on
  defaults.
- [ ] Load the exact reference GGUF and reproduce the exact templated token IDs, prompt-token
  counts, output caps, greedy sampler, stop handling, and raw output.
- [ ] Record authoritative native prompt-eval and decode timings independently of Kotlin/JNI.
- [ ] Use a persistent native model/context handle, clear KV state between requests, and return
  prompt/completion counts, first-token/end timestamps, EOG-versus-cap finish, native timings, and
  selected backend/system information.

### 2B. CPU matrix

- [ ] Compare the Stage 1 winner with direct llama.cpp at the same context.
- [ ] Sweep generation threads 2/3/4 first; use 6/8 only as a bounded check of whether LITTLE cores
  hurt. Separately sweep batch threads 2/4/6/8 and batch/ubatch 128/256/512 without turning this
  into an open-ended search.
- [ ] Record mmap, flash-attention off/on, CPU feature variant, affinity/priority, and KV-cache type.
- [ ] Repeat the exact best setting from a fresh thermal-0 start before selection.

### 2C. Optional GPU probe

LEAP's current packaged backend is CPU-only. A direct GPU experiment is allowed only after the
same-GGUF CPU path reaches parity.

- [ ] Verify an actually supported Pixel 7 Mali backend and required Android driver/API before
  adding it to the app. Do not assume the Qualcomm-first OpenCL path applies to Tensor G2.
- [ ] Start with a standalone smoke and fail cleanly on unsupported operations or allocation.
- [ ] Compare prefill, decode, total latency, PSS, GPU/CPU rail energy, and thermal drift; GPU
  prefill speed alone is not sufficient.
- [ ] Reject output drift, instability, driver-specific crashes, or a worse sustained product
  profile even if one cold benchmark is faster.

### 2D. Android integration boundary

The app already packages LEAP's generic llama/ggml shared libraries and a statically isolated
`parakeet.cpp` ggml. A second llama.cpp must not expose colliding generic symbols or SONAMEs.

- [ ] Prefer mutually exclusive LEAP/direct Gradle variants for an eventual product comparison. If
  a same-APK debug toggle is necessary, use a uniquely named JNI library with statically owned
  ggml, hidden visibility, `--exclude-libs,ALL`, and an export map containing JNI only. Verify it
  has no `DT_NEEDED` entry for generic llama/ggml libraries and exports no `llama_*`/`ggml_*`.
- [ ] Add a `CleanupEngine` implementation without changing the coordinator, IME, microphone, or
  insertion policy.
- [ ] Keep LEAP available as the benchmark control until the direct path is selected or rejected.

### Stage 2 exit

- [ ] Publish a same-artifact LEAP-versus-direct report with output parity and complete Pixel
  performance evidence.
- [ ] Require at least 15% lower median total latency with no p90, PSS, energy, or thermal
  regression before the added native ownership can displace LEAP; otherwise retain LEAP.
- [ ] Replace LEAP only if the material benefit justifies owning the native runtime and collision
  surface; otherwise retain LEAP and preserve the direct probe as evidence.

## Stage 3 — S1-mini LiteRT-LM INT4 CPU/GPU

Goal: test a genuinely different Android execution stack while keeping the exact S1-mini learned
checkpoint and nominal four-bit deployment precision.

### 3A. Reproducible conversion

- [ ] Start from the exact pinned S1-mini BF16 safetensors and tokenizer snapshot, never from the
  GGUF and never from generic Qwen3-0.6B weights.
- [ ] Pin source revision `65f84bcda1d13df582c4a8443c1c5aa53c0c66db`. The 1,503,300,328-byte
  `model.safetensors` SHA-256 is
  `69d2057077ab4dc738aaaab75d2a8ffa141e3a09fb9d956198cfce46f381131a`; record the already
  verified config/tokenizer/template/generation/license/model-card hashes in the conversion
  manifest.
- [ ] Use the official Linux `litert-torch export_hf` path on the RTX A6000 host under
  `/data/rise/android_stt/`; this exporter is not a Mac conversion step. No training is involved.
- [ ] Pin LiteRT-LM, litert-torch, the AI Edge Quantizer, PyTorch, Python 3.11, and every resolved
  package/source revision in a dedicated conversion lock after a small canary.
- [ ] Record input file sizes/hashes, the complete conversion command/configuration, output file
  size/hash, prompt template, stop IDs, prefill signatures, KV layout/type, and context length.
- [ ] Export dynamic block-32 INT4 weights with FP32 activations and float KV unless current pinned
  tooling requires a separately documented equivalent. Do not use the misleading named
  `dynamic_wi4_afp32` recipe without metadata proof: the known form is channelwise and has a
  documented Qwen3-0.6B collapse. Require an explicit blockwise-32 recipe and inspect exported
  metadata. Exclude block-128, channelwise, and sub-four-bit variants.
- [ ] Keep the first comparison at a safe context matching the fixed S1 pass/output contract.
  Context reduction is a separate controlled follow-up, not a hidden part of conversion.
- [ ] Export a 4,096-token artifact first to isolate representation/runtime from context reduction.
  Only after exhaustive boundary tests may a second 2,560-token same-INT4 artifact be considered.

### 3B. Host correctness gate

- [ ] Verify tokenizer IDs, template expansion, empty thinking prefix, system/control placement,
  stop IDs, raw-token count, and requested output cap against the BF16 and GGUF references.
- [ ] Run deterministic smoke cases first, then the declared non-blind parity suites.
- [ ] Record every BF16/GGUF/LiteRT raw-output difference and perform semantic review before Pixel
  benchmarking can influence selection.
- [ ] Reject loops, malformed text, unexpected thinking content, cap handling drift, or an
  unacceptable conversion-induced semantic regression.

### 3C. Pixel runtime matrix

- [ ] Pin the LiteRT-LM Android Maven/runtime version; never use `latest.release` in the project.
- [ ] Add a debug-only `CleanupEngine` adapter and preserve the common result/timing schema.
- [ ] Benchmark CPU first, then GPU with identical artifact and generation settings.
- [ ] Record first-load compilation/cache creation separately from subsequent cold and warm loads.
- [ ] Measure TTFT, prefill/decode, total, PSS/native heap, energy rails, thermal drift, and output
  stability with the same methodology as the reference.
- [ ] Do not plan a Pixel 7 NPU arm. Public Google Tensor custom-model NPU support is not an
  available assumption for this device; revisit only with official, reproducible support.
- [ ] Prove GPU delegation in runtime logs and Perfetto GPU rails; silent CPU fallback is a failed
  GPU arm. Verify current-runtime greedy sampler behavior explicitly rather than inheriting older
  LiteRT-LM GPU sampler assumptions.

### Stage 3 exit

- [ ] Publish a BF16/GGUF/LiteRT conversion-parity report and a thermally controlled Pixel
  LEAP/direct/LiteRT comparison.
- [ ] Select CPU or GPU only from sustained total-product evidence, not vendor numbers from another
  model or phone.
- [ ] Keep the exact model name, license, attribution, and material-change disclosure required for
  any redistributed S1 conversion.

## Ordered tracker

| Order | Work item | State | Required output |
|---:|---|---|---|
| 0 | Freeze invariants, baseline, and benchmark schema | documented | this plan and existing Pixel report |
| 1 | LEAP API/settings audit | complete | supported-option inventory captured above |
| 2 | LEAP context/cache/CPU host implementation | complete | tests and debug-only parameters |
| 3 | LEAP Pixel A/B | pending owner-approved device run | raw results, power trace, report |
| 4 | Direct llama.cpp standalone same-GGUF parity | pending | pinned build manifest and native timings |
| 5 | Direct llama.cpp Android CPU A/B | pending | same-artifact comparison |
| 6 | Direct GPU feasibility probe | pending after CPU parity | supported/no-go evidence |
| 7 | LiteRT-LM S1 BF16 conversion | pending | `.litertlm` hash and conversion manifest |
| 8 | LiteRT host semantic/parity gate | pending | reviewed raw-difference report |
| 9 | LiteRT Pixel CPU/GPU A/B | pending owner-approved device run | performance/power report |
| 10 | Runtime selection and production swap, if earned | pending | decision, tests, rollback path |

The immediate executable task is Order 3: run the predeclared LEAP Pixel A/B in controlled phases,
starting with the implicit-thread/4,096/cache-off default control and explicit thread arms. This
runner installs and launches a debug APK, so obtain the owner's immediate device-session approval
before beginning.
