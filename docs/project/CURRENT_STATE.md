# Current state

Last updated: 2026-08-22

## Repository

- Branch: `main`
- Remote: `https://github.com/shivakanthsujit/android_stt.git`
- Last verified milestone: first daily-driver QoL slice installed on Pixel with bounded transcript
  surfaces, live tail-follow, five-entry fail-closed undo, and cursor-aware insertion spacing;
  owner-run live speech/scroll/undo verification remains open
- Workspace: `/Users/ssujit/Documents/projects/android_stt`
- Current phase: minimal voice IME device verification and daily-driver hardening
- Completed milestones: 0 (toolchain), 1 (Moonshine smoke test), 2 (cleanup harness and Liquid
  no-go evaluation), 3 (cross-family generic-model quality screen)
- Active product milestone: minimal voice-only `InputMethodService`
- Parallel model milestone: 4 (task-specific cleanup qualification/training remains open)
- Partially completed milestone: 5 (standard-corpus STT probe plus streaming microphone
  integration; human dictation/streaming qualification remains)
- Completed integration milestone: the joined path has a pinned, swappable personal-use default
  and supplies the IME under the owner's permissive cleanup insertion policy

## Working functionality

- Kotlin/View-based joined integration Activity on a physical Pixel 7.
- Host-built voice-only `InputMethodService` with Android input-method metadata, enable/select
  setup controls, explicit Start/Stop, Cancel, a five-entry conservative Undo history,
  next-keyboard switch, transcript-free timing logs, and a bounded, independently scrollable live
  raw-partial surface. It is installed and enabled on the Pixel, but the updated scrolling and
  streaming speech path still need an owner-run interactive check.
- Application-scoped `DictationPipelineCoordinator` shares one Parakeet and S1-mini engine pair
  between the Activity and IME; destroying the Activity no longer unloads models needed by the IME.
- IME editor policy disables dictation for password fields, editors requesting no personalized
  learning, and non-text destinations. A result is committed only to the same editor identity that
  started the utterance. Consecutive commits receive a cursor-aware boundary space only when
  needed, and Undo deletes only an exact immediate suffix—including any inserted separator—in that
  editor.
- Moonshine Voice `0.1.2`, English Small Streaming architecture `4`.
- Model download, persistent no-backup cache, progress display, and offline cache reuse.
- Raw provisional/final transcript display and monotonic latency metrics.
- Manual transcript scrolling affects only the viewport: recording and streaming STT continue, and
  live tail-follow resumes after returning to the bottom. The keyboard currently has textual
  `Listening locally…` state, but a stronger persistent recording indicator remains the first QoL
  task for the next session.
- Debug-only, microphone-free STT benchmark Activity that accepts checksum-verified 16 kHz PCM16
  WAVs over ADB and records raw hypotheses, WER inputs, repeat latency, process CPU time, PSS,
  native heap, and thermal status.
- Debug-only joined benchmark Activity that accepts a generated corpus or one host-canonicalized
  WAV/MP3, loads Parakeet and S1-mini once, never opens the microphone, and records raw STT, exact
  model input/output, selected output, fallback reason, and per-stage/joined latency.
- Mac-local, locked Qwen3-TTS/MLX-Audio fixture pipeline that converts literal text or bounded
  regression suites into resumable, hash-addressed 24 kHz masters and Pixel-compatible 16 kHz
  mono PCM16 WAV corpora without putting model weights or generated audio in Git.
- Pinned Android ARM64 `parakeet.cpp` 0.5.0 JNI/C API integration. Historical/dedicated STT evidence
  retains explicit offline TDT/CTC 110M artifact identities; the ordinary live and no-override
  joined paths now use the 120M Realtime EOU Q4_K artifact, with live capture using its cache-aware
  streaming API. Its ggml dependency is statically isolated from Moonshine/LEAP's packaged ggml.
- Optional Perfetto power mode that attributes Pixel CPU/GPU/memory rail energy to measured model
  calls using app trace slices.
- ARM64-only joined/IME debug APK; current host-verified and installed QoL build is 88,046,641
  bytes with SHA-256
  `cd2227b372a2f4028a6ae725ad28d566c130f7424b4241e3057f2290cb57035d`.
- Microphone permission is requested from the Activity.
- The model stays loaded between utterances.
- Android `AudioRecord` is created and started only after **Start Dictation**.
- **Stop Dictation** synchronously stops active microphone capture before final processing.
- The selected live Parakeet model consumes 16 kHz microphone chunks during recording, carries
  encoder/decoder state, and displays newly finalized raw transcript text in both the Activity and
  IME. Stop drains captured audio and flushes only the remaining stream tail. Explicit Stop remains
  authoritative; EOU events do not automatically end capture.
- Liquid LEAP `0.10.9` cleanup-only benchmark with model download progress, persistent cache reuse,
  load/unload, minimal output-validity fallback, and monotonic TTFT/total-generation metrics.
- Editable direct-text cleanup UI plus a 24-case, multi-prompt batch runner that exports JSONL for
  deterministic host-side scoring without involving the microphone or Moonshine.
- Sideloaded LEAP runtime defaults to the official 484,219,808-byte S1-mini by Superwhisper
  Q4_K_M GGUF with SHA-256
  `3b41ebe2502cbd03e811d5d16b022f5ab551eda58d62597d152f89535003c634`. The exact publisher
  system prompt, semi-formal/prose/general control line, embedded Qwen3 template,
  `enableThinking=false`, temperature-zero greedy decoding, and
  `ceil(1.3 × raw transcript tokens + 32)` cap are fixed in the production engine. The cleanup
  interface remains swappable and Sotto is retained only as a historical/debug engine.
- Joined Parakeet → S1-mini execution after every non-empty final transcript. The UI preserves raw
  STT, complete raw model output, selected output, STT tail, cleanup timing, and end-to-end tail.
- Streaming partials are display-only and never reach S1-mini. After Stop produces the complete
  transcript, the production engine uses S1-mini's tokenizer to pack passes at no more than 1,000
  raw tokens, preferring Parakeet EOU and punctuation/sentence boundaries and using whitespace only
  for an overlong unpunctuated span. Passes preserve the exact prompt/template/decoding contract,
  run sequentially, and are rejoined in source order.
