# Decisions

Last updated: 2026-08-22

## Product and architecture

1. Build and benchmark the ordinary Activity before introducing Android IME lifecycle complexity.
2. Keep STT and cleanup implementations behind interfaces so alternatives can be benchmarked.
3. Use explicit tap-to-start/tap-to-stop for V1; automatic endpointing is later polish.
4. Preserve full offline operation after one-time model setup. Do not silently add cloud fallback.
5. Keep transcript contents out of Logcat. UI may display them locally.
6. After completing the ordinary joined Activity baseline, move product work to a minimal
   voice-only IME while cleanup and STT qualification continue in parallel. Reuse an
   application-scoped model coordinator, preserve explicit microphone control, and keep model
   replacement behind the existing interfaces.
7. Share one application-scoped Parakeet/selected-cleanup engine pair between the Activity and IME.
   The IME never starts recording on editor focus, blocks password/private fields, invalidates
   output when the editor changes, commits only the selected local result, and permits Undo only
   while the exact inserted text remains immediately before the cursor in the same editor. Keep
   device verification separate from the host implementation claim.

## Speech recognition

1. Start with Moonshine Voice `0.1.2`, English Small Streaming architecture `4`; Moonshine's helper
   defaults to the much larger Medium model, so the architecture must be explicit.
2. Own Android audio capture in this project. `MicTranscriber.stop()` leaves its `AudioRecord`
   capture infrastructure open, which violates the required microphone lifecycle.
3. Keep the Moonshine model loaded between utterances, but create `AudioRecord` only on Start and
   stop it synchronously on Stop.
4. Treat Android's built-in on-device SpeechRecognizer as an empirical A/B candidate, not an
   assumed replacement. Pixel-specific quality and punctuation must be measured.
5. Cleanup remains the product blocker, but a bounded file-fed STT probe may proceed independently
   when explicitly prioritized. The current live Moonshine path remains provisional.
6. Use pinned `parakeet.cpp` 0.5.0 through its C API for the first Parakeet Android comparison.
   Statically link its pinned ggml into `libparakeet.so` so its generic `libggml.so` names cannot
   collide with Moonshine/LEAP libraries in the same APK.
7. Use the 24-clip LibriSpeech subset only as a reproducible read-speech probe. It can reject weak
   candidates but cannot qualify dictation, names/numbers/technical tokens, streaming, endpointing,
   or Stop-to-final latency.
8. Advance Parakeet TDT/CTC 110M Q4_K as the provisional deployment candidate and retain F16 as the
   non-quantized quality reference. Q4_K added one `Hidalgo`/`Hadalgo` substitution but reduced
   clean latency, model bytes, CPU time, measured energy, and memory materially. Reopen this choice
   if the dictation corpus finds systematic protected-token regression.
9. Treat Perfetto power rails plus per-process CPU time as the energy evidence. The USB-connected
   battery current/charge counter is charger-confounded; hardware rails are downstream of the
   battery. The present Parakeet build is CPU-only, and negligible GPU rail energy is not a GPU
   acceleration claim.
10. Use pinned MLX-Audio 0.4.6 and Qwen3-TTS 1.7B CustomVoice 8-bit with built-in voice Ryan as the
    first Mac-local synthetic fixture generator. Feed only each evaluation record's `spoken`
    field to TTS; never expose simulated STT `raw`, cleanup `expected`, prompts, model results,
    VoiceInk material, or blind-v2 to the generator. Retain hashed 24 kHz masters, derive strict
    16 kHz mono PCM16 files for the existing Pixel harness, and keep caches/audio ignored. Treat
    this as deterministic plumbing and lexical-regression evidence only: a clean single synthetic
    voice cannot qualify real dictation, and technical/Unicode/correction clips require listening
    review.
