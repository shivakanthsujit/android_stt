# Decisions

Last updated: 2026-08-18

## Product and architecture

1. Build and benchmark the ordinary Activity before introducing Android IME lifecycle complexity.
2. Keep STT and cleanup implementations behind interfaces so alternatives can be benchmarked.
3. Use explicit tap-to-start/tap-to-stop for V1; automatic endpointing is later polish.
4. Preserve full offline operation after one-time model setup. Do not silently add cloud fallback.
5. Keep transcript contents out of Logcat. UI may display them locally.

## Speech recognition

1. Start with Moonshine Voice `0.1.2`, English Small Streaming architecture `4`; Moonshine's helper
   defaults to the much larger Medium model, so the architecture must be explicit.
2. Own Android audio capture in this project. `MicTranscriber.stop()` leaves its `AudioRecord`
   capture infrastructure open, which violates the required microphone lifecycle.
3. Keep the Moonshine model loaded between utterances, but create `AudioRecord` only on Start and
   stop it synchronously on Stop.
4. Treat Android's built-in on-device SpeechRecognizer as an empirical A/B candidate, not an
   assumed replacement. Pixel-specific quality and punctuation must be measured.
5. Defer the formal STT comparison while cleanup is the demonstrated blocker. The current working
   offline Moonshine path is a provisional input, not the final STT selection.

## Cleanup

1. Liquid LEAP `0.10.9` remains the measured Android runtime; 230M, 350M, and 1.2B-Instruct
   `Q4_K_M` are all rejected as automatic cleanup models.
2. First prove manual text cleanup independently; join STT only after the cleanup smoke test works.
3. Use deterministic, conservative generation. Preserve meaning, apply obvious self-corrections,
   remove fillers/abandoned starts, fix punctuation, never answer dictated questions, and emit only
   cleaned text.
4. Fall back to raw text for empty output or suspicious expansion (initial ceiling: 1.8× raw
   character count, subject to evaluation).
5. Treat positive anchor preservation as necessary but insufficient: copied disfluencies can score
   well, and summaries can preserve some anchors while changing intent.
6. Require zero meaning changes, zero answered instructions after guardrails, and successful explicit
   self-correction handling before joining cleanup to STT.
7. The three Liquid no-go results reject those candidates, not all small-model cleanup. Before STT
   integration, run one bounded cross-family screen: Granite 4.0 H 350M, Qwen3-0.6B no-think, and
   Gemma 3 270M, with Qwen3.5-0.8B and Gemma 3 1B reserved for a second wave.
8. Screen quality before adding a runtime to the Android app. Only models with zero semantic safety
   failures and successful self-corrections earn Pixel performance work.
9. Prefer LiteRT-LM for the first Qwen Android run and llama.cpp for GGUF/Granite portability.
   Benchmark LiteRT CPU and GPU on Pixel 7; do not assume a Tensor G2 NPU path.
10. Benchmark deterministic cleanup and a hybrid deterministic/LLM router. Comparable open Android
    keyboards show that conservative mechanical cleanup can cover common cases without generation.
11. Reject Granite 4.0 H 350M, Qwen3 0.6B, Gemma 3 270M, Qwen3.5 0.8B, and Gemma 3 1B for automatic
    cleanup after the 45-case held-out host screen. Each failed the semantic safety or explicit
    self-correction gate; guardrail fallback did not make the underlying cleanup adequate.
12. Do not add LiteRT-LM or llama.cpp to Android merely to benchmark a failed model. Quality gates
    runtime work. The next generative cleanup candidate should be task-specific rather than another
    untuned small chat model.
13. Keep the deterministic cleaner as a near-zero-latency control, not as the selected product
    cleaner: it scored 0/7 exact on held-out self-corrections.
14. Make task-specific cleanup the active milestone. First screen the public VoiceInk Qwen3.5-2B
    fine-tune as a quality probe; if it is too large or slow, use it only as a reviewed teacher and
    fine-tune a smaller Qwen base.
15. The committed 24-case and 45-case suites are regression evidence, not training data. Because
    the 45-case set informed guardrail fixes, create a new untouched blind v2 set before measuring
    any trained model's generalization.
16. A 2B model may establish achievable cleanup quality without being shippable. Android runtime
    work remains gated on both semantic quality and a mobile-appropriate quantized artifact.
17. Reject the VoiceInk Qwen3.5-2B Q4_K_M checkpoint after its exact native-prompt screen. It failed
    8/10 corrections semantically/exactly, retained superseded content six times, changed facts or
    meaning three times, and followed one dictated instruction. It is not an automatic labeler.
18. Prepare training data, validators, manifests, and runbooks on this Mac, but run LoRA/QLoRA only
    on the separate training machine. No local training job is authorized or needed now.
19. Use Sotto transcript cleanup as the primary public-data candidate, with Disfl-QA and Nyra
    Disfluency Speech as supplements. Pin immutable revisions and treat every row as untrusted;
    reject or quarantine grammar rewrites, guessed ASR corrections, unsafe deletions, and other
    policy conflicts before project splitting or training.
20. A new RTX A6000 session may build and run the documented pilot, but it must pass Gate A first,
    keep blind-v2 outside the optimization context, monitor/resume long jobs reproducibly, and keep
    datasets, weights, checkpoints, secrets, and private references out of git.
21. Keep RTX source payloads, Hugging Face caches, run directories, adapters, optimizer state, and
    checkpoints under `/data/rise/android_stt/`, outside the repository. Git receives only code,
    locked configuration, sanitized manifests/reports, and project documentation. Checkpoint
    transfer to another machine remains a separate user decision; do not commit checkpoints.