- The active synthetic product regression is now the 20-case personal-conversation v3 suite:
  messages, journal entries, lists, ordinary names/numbers, uncertainty, repetition, explicit
  formatting, natural corrections, and four 3–5 sentence latency cases. Phone-number dictation and
  technical v1 cases are historical/excluded from the active workload.
- The preferred S1 path sends the trimmed Parakeet transcript directly under the publisher control;
  it does not insert the older Sotto-specific deterministic filler preprocessor. Result metadata
  preserves the original transcript, exact model input, complete raw model output, selected output,
  and fallback reason.
- The personal-use Android runtime accepts every sanitized S1-mini generation that is non-empty and
  did not reach its output-token cap. It does not reject lexical, semantic, length, name, number,
  negation, uncertainty, correction, intent, question, command, or formatting changes. Historical
  host guardrails remain research diagnostics and do not gate insertion.
- LFM2.5-230M, 350M, and 1.2B-Instruct `Q4_K_M` were exercised on-device; their raw static-corpus
  results and summaries are preserved under `docs/evaluation/`. All three are cleanup no-go results.
- A deterministic baseline plus Granite 350M, Qwen3 0.6B, Gemma 270M, Qwen3.5 0.8B, and Gemma 1B
  were screened on a fresh 45-case held-out set through llama.cpp on the host. None passed the
  semantic safety/self-correction gate, so no new runtime or model was added to the Android app.
- The runtime-neutral runner now applies a parity-tested port of the Android lexical/intent
  guardrails and emits scorer-compatible JSONL with raw output, guarded selection, TTFT, and total
  latency.
- Cleanup is still the product bottleneck. Correction-repair training and the personal-v3
  checkpoint matrix are complete. Under the default relaxed semantic calibration, clean-base B
  leads the local family at 15/20 acceptable versus 14/20 for public Sotto and A, but it still
  misses required corrections/formatting and fails broader safety. At explicit user direction,
  B epoch 2 is the provisional local integration default so product work can continue. This is not
  a deployment qualification claim.
- S1-mini v1 by Superwhisper now has a reproducible Mac-local performance screen under the exact
  publisher prompt, control line, empty-thinking prefix, greedy decoding, and input-relative cap.
  Across the 69-case seed + held-out project screen, Q4_K_M llama.cpp reaches 110.2 ms median total
  and 141.17 tok/s native decode, versus 206.0 ms and 64.85 tok/s for the same-runtime F16 control.
  The actual BF16 safetensors weights reach 2,147.6 ms median through the documented Transformers
  CPU path. BF16/F16 agree on all 207 requests; Q4 agrees on 201/207. Across project evals plus
  personal-v3, all variants are stable on 89/89 cases and Q4 agreement is 249/267 requests. This is
  performance/agreement evidence only: semantic scoring and all Pixel measurements remain open.
  Full evidence: `docs/evaluation/results/2026-08-21-s1-mini-v1-local-performance.md`.
- S1-mini v1 Q4_K_M now has a full exact-contract Pixel 7 screen through LEAP 0.10.9. Mac and Pixel
  raw-token counts/output caps match 69/69; raw Q4 text matches 66/69, with three bounded backend
  decoder differences and no prompt/template/options drift. Under the user's control-aware
  calibration, personal-v3 raw output is 19/20 acceptable: the fixed `Structure: prose` setting
  resolves the two transcript-level list conflicts, while one retained superseded recipient remains
  a genuine failure. The thermal-clean traced run reaches 975.5 ms median TTFT, 1,576 ms median
  total, 1,293,620 KiB peak PSS, and 6.493 J/call; a matching untraced run crosses to thermal status
  1 under sustained use. At explicit user direction S1 replaces Sotto B as the preferred ordinary
  integration default. A later explicit personal-use policy change removed semantic runtime
  rejection while retaining empty/token-cap fallback. Full evidence:
  `docs/evaluation/results/2026-08-21-s1-mini-v1-pixel.md`.
- The owner approved an ordered S1 inference-optimization program without lower-bit GGUF variants:
  first tune supported LEAP settings with the exact Q4_K_M, then compare a pinned direct
  llama.cpp Android build with the same GGUF, then convert the exact BF16 S1 checkpoint to a
  metadata-verified blockwise-32 INT4 LiteRT-LM artifact for Pixel CPU/GPU. Read
  `docs/research/S1_MINI_PIXEL_INFERENCE_OPTIMIZATION_PLAN_2026-08-22.md`. Stage 1 is complete.
  The selected production LEAP configuration is explicit two CPU threads, 2,560 context, cache
  off, and mmap on; the exact Q4_K_M and publisher contract are unchanged. In matched traces it
  reduces median/p90 total latency by 17.88%/19.32%, peak PSS by 10.50%, native heap by 14.08%, and
  inference compute energy by 10.09%. Raw output matches 60/60 with zero repeat instability. It
  uses 55.47% more median process CPU and 13.76% more average inference compute power, but finishes
  sooner; thermal status 1 is delayed rather than eliminated. The 32/64 MiB cache arms reused zero
  tokens and regressed latency, CPU, memory, and thermal behavior. Full evidence is in
  `docs/evaluation/results/2026-08-22-s1-mini-leap-pixel-tuning.md`. Stage 2's isolated direct
  llama.cpp comparison is complete at pinned commit `ece963f41` / build 10450 with
  NDK `28.0.13004108`, CMake `3.31.6`, exact prompt/token/cap evidence, a transcript-only runner,
  and a reproducible 18,701,319-byte Release APK at SHA-256
  `8931caef1a33acc84c9eb173d4d09d986f71ea0f6816716e3a3e93ce05b1bfad`.
  Pixel selected `android_armv8.2_2`; the natural cap path passed 6/6 measured calls, and the
  bounded generation-thread, batch-thread, internal token-buffer, and flash-attention matrix ran
  strictly one cleanup request at a time. A stress corpus proved 36/36 matched raw-output parity
  for the baseline but overweighted 126–164-token inputs. The corrected user-shaped corpus has
  median 22 raw tokens and matches tuned LEAP 30/30 on prompt counts, caps, and raw outputs. Direct
  was 9.3% slower at median total latency, 7.2% slower at p90, used 8.8% more median process CPU,
  and reached thermal 1 while LEAP stayed at 0; its median PSS was 1.8% lower. Direct CPU is a no-go
  and LEAP remains production. Full device evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-direct-llamacpp-pixel.md`; host/build evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-direct-llamacpp-host-readiness.md`. Stage 3's exact
  BF16 conversion is now complete. Dante produced a 436,596,864-byte 4,096-context LiteRT-LM
  bundle at SHA-256 `8748cd01c614db17454fc02b87ef3fc46558f8c5e796dbb85a6f5be6eb01a403`
  using `dynamic_wi4b32_afp32`. Inspection proves 1,154/1,154 INT4 tensors use block size 32 with
  FLOAT16 scales, while every KV signature remains FLOAT32. The official bundle inspector confirms
  Qwen3 metadata, the source Jinja template, and stop IDs. An isolated LiteRT-LM JVM 0.16.1 smoke
  now loads the exact bundle on both CPU and Apple M2 GPU/WebGPU, proves the 404-byte rendered
  cleanup prompt exactly, and returns `Hello there` on both arms for the project-authored
  `um hello there` input. The isolated Android 0.16.1 probe is also complete on the frozen English
  user-shaped fixture. CPU was 448.2% slower at median total latency and used 42.4% more median PSS
  than the thermal-clean LEAP reference; GPU was 91.0% slower and used 142.9% more PSS despite
  genuine full-main-model Mali/OpenCL delegation. Both lost all 10 paired latency cases and stayed
  at thermal 0. LiteRT exact raw output matched LEAP only 1/10, mostly due omitted final periods;
  CPU also introduced `water the balcony, herbs`. Stage 3 is a no-go, no smaller-context export or
  power arm is advanced, and tuned LEAP remains production. Evidence:
  `docs/evaluation/results/2026-08-22-s1-mini-litert-conversion.md` and
  `docs/evaluation/results/2026-08-22-s1-mini-litert-pixel.md`.