11. Use `nvidia/parakeet_realtime_eou_120m-v1` through pinned `parakeet.cpp` 0.5.0 for the ordinary
    live path because the offline 110M artifact cannot reduce Stop latency through cache-aware
    incremental inference. Feed captured 16 kHz chunks while recording, display only newly
    finalized raw text, keep explicit Start/Stop, stop `AudioRecord` synchronously, and flush only
    the remaining stream tail after Stop. EOU events are preferred cleanup boundaries, not
    automatic Stop or cleanup triggers. Pin the 129,133,984-byte Q4_K GGUF at SHA-256
    `ac9109d0e422bd8aafa899c0f58e1938f4a2846838797a29c04f6a8729033c3c`. This supersedes decision
    8 only for the ordinary live integration artifact; the unmeasured Realtime EOU Q4 quantization
    remains provisional until direct Pixel dictation quality and performance qualification.

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
    for high-concurrency throughput. Deterministic sharding does not imply batch-invariant model
    output: the v0.8.5 publisher sweep varied by up to 12 exact rows and changed 110–124 outputs
    relative to sequential inference. Compare checkpoints only within the same fixed backend and
    concurrency, repeat borderline results, and treat a future batch-invariant vLLM upgrade as a
    new performance/correctness profile.
32. Reject the one-epoch Disfl-QA-only and Nyra-only Qwen3-0.6B adapters as deployment candidates.
    Disfl-QA is strong only on its own publisher distribution and has 23 substantive raw failures
    on the retired diagnostics; Nyra has weaker own-source exactness, zero of ten exact explicit
    corrections, and 18 substantive raw failures. Guardrail fallback cannot rescue either raw
    model. Keep their adapters, checkpoints, vLLM results, review queues, and hashes under `/data`
    as experimental evidence.
33. Proceed with the predeclared fixed-recipe combined direct-source adapter. This is justified by
    measured source specialization: every standalone model transfers poorly to at least one other
    publisher split, and none passes raw semantic safety. Keep Qwen3-0.6B, one epoch, rank-16 BF16
    LoRA, effective batch 32, seed 23, learning rate 2e-4, and the 2,112-token no-truncation policy
    unchanged so the result remains a dataset comparison. Evaluate all source splits and retired
    diagnostics with the fixed vLLM profile; never use blind-v2 for this exploratory decision.
34. Supersede the just-started one-epoch combined run with a separately named three-epoch combined
    learning-curve run at the user's request. Preserve the partial run and its explicit
    `KeyboardInterrupt` evidence. Hold the data, model, LoRA, optimizer, batch, seed, and sequence
    policy fixed; change only epochs, total expected steps, checkpoint/evaluation cadence, and
    retention. Save at the exact end of each epoch (steps 4,599, 9,198, and 13,797), then compare
    all three checkpoints with the same fixed vLLM profile and raw semantic-safety gate. This
    intentionally studies epoch sufficiency and must be reported as a recipe follow-up rather than
    an unchanged one-epoch dataset-comparison row. Never use blind-v2 for epoch selection.
35. Reject every combined Qwen3-0.6B checkpoint for deployment and retain epoch 2 at step 9,198 as
    the experimental baseline only. Epoch 2 has the lowest validation loss (0.08544), best
    source-macro publisher exactness (68.59%), and best retired exactness (52/69), but exhaustive
    raw review still finds nine substantive semantic-policy failures. Epoch 1 has eight failures;
    epoch 3 regresses to fourteen alongside worse validation loss, retired exactness, anchors, and
    no-op behavior. Do not train a fourth epoch. Prioritize leakage-safe safety curation and source
    balancing, then run a separately named Qwen3.5-0.8B rank-16 LoRA one/two-epoch comparison.
    Guardrails cannot qualify any failed raw checkpoint, and blind-v2 remains sealed.