22. Treat explicit spoken bullet-list, numbered-list, paragraph-break, and punctuation directives
    as transcript editor controls under dataset/annotation policy v2. General commands and
    instruction-like content remain literal text; cleanup never answers or performs external
    actions. Keep grammar rewriting and guessed-ASR repair excluded from this safety-first pilot,
    and require human review for every formatting row.
23. Supersede the grammar/ASR exclusion in decision 22 after product clarification: represent all
    relevant Sotto operation categories in the pilot, including conservative grammar repair,
    context-supported ASR repair, mixed/crutch-word cleanup, explicit formatting, adversarial
    content, protected literals, high-stakes text, and declared lexical additions. Keep them in
    separate capped strata or cross-cutting audits, require row-level human approval, and reject
    speculative, invented, meaning-changing, or ungrounded protected-literal edits. This expands
    the editor behavior without permitting answers or external actions.
24. Fill only measured public-source coverage gaps with a deterministic project-authored
    supplemental candidate generator. The text-free pinned-source profile proves shortages in
    adversarial-primary, explicit-paragraph, adversarial cross-cutting, and Unicode/multilingual
    coverage even before unsafe rows are removed. Keep generated JSONL and review ledgers outside
    Git; commit and hash the generator/configuration, mark every generated row pending, require
    explicit human approval, and select deterministically against both exact primary quotas and
    cross-cutting minima rather than lowering quotas or approving unsafe public targets.
25. Before finishing the reviewed 5,000/500 qualification corpus, run a separate exploratory
    direct-source experiment to obtain model evidence quickly. Train four adapters on Sotto,
    Disfl-QA, Nyra text pairs, and their combined publisher train splits. Hold Qwen3-0.6B and a
    one-epoch LoRA recipe fixed, run Sotto first, and compare raw output on publisher validation
    plus the retired 69 diagnostics. These adapters may inform data/base/recipe choices but cannot
    qualify for deployment without the later safety, review, blind-isolation, and raw semantic
    gates. Keep the direct trainer separate from the reviewed-pilot Gate A path.
26. Keep BF16 rank-16 LoRA for the first direct-source Qwen3-0.6B comparison. Although a full
    sub-1B tune fits the RTX A6000, do not confound the dataset experiment with an adaptation-method
    change. If the best source recipe learns useful behavior but plateaus, compare higher-capacity
    LoRA and full BF16 fine-tuning in a separately named study. Use Qwen3.5-0.8B as the first
    stronger base; retain Gemma 3 1B as the measured quality alternative and LFM2.5-350M as the
    deployment-speed wildcard. Gemma 4 E2B is outside this experiment because its total parameter
    footprint is about 5.1B, not sub-1B.
27. Raise the fixed direct-source maximum formatted sequence from 1,024 to 2,112 tokens after the
    complete Sotto audit found 775 train and 46 validation rows over the old limit, with a maximum
    of 2,050. Preserve the full publisher splits and no-truncation policy. Use microbatch 4 plus
    gradient accumulation 8 across the four-way comparison to retain effective batch 32: the
    original microbatch 8 OOMed on the 1,838-token longest train row, while the revised recipe
    passed the exact two-step worst-case A6000 diagnostic without gradient checkpointing.
28. Treat Sotto's official Hugging Face model-card history as a training reference, not as a formal
    paper or a recipe to copy into the active Qwen run. Its clearest SFT record uses full tuning of
    LFM2.5-350M for three epochs at 3e-5, effective batch 8, packed 4,096-token context, AdamW
    beta2 0.95, and later GRPO/refinement/soup stages. Keep the current one-epoch rank-16 Qwen LoRA
    dataset comparison unchanged. If it is useful but undertrained or adapter-limited, run
    separately named three-epoch and full-BF16 comparisons; do not silently extend or reinterpret
    the current 4,235-step run.
29. Reject the one-epoch Sotto-only Qwen3-0.6B adapter as a deployment candidate despite its strong
    51/69 retired-diagnostic exact score. Agent review found eight substantive raw-policy failures,
    including answered content and protected entity, name, identifier, numeric-surface, intent,
    and deletion errors. Full publisher validation reached only 4,751/6,921 raw exact, with 48
    output-cap hits and 3,098 guardrail flags. Guardrail fallback remains defense in depth and
    cannot rescue raw semantic safety. Keep the adapter/checkpoints as experimental evidence under
    the completed run directory.
30. Do not skip standalone Disfl-QA or Nyra training based on Sotto-adapter transfer. Cross-dataset
    exactness was 472/1,000 for Disfl-QA with 732 guardrail flags and 32/250 for Nyra with 76 flags.
    Run the identical one-epoch source adapters after Sotto publisher scoring; decide on the combined
    run afterward rather than assuming it is necessary.
31. Serve RTX evaluation checkpoints through a separately locked vLLM environment rather than the
    training environment. For the current Qwen3-0.6B LoRA on one A6000, pin vLLM 0.8.5 with the
    CUDA 12.4 wheel stack, BF16, prefix caching, a 16,384-token scheduler budget, no request/access
    logging, and request-level `enable_thinking=false`. Use deterministic SHA-256 case sharding,
    strict resume/merge validation, raw scoring, and 64 clients as the measured publisher default.
    Re-benchmark concurrency for a different model or workload. For future multimodal Qwen3.5
    served on a compatible newer vLLM/driver stack, use text-only language-model mode and omit MTP
    for high-concurrency throughput.

## Android/toolchain

1. Pixel-7-first, `arm64-v8a`, minSdk 31.
2. Use Views/XML to minimize Activity and future IME integration overhead.
3. Keep AGP 8.13.2, Gradle 8.13, Kotlin 2.3.20, API 36, and JDK 17 while those are the verified
   Liquid/Moonshine-compatible versions.