- The owner-local FluidVoice 1.6.9 pipeline is now inventoried as a Mac-only reference. Its active
  path is Parakeet TDT v2 Core ML → app filler/dictionary preprocessing → Fluid-1 with bundled
  prompt/template → thinking-markup and app formatting/continuous-dictation postprocessing. The
  prior 3,427,878,144-byte Q4_K_M GGUF is preserved in ignored storage at SHA-256
  `38fafbfaab6504b7ad125523f0b993d52112c3cc7e20543f4929e619022bc7d8`; all eight files in the new
  3,583,024,557-byte main MLX model are also preserved and manifest-verified. Its signed 3.77 GB
  total additionally lists a 188,714,557-byte optional MTP drafter that was not downloaded.
  Neither model is an Android candidate or a
  permitted training/teacher source under the located model-card restrictions. FluidVoice's
  “100K+ dictation data points” statement is retained only as an unverified scale heuristic. See
  `docs/research/FLUIDVOICE_LOCAL_PIPELINE_2026-08-19.md`.

## Physical device

- Google Pixel 7 (`panther`), ARM64, adb serial `33040DLH20004E`.
- Cached Moonshine model remains installed on the device.
- F16 and Q4_K offline Parakeet GGUFs plus the generated LibriSpeech probe remain in ignored
  local/device evaluation storage; they are not committed app assets.
- The 129,133,984-byte Realtime EOU 120M Q4_K artifact at SHA-256
  `ac9109d0e422bd8aafa899c0f58e1938f4a2846838797a29c04f6a8729033c3c` and S1-mini Q4_K_M are
  staged in app-private storage with exact hashes verified on the device. The streaming artifact
  loads and creates a native stream session in the installed APK without opening the microphone.
  App-private storage replaces shell-pushed app-scoped external storage on Android 17.
- Final no-override joined run `20260820T182349Z-joined-file` completes 20/20 personal-v3 cases.
  Median STT/cleanup/pipeline totals are 725.0/1,927.5/2,664.5 ms, peak PSS is 1,589,901 KiB, and
  max thermal is 1. Raw and guarded strict/normalized target counts agree at 8/20 and 9/20; the
  only fallback is the genuine retained-recipient correction failure.
- The IME is installed, enabled, and visually verified in the app's safe text editor. After the
  2026-08-22 QoL reinstall, Gboard is the current default and Local Flow remains available through
  the keyboard chooser; the reinstall did not clear its app-private model files.
  With microphone permission denied it correctly shows `Microphone setup required` and does not
  expose a recording action. Temporary permission grant and interactive model-load verification
  are in progress; actual speech commit, cancel, undo, focus switching, and cross-app behavior
  remain open.
- A first consented in-app voice attempt reached Parakeet and S1-mini. S1 produced a non-empty,
  complete cleanup but the installed guardrail falsely classified compact `ten PM` → `10pm` and
  `nine PM` → `9pm` rendering as new lexical content. The superseding personal-use runtime policy
  now accepts that output and every other non-empty, non-capped generation; the updated APK is
  installed with both app-private models preserved and Local Flow still selected as the IME.
- On-device joined smoke: Parakeet model load 270 ms; 22.091-second microphone capture; 1,568 ms
  Stop-to-STT final; Sotto total 456 ms; 2,029 ms Stop-to-cleanup. Sotto deleted protected negation,
  and the guardrail correctly returned the raw STT text. This is useful integration evidence and a
  direct reminder that the placeholder cleanup model remains unqualified.
- Historical technical-v1 acoustic synthetic run under the superseded guardrail: 4/20 strict and
  11/20 normalized STT exact; 934 ms median
  Stop-to-STT final; 565 ms median cleanup total; 1,466 ms median Stop-to-cleanup. Sotto fell back
  on 15/20 cases. Case 014 changed a dictated technical command and passed the guardrail; case 011
  correctly resolved a beta-to-canary correction but was rejected by the guardrail. The 35-second
  long case completed at 3,350 ms STT tail and 5,484 ms end to end. Thermal status remained 0.