36. Reject the public Sotto LFM2.5-350M production checkpoint at revision
    `6df6f019170b8b55333c047b901886a51750a965` for deployment conversion. Its native-prompt BF16
    screen is promising on basic cleanup and never answers dictated content. Keep 42/69 strict
    exact for immutable comparison, but use the user's ordinary-conversation calibration of 59/69
    acceptable for product iteration. The ten relevant failures are seven retained superseded
    corrections, two retained repetitions, and one statement changed into a question. The other
    strict mismatches—including the malformed Gradle command—are outside this experiment's gate.
37. Make the two-stage LFM correction-repair study the next training work, superseding the planned
    immediate Qwen3.5 follow-up. First continue the pinned public Sotto checkpoint with
    full-parameter SFT for two epochs at `2e-6` on a shuffled natural
    Sotto/Disfl-QA/DISCO-English/Nyra mixture. Use every eligible row once per epoch without
    replaying the smaller sources. After preserving and evaluating that arm, train the
    same ordered mixture from a pinned `LFM2.5-350M-Base` for three epochs at `3e-5`. Use the
    publisher-disclosed microbatch 1, accumulation 8, cosine/50-step warmup, AdamW beta2 0.95,
    weight decay 0.01, BF16+TF32, packed 4,096 context, a generated-and-recorded run seed, and the
    native prompt where applicable. Do not hardcode or gate the campaign on seed 42.
    Do not claim exact reproduction of the unpublished GRPO/refinement/soup lineage, and never use
    the committed diagnostics or blind-v2 as training or checkpoint-selection data.
38. For packed LFM2.5 training, reset `position_ids` at every example boundary and omit the ordinary
    2-D attention mask so Transformers constructs packed causal isolation. Also pass per-token
    `seq_idx` because LFM's short-convolution layers otherwise carry recurrent state across packed
    examples. Keep microbatch one, append EOS, mask native-prompt tokens from loss, never split or
    silently truncate an example, and verify these invariants before any evidence-bearing run.
    Store Hugging Face dataset snapshots in the machine-wide `HF_HOME` hub cache so other projects
    resolve them normally; keep non-HF DISCO at its pinned external artifact path.
39. Do not enforce the earlier proposed 55/25/10/10 LFM sampling weights. The Qwen natural-combined
    experiment was 92.1% Sotto, 4.9% Disfl-QA, and 3.0% Nyra, yet at epoch 2 it reached 769/1,000
    Disfl-QA and 147/250 Nyra versus 765/1,000 and 150/250 for the corresponding one-epoch
    source-specific adapters. Those small deltas are within the practical evaluation-variance
    boundary and do not justify replaying the small datasets roughly five times per epoch. Use a
    globally shuffled single pass over all eligible Sotto, Disfl-QA, DISCO, and Nyra rows instead.
40. Permit a diagnostic joined Android build before cleanup qualification, at the user's explicit
    request, so integration can progress while the correction-repair model trains. Use the selected
    Parakeet 110M Q4_K artifact for project-owned microphone capture and offline final inference
    after Stop. Use a reproducibly converted, hash-pinned public Sotto LFM2.5-350M Q4_K_M only as a
    replaceable cleanup placeholder. Preserve raw STT, complete raw model output, guarded output,
    and per-stage/end-to-end timing. This exception does not reverse Sotto's no-go result, weaken
    the raw semantic-safety gate, or make a guardrail fallback a passing deployment result.
41. Reduce cleanup-model workload with a deterministic pre-model pass limited to standalone `um`,
    `uh`, and `erm`. Preserve the original transcript and expose the exact post-filter model input.
    Do not remove ambiguous discourse or uncertainty terms such as `like`, `well`, `you know`, or
    `hmm`; preserve uppercase acronyms, likely title-cased names without filler punctuation,
    quoted text, hyphenated words, paths, identifiers, and paragraph structure. Apply semantic
    guardrails to Sotto relative to the deterministic model input, and return that visible input on
    fallback. This mechanical removal is product behavior, not evidence that failed raw model
    output is safe.
42. Replace the active technical synthetic dictation cases with the 20-case
    `stt_personal_conversation_tts_cases_v2.jsonl` suite. Product-facing synthetic regression now
    represents personal messages, journals, lists, ordinary names/numbers, uncertainty,
    repetition, formatting directives, and natural self-corrections. Git/URL/checksum/CLI/path/TLS
    and version stress examples remain outside this active workload; their earlier report is
    historical only. Treat personal v2 and its outputs as evaluation-only and never use them for
    training or demonstrations. Use direct WAV/MP3 → Parakeet → Sotto on the debug Activity as the
    primary fast synthetic pipeline regression, while keeping microphone playback as a separate
    acoustic/lifecycle check. Revise Android and host guardrails away from literal surface-token
    protection where equivalence is provable: permit bounded sentence-initial discourse deletion,
    explicit self-correction replacement, identical-value spoken-number rendering, and consumed
    explicit list/paragraph directives. Continue to fail closed on changed facts, names, numeric
    values, negation, uncertainty, unsupported additions, and answered content. Guardrail fallback
    remains containment and cannot qualify raw model output.
43. Supersede personal-conversation v2 with v3 without rewriting the recorded v2 evidence. Remove
    phone-number dictation from the active suite. Add four ordinary 3–5 sentence message/journal
    cases so cleanup quality and latency are measured at 14.88–25.84 seconds of synthetic speech,
    while retaining a short/medium mix. Commit a separate scorer-compatible direct-text v3 corpus
    for the A6000 checkpoint matrix. Evaluate the public start and every saved correction-repair
    epoch on that fixed corpus with exact checkpoint hashes, raw-output review, and per-long-case
    latency. V3 is evaluation-only and may inform checkpoint comparison as a declared regression,
    but its text, targets, outputs, errors, and phrasings must never enter training, prompting,
    retrieval, preference construction, or repair generation. Create v4 for future product changes.
44. Do not require a clean, committed, or pushed repository before training. Record the current Git
    commit and dirty paths plus SHA-256 hashes of the exact trainer, training config, data config,
    mixture manifest, and train/dev streams used by each run. These byte identities, immutable
    artifact directories, logs, and checkpoints are the reproducibility boundary; Git credentials
    and repository cleanliness are operationally unrelated to whether a GPU run may launch.
45. Delete heavyweight checkpoints and final-model copies produced only by completed mechanical
    smoke tests after saved-checkpoint reload/inference is proven. Retain their compact status,
    metrics, telemetry, manifests, hashes, and failure evidence. Track disk use before and after;
    preserve evidence-bearing full-run epoch checkpoints until evaluation and selection finish.
46. Keep uncertainty-word deletion visible in strict preservation metrics and review evidence, but
    per user calibration do not make the Experiment A `heldout-036` removal of “probably” a product
    go/no-go failure. This does not weaken the general requirement to record raw output faithfully.
47. Run a separately named four-epoch public-checkpoint refinement learning curve after the
    two-epoch run remained net-positive on every publisher source. Start again from the pinned
    public checkpoint with the same natural mixture and all existing `2e-6` optimizer/packing
    settings, but span one cosine schedule across four epochs and retain all four checkpoints.
    Do not mislabel this as a resume of the completed two-epoch schedule, which already reached
    zero learning rate.
48. Select epoch 4 of the four-epoch public-checkpoint learning curve as the research comparison
    checkpoint, not as a deployment candidate. It has the best source-dev exact result
    (4,889/8,519) and lowest dev loss (0.13746), but two source-dev examples repeat through the
    900-token generation cap. Do not run epoch 5 because epoch 4 adds only six exact matches over
    epoch 3 while loss is effectively flat. Proceed to the predeclared clean-base Experiment B.