- Personal-v3 direct-file joined run: 20/20 completed; Parakeet reached 8/20 strict and 15/20
  normalized exact against spoken references. Public Sotto/guarded output reached 8/20 strict and
  10/20 normalized exact against intended cleanup with three fallbacks, all on retained explicit
  corrections. Median STT/cleanup/joined times were 625/645/1,261 ms. The four long-form cases ran
  from 2,543 to 4,746 ms joined for 14.88–25.84 seconds of audio. This fast regression does not test
  microphone acoustics or lifecycle.
- Pixel `stay_on_while_plugged_in` was restored to its original `0`; airplane mode is disabled.
- The cleanup harness and all three Liquid evaluations are committed in `8dce7ab`.

## Known issues and observations

- Moonshine Small Streaming handled a 59.6-second utterance without ending microphone capture, but
  it produced overly short line segments and several recognition errors.
- On the clean 24-clip read-speech probe, Moonshine scored 3.54% WER, Parakeet F16 1.69%, and
  Parakeet Q4_K 1.85%. Q4_K was the fastest untraced path (0.72 s median, 1.80 s p90), with zero
  output instability across repeats.
- The pinned Qwen3-TTS 1.7B CustomVoice 8-bit pipeline generated 45 retired held-out-v1 cleanup
  regression clips plus 20 project-authored dictation stress clips with the built-in Ryan voice.
  The 65 canonical files total 401.28 seconds and have manifest SHA-256
  `10a06cdece044e4c0383eb5719461fdba3b74cb6638efd9d5c238cf7728964cf`; all WAV/header/hash,
  silence, clipping, offline-cache, and resume checks pass. Audio remains ignored under
  `.cache/stt-eval/`. This clean single-speaker synthetic corpus validates plumbing and lexical
  regressions, not real dictation quality. The 20 project-authored cases have now completed one
  uncontrolled acoustic Pixel integration run; listening review and controlled/human-speaker
  qualification remain pending. Full evidence is in
  `docs/evaluation/results/2026-08-18-parakeet-sotto-tts-acoustic-integration.md`.
- Q4_K's only normalized difference from F16 was `Hidalgo` → `Hadalgo`. In matched power runs it
  used 23.8% less process CPU time, 23.3% less inference compute-rail energy, 8.6% less average
  compute power, and 25.5% less peak PSS. Q4_K is the provisional deployment candidate; F16 is the
  quality reference.
- The current Parakeet build is CPU-only. GPU rail energy was below 0.1% of compute energy for the
  earlier offline model. Cache-aware microphone streaming is now integrated, but the Realtime EOU
  Q4 artifact has no publisher-reported quantized WER and has not yet undergone owner-run live
  partial-responsiveness, Stop-to-final, protected-token, memory, thermal, or power qualification.
- An initial F16 latency run was contaminated by active phone use and excluded. Clean runs start
  with no competing app and thermal status 0. Perfetto affects wall timing, so untraced runs select
  latency while traced runs supply CPU/energy evidence.
- Live Parakeet partials are displayed while recording. Only its whole final transcript is supplied
  to cleanup after Stop.
- Automatic end-of-speech is deliberately not implemented. V1 uses explicit Start/Stop.
- Android's built-in on-device `SpeechRecognizer` is a planned A/B branch after the joined pipeline.
- Liquid LEAP is governed by its own Terms of Use; its model weights have separate LFM licensing.
- LFM2.5-230M passed Android/offline runtime checks but failed cleanup quality: only 3/24 strict
  matches for the safest prompt. It remains a latency baseline, not the selected default.
- LFM2.5-350M performed worse (1/24 exact, 77.0% preservation, meaning-changing negation failure)
  and is rejected.
- LFM2.5-1.2B-Instruct reached 13/24 exact at best but still changed meaning, answered content,
  dropped technical details, and failed all self-corrections. It is rejected for automatic cleanup.
- The cleanup harness has stricter lexical/intent fallback checks, but a safety fallback cannot
  compensate for inadequate raw cleanup quality. The joined UI shows fallback selection for
  diagnosis; no failed model is qualified by that behavior.
- Guardrail fallback now returns the visible deterministic post-filler input rather than restoring
  removed fillers. This is a declared mechanical transformation; Sotto's raw output still must
  pass semantic safety independently.
- Gemma 3 1B was the closest generic candidate at 32/45 raw exact and 94.1% anchor preservation,
  but it retained a superseded command and obeyed two embedded instructions. It is rejected.
- Historical host screens remain Apple M2 measurements. Public Sotto now also has Pixel 7 runtime
  smoke evidence solely to unblock integration work; this does not supersede its failed quality
  decision.
- The original 24 cases are a development/regression set. The 45-case held-out set has now informed
  guardrail fixes, so it is also a regression set rather than a future blind test. Training work
  must create leakage-isolated train/dev data and a new untouched blind v2 evaluation set.
- The first specialized quality probe, VoiceInk Qwen3.5-2B Q4_K_M, is complete and rejected. It
  reached 38/69 raw exact but only 2/10 explicit corrections, retained six superseded edits,
  changed meaning/facts three times, and answered one dictated instruction. Its fine-tune license
  is also undeclared.
- Task-specific data work has a versioned JSONL contract and standard-library validator covering
  provenance/review policy, frozen-corpus overlap, split leakage, anchors, lexical additions, and
  deterministic SHA-256 manifests. No training rows have been generated yet.
- Public candidate sources are now pinned for audit: Sotto transcript cleanup at
  `183cc8fd58532f13fa192980185214de1bcd5acc`, Disfl-QA at
  `1f0c16171c77b3d3408be92c485f11b8998a9189`, and Nyra Disfluency Speech English at
  `723e9e69bfbdc8214a9b8ce8815985e90afcbaa3`. None has been imported or approved yet.
- `TRAINING_MACHINE_HANDOFF.md` is the self-contained entry point for the RTX A6000 session. It
  authorizes building the missing data/training/evaluation pipeline and running the pilot there,
  subject to Gate A, monitoring, artifact, review, and blind-isolation rules.
- RTX Phase 0 hardware/storage checks pass on host `dante`: the user verified NVIDIA-SMI
  550.144.03, CUDA compatibility 12.4, an idle 49,140 MiB RTX A6000, and about 9.6 TiB free under
  the writable `/data/rise/android_stt/` artifact root. The exact CUDA 12.4 environment lock is
  synchronized under `/data/rise/android_stt/env`; the exact package check and BF16 CUDA matmul
  pass. See
  `docs/training/2026-08-17-RTX-A6000-PHASE0.md`.
- The first reproducible data-pipeline checkpoint now contains pinned-source configuration, a
  revision-verifying/hash-recording fetcher, conservative Sotto/Disfl-QA/Nyra import and
  quarantine logic, pre-split family/near-duplicate grouping, exact pilot quota checks, and unit
  tests. The 14-file, 1.1 GiB pinned source snapshot passes identity/byte/SHA verification; the
  real importer dry run passes, no public row is approved, and the durable `/data` import remains
  to be created.
- A text-free profile of all 147,142 mappable pinned rows records 63,990 candidates, 81,325
  quarantined rows, and 1,827 rejected rows without consuming source-native holdouts. Even as an
  optimistic upper bound, public data is short by 326 adversarial-primary rows, 53 paragraph rows,
  402 adversarial cross-cutting rows, and 524 Unicode/multilingual rows for the 5,000/500 pilot.
  The sanitized profile is `docs/evaluation/results/2026-08-17-cleanup-source-profile.json`.
- A deterministic supplemental generator now produces 2,800 pending, non-blind candidates outside
  Git: 720 adversarial-primary, 400 paragraph-primary, and 1,576 Unicode/multilingual cross-cutting
  rows, plus edit-bearing adversarial variants. Its dry run passes the V2 validator for all 2,800
  rows. The quota builder reserves rare cross-cutting supply and satisfies minima during selection;
  no generated or public row is auto-approved.
- Dataset/annotation contract V2 treats explicit bullet/numbered-list, paragraph-break, and
  spoken-punctuation directives as reviewed editor controls while preserving arbitrary commands
  as text. Following product clarification, the 5,000/500 pilot also has dedicated 500/50 strata
  for conservative grammar repair and context-supported ASR repair, retains mixed/crutch,
  high-stakes, protected, and declared lexical-addition candidates for human review, and still
  rejects invented formatting items automatically.
- Do not start LoRA/QLoRA training on this Mac; use it for Android work, authoring/validation, local
  inference screens, and result analysis only.
- The immediate experimental direction is now four direct-source adapters: Sotto, Disfl-QA, Nyra,
  and all three combined. Hold Qwen3-0.6B and a one-epoch LoRA recipe fixed so the experiment
  measures the dataset effect; train Sotto first and evaluate its raw output before launching the
  other three. This fast evidence track is documented in
  `docs/training/DIRECT_SOURCE_EXPERIMENT_PLAN.md` and does not qualify an adapter for deployment.
- A separate direct-source trainer/config now supports Sotto, Disfl-QA, Nyra, and combined
  publisher splits without weakening the reviewed-pilot Gate A path. It verifies source
  revisions/bytes/hashes, nonempty-pair counts, frozen-corpus isolation, exact optimizer steps,
  assistant-only masking, and the no-truncation 2,112-token contract.
- The exact Qwen3-0.6B snapshot is cached and the 32-row/two-step Sotto smoke completed at run
  `direct-sotto-qwen3-0.6b-smoke2-seed23-20260817T121729Z`: step 2, train loss 1.4543, no
  truncation, 10,092,544 trainable LoRA parameters, checkpoint plus final adapter present. Two
  earlier mechanical attempts failed before any optimizer step and led to committed Transformers
  5.14 compatibility fixes for mapped chat-template output and `TrainingArguments`.
- The user explicitly waived the pre-run push gate for local commit `53a5551`. The first managed
  full-run launch exposed a monitor/startup race and exited before run state or optimizer work;
  its directory is preserved. A second clean launch reached the full-corpus no-truncation audit
  and failed before model load because row 75 formats to 1,294 tokens under the fixed 1,024-token
  limit. No optimizer step ran.
- The completed text-free audit found 775/135,503 Sotto train rows and 46/6,921 publisher-validation
  rows above 1,024 tokens, with maxima of 1,838 and 2,050 respectively. The evidence is
  `docs/evaluation/results/2026-08-17-direct-sotto-token-length-audit.json`. Do not truncate, drop,
  or change the fixed sequence policy without an explicit recipe decision and a new longest-row
  memory smoke.
- The authorized 2,112-token limit is within Qwen3-0.6B's pinned 40,960-token context, but the exact
  longest train row OOMs at the original microbatch 8 without checkpointing. Two-step worst-case
  diagnostics pass with either microbatch 4 / accumulation 8 (31.87 GB peak allocated, 13.84 s)
  or microbatch 8 / accumulation 4 plus gradient checkpointing (29.09 GB, 17.76 s); validation
  batch 8 passes at the 2,050-token maximum. The authorized recipe is 2,112 tokens plus microbatch
  4 / accumulation 8, preserving effective batch 32 and all expected step counts. Evidence is
  `docs/evaluation/results/2026-08-17-direct-sotto-2112-memory-diagnostic.json`.
- The full 135,503-row Sotto run completed successfully at
  `/data/rise/android_stt/runs/direct-sotto-qwen3-0.6b-e1-seed23-20260817T124158Z` from training
  commit `c556709`. It passed complete no-truncation audits (train maximum 1,838; validation
  maximum 2,050), reached 4,235/4,235 optimizer steps, and exited zero. Train loss was 0.09389;
  validation loss improved from 0.09679 at step 1,059 to 0.07938 at step 4,235. Runtime was
  7,662.1 seconds. Resumable checkpoints are under `checkpoint-1059`, `checkpoint-2118`,
  `checkpoint-3177`, and `checkpoint-4235`; the final adapter is under `final-adapter`, and the
  root `trainer_state.json` and `status.json` record the terminal state.
- The final 40,422,168-byte adapter has SHA-256
  `22736a4d4aff8b5788386a80d643296874c3b54dd980404e7196a5665023fa2b` and exactly matches the
  step-4,235 checkpoint adapter. Its config SHA-256 is
  `f08b77c9295ebedfee2c0230f7277c7ec5d17f33ea54d040c19440b19d71249d`.