49. Select clean-base Experiment B epoch 1 (`checkpoint-271`) as the final Sotto LFM campaign
    research checkpoint, but do not qualify it for deployment. It reaches 5,477/8,519 source exact,
    51/69 retired exact, and 155/163 protected anchors, outperforming selected Experiment A epoch 4
    by 588 source matches, five retired matches, eleven anchors, and one fewer cap hit. Do not select
    clean-base epoch 3 solely for its 5,796 source exact matches: it regresses to 46/69 retired exact,
    149/163 anchors, and three additional guardrail flags versus epoch 1. Epoch 1 still has a capped
    repetition loop and substantive raw-output intent, command, identifier, name, and structured
    payload failures. Further work requires a separately reviewed targeted repair experiment, not
    automatic extra epochs or guardrail-based qualification.
50. Do not replace the public Android Sotto placeholder after the personal-v3 checkpoint matrix.
    Public start leads the revised ordinary-dictation workload at 11/20 exact and 53/61 literal
    anchors; the best fine-tuned checkpoint on v3 is B epoch 2 at 8/20 and 50/61, while the prior
    campaign-selected B epoch 1 reaches 7/20 and 46/61. Keep B epoch 1's earlier designation scoped
    to the pre-v3 campaign criteria rather than pretending the rankings agree. All A epochs make an
    unsupported currency-unit substitution; B avoids that substitution but retains required
    corrections and formatting directives. Treat the observed guardrail misses and false rejection
    as defects to repair against new regression coverage, not permission to tune on v3 and rescore
    it as unseen evidence.
51. Supersede strict exactness as the primary personal-workload ranking metric with version 1 of
    `docs/evaluation/PERSONAL_CLEANUP_ACCEPTANCE.md`. Report user-calibrated semantic acceptability
    first and strict exactness/anchors as secondary diagnostics. Accept harmless punctuation,
    number-surface, conservative wording, and collapsed duplicated-intensifier differences. Still
    reject retained corrections, changed facts/names/values/units/temporal tense/negation/
    uncertainty, answered content, invention/deletion, and unrealized explicit formatting
    directives. Under this default, all B epochs reach 15/20 and lead public-HF/A at 14/20, but no
    local checkpoint is deployment-qualified or authorized to replace the public placeholder.
52. Use clean-base B epoch 2 as the local side of the user-authorized experimental Pixel
    comparison against hosted `gpt-5.6-luna`. This follows the default relaxed personal-v3 ranking
    and its strict/anchor tie-breaker, without changing the deployment decision. Keep the weights
    outside Git on `dante` at
    `/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty/checkpoint-542`; the Pixel
    build machine may copy them directly from that host.
53. Reject B epoch 2 as a deployment cleanup model after its Pixel Q4_K_M measurement. Its primary
    direct score remains 15/20 acceptable with only 1/3 corrections and 0/3 formatting directives;
    raw semantic failures remain after quantization. Keep its new direct and Parakeet-fed Pixel
    measurements as runtime evidence, but do not let 481 ms median direct latency, 2.69 J/call, or
    guardrail fallback override raw-model quality. Report cloud power as unavailable rather than
    estimating it from Pixel rails.
54. At the user's explicit 2026-08-19 direction, promote B epoch 2 Q4_K_M from a benchmark override
    to the ordinary app's provisional local integration default. This supersedes decisions 51–53
    only as to the integration artifact identity; it does not reverse the deployment rejection or
    weaken the raw semantic-safety gate. Pin the 229,310,336-byte artifact at SHA-256
    `02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0`, preserve raw and guarded
    output in the UI, retain the debug artifact override and `CleanupEngine` boundary, and make a
    later swap only after fresh evidence and an explicit selection.
55. Keep the reverse-inventoried FluidVoice/Fluid-1 artifacts as an owner-local Mac reference only.
    Do not commit, redistribute, bundle, convert for Android, fine-tune, use as a teacher, or feed
    project evaluation cases into Fluid-1 without explicit written permission consistent with the
    located model card. Its roughly 4.6B architecture and 3.19 GiB GGUF / approximately 3.77 GB MLX
    package are not Pixel deployment candidates. Record “Trained on 100K+ dictation data points”
    only as a vendor-reported scale heuristic: it supplies no verifiable dataset provenance,
    pairing, licensing, diversity, split, or quality evidence, and does not override this project's
    reviewed data contract or safety gates.