- Retired diagnostics are complete: 15/24 seed exact, 36/45 heldout exact, 51/69 combined, 153/163
  anchors, 7/10 self-corrections, and 15/17 must-not-answer cases. Agent review of all 18 non-exact
  outputs found eight substantive raw-policy failures, including intent change, answered content,
  protected entity/name/identifier changes, and substantive deletion. Raw semantic safety fails;
  this adapter is not a deployment candidate and guardrails cannot convert it into one.
- Full Sotto publisher validation is complete: 4,751/6,921 raw exact (68.65%), zero empty outputs,
  48 output-cap hits, and 3,098 guardrail flags. Generation exited zero with exactly 6,921 result
  rows. Mixed-concurrency A6000 latency was 91.5 ms median TTFT and 583.4 ms median total; do not
  treat it as a clean standalone benchmark.
- A separate locked vLLM 0.8.5 / Python 3.10 / Torch 2.6.0+cu124 environment now serves the pinned
  Qwen3-0.6B base and completed Sotto LoRA on the A6000. The deterministic multi-client runner
  shards by case ID, resumes only validated prefixes, records raw and parallel guardrail evidence,
  refuses blind paths, and validates a source-order merge. Complete publisher sweeps took 91, 87,
  83, and 84 seconds at 16, 32, 64, and 128 clients; 64 is the measured default for this workload.
  The server was stopped after evaluation. Sharding and merge membership are deterministic, but
  vLLM 0.8.5 generation is not batch-invariant: publisher exact counts ranged from 4,739 to 4,750
  versus 4,751 sequential, with a maximum 0.17-point aggregate delta and 110–124 changed outputs
  per run. Use one fixed 64-client backend for comparisons and repeat borderline results. All raw
  results remain under `/data`.
- Cross-dataset generation is complete. The Sotto adapter reached 472/1,000 exact on Disfl-QA dev
  with 732 guardrail flags and 32/250 exact on Nyra validation with 76 guardrail flags. Neither
  result justifies skipping standalone source training.
- Final sanitized training, artifact, publisher, cross-dataset, and retired-diagnostic evidence is
  in `docs/evaluation/results/2026-08-18-direct-sotto-qwen3-evaluation.json`; the earlier interim
  snapshot is retained for provenance. Raw publisher pairs/results and model artifacts remain
  under `/data`, outside Git.
- Sotto has no located formal paper; the publisher's evolving Hugging Face model card is its
  stated training research document. The closest detailed reference uses LFM2.5-350M full SFT for
  three epochs at 3e-5, effective batch 8, AdamW beta2 0.95, cosine/50-step warmup, packed 4,096
  context, BF16+TF32, and seed 42, followed by GRPO/refinement stages. This is follow-up evidence,
  not a directly transferable Qwen LoRA recipe. The immutable-source comparison is
  `docs/research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md`.
- The current base-model reassessment keeps Qwen3-0.6B plus BF16 rank-16 LoRA for the controlled
  source comparison, then prioritizes Qwen3.5-0.8B as the stronger-base follow-up. Gemma 3 1B is
  the quality alternative and LFM2.5-350M is the deployment-speed wildcard; Gemma 4 E2B is outside
  the sub-1B experiment.
- The fixed-recipe Disfl-QA standalone run completed at
  `/data/rise/android_stt/runs/direct-disfl-qa-qwen3-0.6b-e1-seed23-20260817T165542Z`: 225/225
  steps, 7,181/1,000 rows, no truncation, 0.19946 train loss, and 0.14729 final validation loss.
  Its own-source vLLM score was 765/1,000 exact, but transfer collapsed to 100/6,921 Sotto and
  30/250 Nyra. Exhaustive review of its 62 non-exact retired outputs found 23 substantive raw
  policy failures. It is source-specific and rejected; sanitized evidence is
  `docs/evaluation/results/2026-08-18-direct-disfl-qa-qwen3-evaluation.json`.
- The fixed-recipe Nyra standalone run completed at
  `/data/rise/android_stt/runs/direct-nyra-qwen3-0.6b-e1-seed23-20260817T171059Z`: 140/140 steps,
  4,458/250 rows, no truncation, 0.12580 train loss, and 0.07235 final validation loss. Its
  same-profile vLLM results were 150/250 own-source, 1,479/6,921 Sotto, and 73/1,000 Disfl-QA.
  Retired diagnostics reached 38/69 exact but all 10 self-corrections missed exact targets, and
  exhaustive review of all 31 non-exact outputs found 18 substantive raw policy failures. It is
  rejected; sanitized evidence is
  `docs/evaluation/results/2026-08-18-direct-nyra-qwen3-evaluation.json`.
- Poor cross-source transfer and raw-safety failure across all three standalone adapters justify
  the predeclared combined experiment. The initial one-epoch combined run at
  `/data/rise/android_stt/runs/direct-combined-qwen3-0.6b-e1-seed23-20260817T172338Z` passed the
  complete no-truncation audit and reached step 92/4,599 before an explicit user-requested stop;
  its `KeyboardInterrupt` status and logs are preserved, and it is not a training failure.
- The combined follow-up is deliberately three epochs so checkpoints at steps 4,599, 9,198, and
  13,797 can be evaluated as an epoch-wise learning curve. The dedicated config changes only
  epochs, total expected steps, save/eval cadence, and checkpoint retention relative to the
  combined one-epoch recipe; data, Qwen3-0.6B, BF16 rank-16 LoRA, optimizer settings, effective
  batch 32, seed 23, and the 2,112-token no-truncation contract remain fixed. This is a recipe
  follow-up, not a directly identical fourth row in the one-epoch dataset comparison. Never use
  blind-v2 to choose among its checkpoints.
- The three-epoch run completed at
  `/data/rise/android_stt/runs/direct-combined-qwen3-0.6b-e3-seed23-20260817T173233Z` from clean
  training commit `00fae17`: exactly 13,797 steps, 23,584.5 seconds, 0.07053 aggregate train loss,
  and zero truncation across 147,142/8,171 rows. Complete resumable checkpoints exist at steps
  4,599, 9,198, and 13,797; the final adapter exactly matches checkpoint 13,797.