56. Keep the 2026-08-21 S1-mini v1 screen performance-only. Use the exact publisher system prompt,
    trained control line, `enable_thinking=false`, greedy decoding, and input-relative output cap;
    do not silently substitute F16 GGUF for the actual BF16 reference. On the 69-case seed +
    held-out screen, preserve Q4_K_M's 1.87× same-runtime median-total speedup over F16 and 19.48×
    cross-runtime speedup over Transformers BF16 as host evidence, while treating their memory
    footprints as non-comparable runtime allocations. BF16/F16 agree on 207/207 requests and Q4
    agrees on 201/207, but no difference is an accuracy loss or gain until semantic review. Make no
    Android selection or BF16 Pixel feasibility claim from this Mac-only pass.
57. Do not replace Sotto B with S1-mini v1 after the exact-contract Pixel screen. S1 Q4_K_M
    improves default personal-v3 raw acceptability from 15/20 to 17/20, but it retains one
    superseded recipient correction and ignores two explicit list-formatting directives. On the
    Pixel 7 CPU path it needs about 1.576 seconds median traced direct cleanup, 1,293,620 KiB peak
    PSS, and 6.493 J of compute energy per call, and sustained runs reach thermal status 1. Keep it
    as research evidence only. Any later accelerated-runtime comparison must preserve the exact
    system prompt, control line, empty-thinking prefix, greedy decoding, and per-input token cap,
    then re-establish prompt-token and raw-output parity before comparing performance. BF16 Pixel
    feasibility and the full retired-diagnostic semantic gate remain open.
58. Supersede decision 57 only for the ordinary integration identity at explicit user direction:
    use S1-mini by Superwhisper Q4_K_M as the preferred on-device cleanup model. The fixed
    `[Structure: prose]` control makes the two transcript-level list directives configuration
    conflicts rather than Pixel deployment failures, giving 19/20 user-acceptable personal-v3 raw
    outputs; the retained superseded recipient remains a genuine failure. Pin the official
    484,219,808-byte artifact at SHA-256
    `3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634` and preserve the exact
    system prompt, semi-formal/prose/general control, embedded Qwen3 template,
    `enableThinking=false`, greedy decoding, and `ceil(1.3 × raw tokens + 32)` cap. Mac/Pixel raw
    token counts and caps agree 69/69 and raw text agrees 66/69, so no silent option-loss bug is
    present; bounded backend output differences still require raw semantic review and fallback.
    This preference accepts measured Pixel latency/memory/thermal cost and does not qualify raw S1
    for deployment or weaken the retired-diagnostic semantic-safety gate.
59. Supersede the runtime-enforcement portions of earlier cleanup decisions for this personal-use
    app. The owner accepts responsibility for reviewing and editing inserted text. Use every
    sanitized, non-empty S1-mini generation that did not reach its output-token cap; fall back to
    the raw transcript only for blank or capped output. Do not reject runtime output for lexical,
    semantic, length, name, number, negation, uncertainty, correction, intent, question, command,
    or formatting changes. Preserve the stricter host guardrails and prior semantic evaluations as
    historical/research diagnostics only; they do not gate personal-use insertion. Keep the exact
    S1-mini publisher prompt, control, template, thinking, greedy-decoding, and output-cap contract.
60. Apply S1-mini only to a completed STT transcript, never to live partials. Follow the v1 model
    card's long-input guidance by counting raw tokens with the loaded S1 tokenizer and keeping each
    pass at or below roughly 1,000 tokens. Greedily prefer Parakeet EOU offsets and written sentence
    endings, fall back to whitespace only for an overlong unpunctuated span, run passes sequentially
    with the exact trained prompt/template/greedy/per-input-cap contract, and rejoin them in source
    order. Retain the personal-use blank/capped fallback policy independently for each pass.