- Validation loss was 0.09308, 0.08544, and 0.09364 at epochs 1–3. The fixed vLLM profile scored
  every epoch on all three publisher splits and both retired diagnostic suites. Epoch 2 is the
  experimental selection: 4,850/6,921 Sotto, 769/1,000 Disfl-QA, 147/250 Nyra, 52/69 retired
  exact, and 153/163 anchors. It improves the same-profile standalone Sotto/Disfl-QA counts by
  111/4 but trails Nyra by 3. Epoch 3 marginally improves Sotto/Disfl-QA while regressing Nyra,
  validation loss, retired exactness, anchors, no-op behavior, and safety.
- No combined checkpoint is deployable. Exhaustive agent review of every non-exact retired raw
  output found 8, 9, and 14 substantive policy failures at epochs 1–3, including answered content,
  changed dictated intent, deleted framing/negation/tone, protected name/literal changes, and
  invented formatting. Guardrails cannot rescue these raw failures. Sanitized hashes and the
  selection rationale are in
  `docs/evaluation/results/2026-08-18-direct-combined-qwen3-learning-curve.json`; raw artifacts and
  review queues remain under the run's `/data/.../evaluation/epoch-*` directories.
- The publisher's finished Sotto LFM2.5-350M checkpoint was pinned at
  `6df6f019170b8b55333c047b901886a51750a965`, downloaded, hash-verified, and evaluated in BF16 with
  its native prompt/decoder on all 69 retired diagnostics. It reached 42/69 exact, 147/163 anchors,
  and 2/10 exact self-corrections; all 17 dictated questions/commands remained text rather than
  being answered. User review calibrated 59/69 outputs as acceptable for ordinary conversation.
  The ten relevant failures are seven retained superseded corrections, two retained direct
  repetitions, and one statement changed into a question. It has been converted only as a
  replaceable Android integration placeholder and is not deployment-ready; see
  `docs/evaluation/results/2026-08-18-sotto-lfm25-350m-public-screen.md`.
- The user-calibrated everyday-conversation screen does not gate on disposable lead-ins,
  punctuation/contractions, word-to-digit time conversion, inferred list formatting, redundant
  but correct version wording, currency/non-Latin-name normalization, brackets, or technical/code
  literals such as the malformed Gradle case. Strict metrics remain unchanged for reproducibility.
- The approved next work is `docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`: first continue the
  public Sotto checkpoint for two full-SFT epochs at `2e-6` on the shuffled natural
  Sotto/Disfl-QA/DISCO-English/Nyra mixture, then—after complete evaluation—run a clean three-epoch
  `3e-5` full-SFT reproduction from pinned `LFM2.5-350M-Base` using the same mixture and the
  publisher's disclosed batch/schedule/packing settings.
- Training-code and data preflight for that campaign completed on the RTX A6000 host. Sotto
  and Nyra now resolve offline from the global Hugging Face hub cache, pinned DISCO English is
  preserved separately under `/data`, and the interrupted duplicate staging tree was removed.
  The prepared 149,922/8,519 train/dev streams use generated-and-recorded seed
  `5612273261405755832`, include every eligible row exactly once per epoch, contain no DISCO test
  rows, and exclude two Sotto train rows that overlapped frozen diagnostics. Natural train shares
  are 90.38% Sotto, 4.79% Disfl-QA, 1.86% DISCO, and 2.97% Nyra. The text-free mixture manifest
  SHA-256 is `5a08a5692d82bff9b3f7556ca4933fd4554fef724257c4dd7a4ae25d36126080`.
- The new LFM path is full-parameter SFT, not LoRA. It uses the publisher-native completion prompt,
  assistant-only labels, EOS termination, no truncation, ordered greedy 4,096-token packing, and
  microbatch one. Packed examples reset both `position_ids` (attention isolation) and `seq_idx`
  (LFM convolution-state isolation); a real BF16 A6000 forward pass accepted those tensors.
- Format, overfit, longest-example, interruption/resume, and saved-model inference gates all pass.
  Heavy smoke checkpoints were deleted after verification, reclaiming 6.0 GB while keeping compact
  evidence. Two-epoch Experiment A completed in 25m43s with dev loss 0.15292→0.14940. Both epochs
  score 47/69 retired exact versus 42/69 at start and emit identical retired text. Full source-dev
  exact improves 2,736→4,636→4,670/8,519 from start through epochs 1/2, with epoch 2 net-positive
  on every source. The separately named four-epoch learning curve completed in 51m18s and reached
  4,709→4,868→4,883→4,889/8,519 source exact with dev loss 0.14752→0.13859→0.13755→0.13746.
  Epoch 4 is selected for research comparison, but is not deployment-qualified because two
  source-dev cases repeat through the 900-token cap; epoch 5 is not justified. The predeclared
  three-epoch clean-base Experiment B completed in 39m19s. Its source exact curve is
  5,477→5,731→5,796/8,519, while retired exact is 51→47→46/69 and protected anchors are
  155→149→149/163. Select epoch 1 (`checkpoint-271`, SHA-256
  `e9d552f472374b51f8d59fe67623e0ae737ca9393a4b28d87341e9f5fab5de65`) as the safety-weighted
  research checkpoint, not epoch 3's aggregate leader. It still has one capped source repetition
  loop plus substantive raw-output safety failures, so no LFM checkpoint is deployment-qualified.
  The sanitized comparison is in
  `docs/evaluation/results/2026-08-18-sotto-lfm-ab-comparison.json`. The post-merge script suite
  passes 159/159 tests.
- The fixed personal-v3 BF16 matrix covers public start, all four A epochs, and all three B epochs.
  Strict diagnostics still put public first at 11/20 exact and 53/61 anchors. The default relaxed
  product calibration instead puts every B epoch at 15/20 acceptable, ahead of public/A at 14/20;
  B epoch 2 is the strict/anchor tie-breaker within B. Public fails three corrections and three
  formatting directives; B fixes one correction but still fails two corrections and all three
  directives. A also changes a euro value to dollars and changes past to present tense. B epoch 2
  now replaces the public artifact only as the explicit provisional integration default; its
  broader safety failures still prohibit deployment qualification. See
  `docs/evaluation/results/2026-08-18-sotto-lfm-personal-v3-checkpoint-matrix.md`.
- A separate hosted-API campaign now compares `gpt-5.4-mini-2026-03-17` and
  `gpt-5.4-2026-03-05` for the owner's optional personal-use path. It is isolated from local-model
  training and may not consume or produce training data. The user explicitly authorized sending
  both committed 24/45-case corpora and the public/synthetic source-dev evaluation split to this
  API evaluation, but blind-v2 remains prohibited. The user confirmed pilot traffic was free, then
  both models completed the 69-case sequential screen. Mini reached 27/69 exact but retained
  superseded text in 8/10 correction cases. GPT-5.4 reached 51/69 but obeyed a dictated instruction
  by outputting `Approved`, so both fail raw safety. On the same deterministic 1,500-row
  publisher-dev sample, GPT-5.4 reached 511 exact versus mini's 380, selected local A4's 848, and
  selected local B1's 951. Four-client median/p95 total latency was 788/1,207 ms for mini and
  855/1,348 ms for GPT-5.4. The complete hosted campaign used 1,343,189 tokens; standard paid
  equivalent is $2.4309, while dashboard attribution remains authoritative. See
  `docs/evaluation/results/2026-08-18-gpt54-api-screen.md`.
- The hosted campaign now also covers the active 20-case personal-v3 suite without rerunning the
  HF/publisher source-dev split. GPT-5.4 and GPT-5.6 Luna tie at 12/20 strict exact and 55/61
  anchors; mini reaches 10/20 and 53/61. Under user calibration, full and Luna are 20/20
  acceptable while mini is 18/20 because it retains two corrections. Luna leads the hosted
  comparison at 649 ms median total and $0.00112 paid-equivalent for the 20 requests. This makes
  Luna a personal-v3 candidate, not a claim about corpora that were deliberately not rerun.
- The default cross-model personal-v3 ranking is Luna/GPT-5.4 at 20/20 acceptable, mini at 18/20,
  clean-base Sotto B at 15/20, and public-HF/A at 14/20. Strict exactness remains secondary
  diagnostic evidence. The generic relaxed policy does not permit retained corrections, changed
  facts/units/tense, answered content, or unrealized explicit formatting directives.
- The user-authorized Pixel integration comparison should use hosted model slug `gpt-5.6-luna`
  and local B epoch 2. The latter remains outside Git on host `dante` at
  `/data/rise/android_stt/runs/sotto-lfm-b-full-20260818T084213Z-dirty/checkpoint-542` (weight
  SHA-256 `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6`). This is an
  integration-test candidate, not a deployment-qualified checkpoint.
- The local half of that comparison is now complete. Only inference files were copied from
  `dante`; optimizer state was not transferred. The reproducible B epoch-2 Q4_K_M is 229,310,336
  bytes with SHA-256 `02a4635a4c3bfdeadaa8c23a975dfc3bc6fde127184017f08ccefa6b431f65e0`.
  On direct personal-v3 cleanup it remains 15/20 acceptable, 8/20 strict, 46/61 literal anchors,
  1/3 corrections, and 0/3 formatting directives. Three-repeat Pixel timing is 159 ms median
  TTFT and 481 ms median total; attributed compute is 2.69 J/call at 3.84 W, peak PSS is 669,140
  KiB, and thermal status stays 0. Raw failures keep it out of deployment.
- The B epoch-2 Parakeet-fed run completes all 20 v3 synthetic clips. Parakeet reaches 15/20
  normalized STT exact; cleanup reaches 8/20 normalized intended-target exact and about 13/20
  manually acceptable. Median STT/cleanup/pipeline times are 764/784/1,552 ms. The attributed STT
  and cleanup stages total 7.18 J per utterance; peak joined PSS is 920,517 KiB and thermal status
  remains 0. The exact post-filler Parakeet inputs are projected for Luna without including local
  output as context.
- The user authorized the credential in `free_usage.md`, and the hosted half is complete. The
  canonical usage-enabled Luna run is 20/20 acceptable direct, 11/20 strict, and 54/61 anchors at
  630 ms median TTFT and 836 ms median total. After the exact measured Parakeet inputs, Luna is
  17/20 acceptable, 9/20 strict, and 53/61 anchors; estimated cleanup/pipeline medians are
  941/1,585 ms. It handles all three corrections and formats but changes case 012's protected
  `ICO` token into a first-person subject. The guard flags it, but the raw failure prevents
  deployment qualification. Luna remains the leading optional hosted candidate.
- The canonical 40 Luna calls report 4,763 input and 1,068 output tokens, or $0.002234 at captured
  standard rates. A first 40-call instrumentation pass lacked streamed usage; output caps bound
  the entire 80-call session at $0.005353 paid-equivalent. Dashboard billing/data attribution is
  authoritative. Complete aggregate evidence is
  `docs/evaluation/results/2026-08-18-luna-vs-sotto-b-epoch2-pixel.md`.

## Toolchain

- Android Studio Quail 3 / 2026.1.3 Patch 1
- Android Gradle Plugin 8.13.2
- Gradle 8.13
- Kotlin 2.3.20
- JDK 17
- compileSdk / targetSdk 36; minSdk 31
- Android Platform-Tools 37.0.1
- Android NDK 28.0.13004108 and SDK CMake 3.31.6 for the pinned Parakeet ARM64 build
- Perfetto trace processor 57.2 for optional Pixel power-rail analysis

## Resume checklist

1. Read root `AGENTS.md`, this file, and `NEXT_STEPS.md`.
2. Run `git status --short` and preserve any uncommitted work.
3. On the RTX A6000 machine, read `TRAINING_MACHINE_HANDOFF.md` completely and follow its Phase 0
   preflight. Do not run the Mac/Pixel steps below.
4. On the Mac with the Pixel attached, run `./scripts/check-toolchain.sh`, then
   `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`.
5. To resume integration testing, install the debug APK, run
   `./scripts/stage-integration-models.sh`, then load staged Parakeet and S1-mini in the Activity or
   IME. The
   ignored `.cache` artifacts must match the hard-coded hashes; see the root README and integration
   evidence manifest.
6. Preserve the completed LFM campaign and personal-v3 evidence. Keep exact-contract S1-mini as the
   preferred integration model, with Sotto B retained only for historical/debug reproducibility.
   Do not train on v3 errors. Any next model run or guardrail repair needs a separately reviewed
   plan and a fresh evaluation version; never use blind-v2 for iteration.