61. Optimize S1-mini Pixel inference in three controlled stages: supported LEAP settings with the
    exact selected Q4_K_M; a collision-isolated direct llama.cpp Android comparison using the same
    GGUF; and an exact-checkpoint BF16-to-LiteRT-LM blockwise-32 INT4 conversion measured on Pixel
    CPU/GPU. Do not test lower-bit GGUF, block-128, or channelwise conversion variants. Preserve the
    exact tokenizer, prompt/control/template, empty thinking prefix, greedy decoding, per-input cap,
    chunking, raw-output evidence, and personal-use insertion policy. Require host contract and raw
    semantic-difference review before device speed can influence selection. Pixel 7 Tensor G2 NPU
    is outside the plan without official reproducible support. Use a separate direct llama.cpp
    benchmark module first because LEAP already packages generic llama/ggml libraries and Parakeet
    owns another statically isolated ggml; never introduce colliding native SONAMEs or symbols.

## Hosted API benchmark

1. Keep the GPT-5.4 hosted-API comparison as a separate optional personal-use campaign. It does
   not replace, tune, select, or supply examples to the local cleanup-model training plan.
2. The user authorizes sending both committed cleanup corpora to the OpenAI API for this campaign.
   Keep them evaluation-only, never send blind-v2, and never reuse API inputs or outputs for local
   training, demonstrations, retrieval, prompt tuning, or preference pairs.
3. Use dated GPT-5.4 snapshots, standard/default service tier, streaming, raw-output scoring,
   `reasoning_effort=none`, and the Android-equivalent output cap through
   `max_completion_tokens`. Measure sequential product latency before a separately labeled
   concurrency/throughput profile.
4. Stage the campaign behind a four-case-per-model seed pilot and user dashboard confirmation of
   complimentary shared-data usage. A later personal deployment uses a separate non-sharing key;
   never treat the shared-data test key as the privacy configuration for real transcripts.
5. Reject both hosted snapshots for automatic cleanup on current raw-output evidence. Mini's
   systematic correction retention is disqualifying; GPT-5.4's `Approved` response to dictated
   instruction text is a direct must-not-answer failure. GPT-5.4 is faster than the product's
   likely one-second cleanup budget and materially better than mini on publisher dev, but latency
   and low per-call price cannot override safety or its large exactness gap to task-trained local
   checkpoints. Do not spend more hosted quota on prompt/concurrency tuning from these evaluation
   cases, and never use blind-v2 in this campaign.
6. Treat GPT-5.6 Luna as the leading hosted candidate on active personal v3, while keeping its
   evidence scoped to that suite. Under the default personal cleanup acceptance policy, Luna and
   GPT-5.4 are both 20/20 user-acceptable; mini is 18/20
   because it retains two superseded corrections. Prefer Luna on this workload because it is
   faster and cheaper. Do not imply that Luna passed the retired safety or HF/source-dev corpora,
   which were deliberately excluded from the rerun.
7. Keep Luna as the leading optional hosted candidate after the Pixel/Parakeet comparison, but do
   not qualify it for automatic cleanup. It reaches 20/20 acceptable direct and 17/20 acceptable
   joined, applies all three corrections and formats, and materially beats local Sotto B. However,
   on joined case 012 it reinterprets a protected Parakeet token as a different grammatical
   subject. Guardrail fallback does not rescue the raw failure. Any hosted product experiment must
   remain explicit and privacy-aware, use a non-sharing personal key, preserve the fully local path,
   and measure a real Pixel network client's latency/energy rather than treating the Mac-origin
   estimate as shipping evidence.

## Android/toolchain

1. Pixel-7-first, `arm64-v8a`, minSdk 31.
2. Use Views/XML to minimize Activity and future IME integration overhead.
3. Keep AGP 8.13.2, Gradle 8.13, Kotlin 2.3.20, API 36, and JDK 17 while those are the verified
   Liquid/Moonshine-compatible versions.
