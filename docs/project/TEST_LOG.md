# Test log

## 2026-08-18 — Relaxed personal-v3 cross-model audit

- Verified all eight local result JSONLs against their recorded SHA-256 values and confirmed 20
  unique cases per file. Reused raw outputs only; no local or hosted inference was launched.
- Reviewed the public Hugging Face Sotto SFT, A1–A4, B1–B3, GPT-5.4-mini, GPT-5.4, and GPT-5.6
  Luna under personal cleanup acceptance policy v1. Relaxed accepted counts are 14 for public,
  14 for every A epoch, 15 for every B epoch, 18 for mini, and 20 for full/Luna.
- Verified the relaxed failure sets: public `002/011/014/017/019/020`; A
  `011/013/014/016/019/020`; B `011/014/017/019/020`; mini `002/011`; full/Luna none.
- Historical strict scores and raw artifacts remain unchanged. Complete policy, comparison,
  provenance, and result hashes are in
  `docs/evaluation/results/2026-08-18-personal-v3-relaxed-cross-model-comparison.md`.

## 2026-08-18 — Hosted GPT personal-v3 screen

- Focused hosted runner/sharding tests passed 17/17 before transmission.
- Explicitly authorized personal-v3 run completed 60/60 first-attempt requests across
  GPT-5.4-mini, GPT-5.4, and GPT-5.6 Luna; every response was non-empty, finished with `stop`, and
  stayed below the Android-equivalent output cap. The HF/publisher source-dev corpus was not run.
- Raw strict results were 10/20, 12/20, and 12/20; literal anchors were 53/61, 55/61, and 55/61.
  Median total latency was 827, 860, and 649 ms respectively.
- Every non-exact and safety-sensitive output was reviewed. Under the user's explicit acceptance
  of collapsed duplicated emphasis, full and Luna are 20/20 user-acceptable. Mini is 18/20 because
  it retains superseded corrections in cases 002 and 011. No model answered either dictated
  question in the suite.
- Corpus/result SHA-256 values and the complete sanitized decision are recorded in
  `docs/evaluation/results/2026-08-18-gpt54-api-screen.md`.

## 2026-08-18 — Sotto LFM personal-v3 checkpoint matrix

- Integrated remote commits `b0ed579` and `cd77e76` through local merge `ab85a54`, preserving the
  existing dirty campaign worktree and retaining a named safety stash.
- `python -m unittest` for the sequential/batched Sotto inference and cleanup-guardrail modules
  passed 34/34 tests.
- Verified the 20-case v3 corpus SHA-256 as
  `667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`, the runner as
  `9d5839fed0680f54715ab038b0505907d5f893dabf78a54811b3f1d1ab31fe9f`, and all eight checkpoint
  weight hashes before inference.
- Public start plus A epochs 1–4 and B epochs 1–3 each completed 20/20 sequential BF16 cases with
  no token-cap hit. Public start leads at 11/20 exact and 53/61 anchors. Best fine-tuned is B epoch
  2 at 8/20 and 50/61; prior selected B epoch 1 reaches 7/20 and 46/61.
- Manually reviewed every non-exact and safety-sensitive raw output. A has a repeated unsupported
  currency-unit substitution. Public and all B checkpoints avoid unsupported substitutions here
  but fail required corrections/formatting. Guardrail review found two false-negative classes and
  one false-rejection class; passing parity tests do not cover these semantic gaps.
- The complete `scripts/tests` discovery suite passed 159/159 after the merge and report updates.
- Complete sanitized evidence:
  `docs/evaluation/results/2026-08-18-sotto-lfm-personal-v3-checkpoint-matrix.md`.

## 2026-08-18 — Personal-v3 long-form and checkpoint-eval contract

- TTS/checkpoint case files contain 20 matching IDs. Phone/callback-number text is absent. Four
  cases contain 3–5 sentences and are labeled `long_form`.
- `python3 scripts/score-cleanup-results.py --cases docs/evaluation/cleanup_personal_conversation_v3.jsonl --validate-cases-only`:
  passed with 20 valid cases and expected-aligned preservation anchors.
- Focused TTS/joined/inference/guardrail tests passed 49/49, including custom checkpoint identity,
  exact expected weight hash, audio/checkpoint case parity, and input-field CLI parsing.
- Complete `scripts/tests` discovery passed 141/142. The sole failure remains the pre-existing
  macOS `/var` versus `/private/var` temporary-path assertion. Final Android
  `lintDebug testDebugUnitTest assembleDebug` passed all 55 tasks.
- Offline TTS generation completed 20/20; cases SHA-256
  `f3939fd89d9512e3599d875d5b8391aa3267dd4556ae21b2889903bfe1026791`, direct checkpoint cases
  SHA-256 `667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`, and manifest SHA-256
  `35f43e00b8e2a6fa7d95ae15de96ed75db5af82a62ca95dcd9ce079a6b69794e`.
- Pixel run `20260818T095822Z-joined-file`: 20/20 complete; STT strict/normalized exact 8/20 and
  15/20; raw/guarded cleanup strict/normalized exact 8/20 and 10/20; three fallbacks. Median
  STT/cleanup/joined latency was 625/645/1,261 ms. Raw result SHA-256
  `4567490e2d7e00039c95b12fd7db65e30f482c0f16f86cda386b6df5b20b90f9`.
- Long-form joined latency: v3-015 3,970 ms, v3-018 2,543 ms, v3-019 3,716 ms, and v3-020
  4,746 ms. All produced complete results; v3-020 used fallback for retained correction content.
- Tested/installed APK: 88,044,569 bytes, SHA-256
  `40ab366fbdf24aa15cfcff11a1ea8ce947c7106d7d65d249c4f22ab581e102a8`. Final
  documentation-inclusive local build: 88,044,777 bytes, SHA-256
  `22719570e435a379ecbaa2d91e823fb0b5b846f93a761d9021f86524d5b40ae3`.

## 2026-08-18 — Personal-v2 file-fed joined regression

- `bash -n scripts/run-joined-file-eval.sh`: passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts.tests.test_tts_pipeline scripts.tests.test_score_joined_results -v`:
  16/16 passed after adding cleanup-target scoring.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest scripts.tests.test_cleanup_guardrails -v`:
  28/28 passed, including host parity for sentence-initial discourse removal, numeric equivalence,
  changed-value rejection, repeated-imperative `sorry` correction, formatting directives, and the
  bounded journal lead-in.
- `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`:
  final rerun passed (55 tasks, no lint/build/unit failure).
- Complete `scripts/tests` discovery: 139/140 passed. The sole failure is the pre-existing macOS
  `/var` versus `/private/var` temporary-path assertion in
  `test_safe_target_rejects_archive_escape`; all 28 updated host guardrail parity cases and all new
  TTS/joined-scorer tests passed. Separate `tests/` discovery passed 10/10.
- Offline TTS generation completed 20/20 personal v2 clips. Cases SHA-256:
  `2a8c6e247a47b6ad9a48a78e37c540ab44707cb546f53bef2b421c540a3103ba`; manifest SHA-256:
  `771d2fff6b1d9bf8c2e9492d483dbe461f07dd7176996ad6f817e9e5f7c62029`.
- Final Pixel run `20260818T093938Z-joined-file`: 20/20 complete; raw STT strict/normalized exact 6/20 and
  16/20; raw/guarded cleanup strict/normalized exact 8/20 and 10/20; three fallbacks. Valid medians:
  499 ms STT, 637 ms cleanup, 1,135 ms joined. Raw result SHA-256:
  `f25543e4f7447900069ce4d1acf49f20732e6dfc987ef8748b863ea2dad7d1a8`.
- Tested/installed APK: 88,044,472 bytes, SHA-256
  `0b594350f9239376a16b9abf508e9f51f64fa92651085d084a164afb6a91b654`.
- Final documentation-inclusive local build APK: 88,044,472 bytes, SHA-256
  `737c6eecd425df89ec2564d1eb7ce818675f2f308300d39921d16a1062a50ab5`.
- Schema repeat `20260818T092847Z-joined-file` reproduced all quality counts and verified JSON-array
  filler metadata plus explicit nullable fields. Its latency is excluded because the Pixel slept
  while the Activity was paused; the launcher now wakes/dismisses keyguard before starting.
- Manual raw-output review: the three fallbacks were genuine retained correction content in cases
  002, 011, and 020. Accepted Sotto output did not invent a new semantic fact beyond Parakeet's
  hypothesis, but list/paragraph/false-start cleanup remained incomplete and name errors propagated
  from STT. Public Sotto remains no-go.

## 2026-08-18 — Twenty-case acoustic joined-pipeline regression

- Played `dictation-tts-001` through `dictation-tts-020` from the pinned Qwen3-TTS/Ryan fixture
  corpus through the MacBook Air speakers at volume 56 into the physical Pixel 7 microphone. The
  desk acoustic path was uncontrolled; this is integration regression evidence, not STT quality
  qualification.
- Exact tested identities: APK SHA-256
  `a00353b6b1975f6a016878fdd694f33e9668eb25f8a3eaed2a67938b55239865`, Parakeet SHA-256
  `2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf`, Sotto SHA-256
  `05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570`, and fixture-manifest
  SHA-256 `10a06cdece044e4c0383eb5719461fdba3b74cb6638efd9d5c238cf7728964cf`.
- All 20 cases completed with warm models. No crash, stuck microphone, failed model state, or
  missing cleanup result occurred. Post-run AppOps showed the last microphone duration as 37.97
  seconds with no active use, Logcat showed the final stop/finalize/cleanup sequence without an
  error, and thermal status remained 0.
- Parakeet reached 4/20 strict exact and 11/20 lowercase/punctuation-normalized exact on this
  acoustic path. Diagnostic timing medians were 934 ms Stop-to-STT, 565 ms cleanup total, and
  1,466 ms Stop-to-cleanup; p90s were 1,333, 655, and 1,950 ms respectively.
- Sotto produced 15 guardrail fallbacks and five accepted outputs. Four accepted outputs were
  no-ops. Case 014's remaining accepted output changed a dictated technical command and is a raw
  semantic-safety/guardrail miss. Case 011 correctly selected canary over superseded beta, but the
  guardrail rejected the correction. Public Sotto remains a no-go integration placeholder.
- Full per-case observations, critical raw outputs, hashes, timing, and caveats:
  `docs/evaluation/results/2026-08-18-parakeet-sotto-tts-acoustic-integration.md`.

## 2026-08-18 — Conservative filler pre-pass

- Added eight focused JVM cases for the deterministic `um`/`uh`/`erm` pass. All pass, including
  preservation checks for ambiguous discourse words, quoted/code-like text, uppercase acronyms,
  a title-cased name-like token, hyphenated text, paths, and paragraph breaks.
- Full `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`
  verification passed with no lint errors. The suite has 35 passing JVM tests: 8 filler, 22
  guardrail, 3 artifact-identity, and 2 STT-metric tests.
- The final 88,044,124-byte APK has SHA-256
  `a00353b6b1975f6a016878fdd694f33e9668eb25f8a3eaed2a67938b55239865` and installed successfully
  on the connected Pixel 7 without clearing its staged models. Interactive filler-path
  verification could not proceed because the device returned to a secure lock screen; no
  credential bypass was attempted. Host logic/build verification is complete, but this entry does
  not claim a new on-device inference result.

## 2026-08-18 — Joined Parakeet/Sotto Pixel integration

- Full Android gate passed:
  `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`.
  Shell syntax and `git diff --check` also passed.
- Installed the 88,043,862-byte ARM64 debug APK on Pixel 7; SHA-256
  `33a2b85b8d6c003631ac63ad5100002bdcd81032e066d7efc970d59f206d3327`.
- Reverified the staged device artifacts: Parakeet Q4_K
  `2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf` and Sotto Q4_K_M
  `05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570`.
- Both Android runtimes loaded: Parakeet in 270 ms and Sotto in 904 ms. A benign typed cleanup
  smoke completed without fallback at 141 ms TTFT and 285 ms total.
- A real microphone → Parakeet → Sotto run completed. The 22.091-second capture finalized in
  1,568 ms after Stop; cleanup completed in 456 ms and total Stop-to-cleanup tail was 2,029 ms.
  Sotto's raw output deleted protected negation, the lexical guardrail detected it, and the final
  output fell back to raw STT. No raw microphone transcript is persisted in this log.
- This proves the joined lifecycle and fallback visibility, not model qualification. Public Sotto
  remains a no-go placeholder and Parakeet remains batch-on-Stop rather than streaming. Full
  identities and sanitized evidence are in
  `docs/evaluation/results/2026-08-18-parakeet-sotto-integration-build.json`.

## 2026-08-18 — vLLM sharded evaluation

- Locked environment verification passed with Python 3.10.19, vLLM 0.8.5, Torch 2.6.0+cu124,
  Transformers 4.51.3, CUDA visibility, A6000 BF16 matmul, exact source/model/adapter/config hashes,
  and a clean vLLM v0.8.5 source checkout.
- Server smoke passed for both `/v1/models` registration and a non-thinking completion through the
  startup-loaded `sotto-qwen3-0.6b-e1-seed23` LoRA.
- The 16-client initial publisher run produced and validated all 6,921 rows. The committed 24-case
  and 45-case corpora likewise merged 24/24 and 45/45 rows. All outputs remain outside Git.
- Final-profile complete publisher sweeps validated 6,921/6,921 rows at each concurrency: 16 clients
  in 91 seconds, 32 in 87 seconds, 64 in 83 seconds, and 128 in 84 seconds. A quiet 64-client repeat
  also completed in 83 seconds with every request succeeding on its first attempt.
- Latest unit verification: `python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`
  passed 111/111; `python3 -m unittest discover -s tests -p 'test_*.py' -v` passed 10/10.
- `bash -n scripts/training/setup_vllm_env.sh`, server command rendering, JSON evidence validation,
  and `git diff --check` passed. Blind-v2 was not read or used, and this work did not score or
  modify the separately managed sequential evaluation.
- Post-run row comparison: both committed diagnostic suites are bit-for-bit equal between
  sequential and vLLM inference. Publisher vLLM runs have 110–124 model-text differences and
  48–61 exact-status flips relative to sequential, with net raw-exact deltas from -1 to -12 rows.
  Two 64-client repeats differ on 75 outputs and 32 exact statuses. Every publisher result retains
  the same 6,921 IDs, zero empty outputs, and 48 cap hits; guardrail flags range from 3,097 to 3,102.

## 2026-08-17 — RTX Phase 0 and public-data pipeline fixtures

- Preflight repository commit: `2ae244cf761d91846396b6f96161955e7666e3d5`.
- Script/unit command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`.
- Latest result: 93/93 passed, including V2 formatting/grammar/ASR controls, deterministic pending
  supplement generation, cross-cutting quota-aware selection, optimized near-duplicate grouping,
  and a complete text-free Gate A CLI fixture using the real validator/schema/artifact hashing path.
- Baseline command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v`.
- Result: 10/10 passed.
- `git diff --check`: passed.
- The new tests use synthetic fixtures only. They do not load or reproduce either frozen cleanup
  evaluation corpus as training data.
- GPU training has not started: the locked CUDA environment and BF16 check pass, but Gate A human
  review has not occurred.

All tests below used a physical Google Pixel 7 unless stated otherwise. Raw transcript contents are
not persisted here; only representative accuracy observations and timing are recorded.

## 2026-08-18 — File-fed STT and power probe

- Device: Pixel 7 `panther`, serial `33040DLH20004E`; debug ARM64 APK; cleanup unloaded; no
  microphone opened.
- Corpus: deterministic 24-clip/12-speaker LibriSpeech `test-clean` probe; manifest SHA-256
  `7c90de45a130caf4ceb2f5215be114bd9daaa34e95549958440ccb7a95cc187f`; one warm-up plus three
  measured repeats per clip.
- Clean untraced Moonshine Small: 3.54% WER (21/593), 1,233.7 ms median, 3,033.3 ms p90,
  4,061.1 ms max, 6.46× realtime, 816,828 KiB peak PSS, thermal status 1, 7 normalized unstable
  cases.
- Clean untraced Parakeet F16: 1.69% WER (10/593), 1,034.5 ms median, 2,388.1 ms p90,
  3,772.7 ms max, 7.94× realtime, 525,408 KiB peak PSS, thermal status 0, no unstable cases.
- Clean untraced Parakeet Q4_K: 1.85% WER (11/593), 717.0 ms median, 1,798.4 ms p90,
  2,694.9 ms max, 11.31× realtime, 392,342 KiB peak PSS, thermal status 0, no unstable cases.
- F16/Q4_K normalized outputs differed only on `Hidalgo` versus `Hadalgo`.
- Perfetto v57.2 power runs used 72 app-marked measured inference slices and Pixel on-device power
  rails. Q4_K: 553.3 process-CPU seconds, 205.895 J CPU, 0.097 J GPU, 29.065 J memory/fabric,
  235.057 J compute total, 2.802 W average compute power, 387,103 KiB peak PSS. F16: 725.7 CPU
  seconds, 276.313 J CPU, 0.268 J GPU, 29.996 J memory/fabric, 306.577 J compute total, 3.065 W,
  519,708 KiB PSS. Moonshine: 696.9 CPU seconds, 367.330 J compute total, 811,449 KiB PSS.
- Power-trace wall latency was perturbed, especially for Moonshine; untraced runs are the latency
  evidence and traced runs are CPU/energy evidence.
- STT-session host standard-library tests passed 54/54 before integration; the focused STT scorer
  tests passed 3/3 afterward. Final offline `lintDebug testDebugUnitTest assembleDebug`
  verification passed (55 Gradle tasks). The integrated debug APK was 87,964,790 bytes with
  SHA-256 `da4a8dcddb133690b9b78b392697829bcee5dc5b991ac52c3486d75697cdc122`.
- After rebasing over concurrent training work, the expanded host suites passed 117/118 script
  tests and 10/10 general tests. The sole failure is the unrelated training fetcher's macOS
  temporary-path assertion comparing `/var/...` with its canonical `/private/var/...` form in
  `test_safe_target_rejects_archive_escape`; the concurrent training code was left unchanged.

## 2026-08-17 — Training-machine handoff validation (host only)

- Verified `origin` points to `https://github.com/shivakanthsujit/android_stt.git` and `main`
  tracks `origin/main`.
- Resolved immutable source revisions with `git ls-remote`: Sotto
  `183cc8fd58532f13fa192980185214de1bcd5acc`, Disfl-QA
  `1f0c16171c77b3d3408be92c485f11b8998a9189`, and Nyra Disfluency Speech
  `723e9e69bfbdc8214a9b8ce8815985e90afcbaa3`.
- Host script tests: 51/51 passed.
- Deterministic baseline tests: 10/10 passed.
- Both frozen cleanup corpora validated: 24/24 and 45/45 structurally valid.
- `git diff --check` passed.
- Confirmed git ignores raw/work/private cleanup data, training runs, checkpoints, and model
  artifacts while retaining `data/cleanup/README.md`.
- No dataset payload, model training, checkpoint generation, or Android code change occurred.

## 2026-08-17 — Milestone 1 Moonshine

### Build verification

- Command: `. ./scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`
- Result: successful; 55 tasks; lint has no errors.
- Unit tests: `SttResult` monotonic metric tests passed.
- Final APK SHA-256 at commit `3273684`:
  `1b95121403d2e3469031f487ea45ed1311cf0cf8fe6cf4dfb6d78d915d36859e`
- APK size: about 31 MiB, ARM64 only.

### Model/cache

- First Small Streaming download and load: 21,549 ms.
- Subsequent warm loads: 1,029–1,064 ms.
- Airplane-mode force-stop/cold-launch load from cache: 1,064 ms; transcription succeeded.
- Airplane mode was disabled again after the test.

### Transcription/timing

- Short benchmark utterance: accurately recognized; finalization proxy initially 250 ms.
- Explicit low-level Transcriber implementation: finalization tail 0–7 ms in observed runs.
- Long user evaluation: 59,551 ms of recording; 7 ms finalization; the full recording continued
  until Stop, but accuracy and sentence segmentation were unsatisfactory.

### Microphone lifecycle regression test

1. Before Start, `cmd appops get dev.localflow.dictation RECORD_AUDIO` had no `(running)` marker.
2. During dictation it reported `RECORD_AUDIO ... (running)`.
3. Immediately after Stop the `(running)` marker disappeared and AppOps showed a completed duration.
4. A repeated final-build cycle recorded 18,881 ms and again showed no active operation after Stop.

Conclusion: the model remains warm, while microphone capture is active only between Start and Stop.

## 2026-08-17 — LFM2.5-230M cleanup-only evaluation

- Liquid LEAP 0.10.9; LFM2.5-230M Q4_K_M.
- First download/load: 38,616 ms; cached warm loads: 662–989 ms.
- Direct-text corpus: 24 cases × 3 prompt variants; no microphone use.
- Final 72-run matrix completed fully offline in 44,176 ms.
- Best safe variant: isolated rules; 3/24 strict exact, 96.7% anchor preservation, 3/24
  guardrail fallbacks, 530 ms median TTFT, 661 ms median total.
- Decision: 230M is too unreliable as the default cleanup model; proceed to 350M comparison.
- Full summary and raw static-corpus outputs:
  `docs/evaluation/results/2026-08-17-lfm25-230m-q4km.md`.

## 2026-08-17 — LFM2.5-350M cleanup-only evaluation

- Same Pixel, LEAP version, corpus, prompt variants, seed, bounds, and guardrails as 230M.
- First model download/load: 55,706 ms.
- Full matrix: 60,162 ms.
- Best isolated prompt: 1/24 strict exact and 77.0% anchor preservation.
- Observed meaning-changing negation failure; 350M is a no-go and worse than 230M.
- Full summary and raw outputs: `docs/evaluation/results/2026-08-17-lfm25-350m-q4km.md`.

## 2026-08-17 — LFM2.5-1.2B-Instruct cleanup-only evaluation

- Liquid LEAP 0.10.9; LFM2.5-1.2B-Instruct `Q4_K_M`; about 697 MiB download.
- First download/load: 248,559 ms. Cached airplane-mode load: 1,928 ms; airplane mode restored.
- A/B/C matrix: 72 runs in 240,634 ms. Best exact score was isolated rules at 13/24, but it had
  meaning-changing summaries/answers, lost technical content, and failed all self-corrections.
- Safest copying variant: command envelope at 6/24 exact, 98.4% anchor preservation, and 2,807 ms
  median total; it under-edited and relied on fallbacks.
- Focused D/E matrix: 48 runs in 304,337 ms. Strict minimal editing scored 0/24; few-shot scored
  8/24 with 6,956 ms median total and sometimes copied a demonstration.
- Post-run memory: 922,265 KiB PSS, 980,028 KiB RSS. Overall thermal status 0; battery about 33.6 °C.
- Decision: no-go for automatic cleanup. Full summary and raw outputs:
  `docs/evaluation/results/2026-08-17-lfm25-1.2b-instruct-q4km.md`.
- Final cleanup-harness APK: about 61 MiB; SHA-256
  `fa924ce4c4f4d9bd5695219802c1189938294959236616000adde08866bfe4c9`.
- Final build passed lint, unit tests, and assembly. Temporary screen-awake settings were removed;
  device `stay_on_while_plugged_in=0` and airplane mode was disabled.

## 2026-08-17 — Cross-family host cleanup screen

- Added and validated a fresh 45-case held-out corpus with 102 preservation anchors and no
  normalized-raw overlap with the original 24 cases.
- Host: Apple M2 MacBook Air, 16 GB; llama.cpp build 10450 (`ece963f41`).
- Fixed run settings: temperature 0.1, seed 23, input-derived 16–96 output-token cap.
- Screened deterministic v1, Granite 4.0 H 350M Q4_K_M, Qwen3 0.6B Q4_0 no-think, Gemma 3 270M
  QAT Q4_0, Qwen3.5 0.8B Q4_0 no-think, and Gemma 3 1B Q4_K_M.
- Best raw result was Gemma 1B: 32/45 exact, 96/102 anchors, 253 ms median TTFT, and 437 ms
  median total host latency. It still produced three semantic/safety failures and is a no-go.
- The Android-equivalent host guard selected 29/45 exact for Gemma 1B with 6/45 fallbacks after two
  held-out regressions were added. It now rejects all three audited unsafe edits; guardrails remain
  safety containment, not a quality substitute.
- The revised guard accepts 41/45 held-out reference edits. Its four conservative false rejections
  are recorded in the full report and require a new validation set before further policy tuning.
- No candidate advanced to Pixel runtime benchmarking. Complete model-by-model results and failure
  examples: `docs/evaluation/results/2026-08-17-cross-family-cleanup-screen.md`.
- Host guardrail/runner tests: 28/28 passed; deterministic baseline tests: 10/10 passed. Both the
  24-case seed and 45-case held-out result sets pass schema and complete-run scoring validation.
- Final Android verification: offline `lintDebug testDebugUnitTest assembleDebug` succeeded (55
  tasks). Debug APK: about 62 MiB, SHA-256
  `71af1c0ef2a1967b48a4f645681d3dd82ba4435fffc6ae17035c7ba0463fae56`.

## 2026-08-17 — VoiceInk Qwen3.5-2B task-tuned screen

- Internal inference only; no training job. Author-published 1,274,396,352-byte Q4_K_M GGUF,
  SHA-256 `343721d889adcec76725373f51be207e6a980eec8411e4e6c553dd6c8329d175`.
- Exact author training prompt and `<TRANSCRIPT>` wrapper; llama.cpp build 10450; non-thinking;
  temperature 0.1; seed 23; input-derived 16–96 token cap.
- Seed raw: 12/24 exact, 55/61 anchors, 0/3 corrections; median TTFT 122 ms, total 492 ms.
- Regression-v1 raw: 26/45 exact, 94/102 anchors, 2/7 corrections; median TTFT 122 ms, total 396 ms.
- Independent audit: 21 harmless differences, 6 retained superseded corrections, 3 meaning/fact
  changes, and 1 followed instruction. Strict no-go; no Pixel runtime work.
- Full report and raw/provenance artifacts:
  `docs/evaluation/results/2026-08-17-voiceink-qwen35-2b-q4km.md`.

## 2026-08-17 — Direct-source trainer preflight

- `PYTHONDONTWRITEBYTECODE=1 /data/rise/android_stt/env/bin/python -m unittest discover -s scripts/tests -p 'test_*.py' -v`
  passed 97/97.
- `PYTHONDONTWRITEBYTECODE=1 /data/rise/android_stt/env/bin/python -m unittest discover -s tests -p 'test_*.py' -v`
  passed 10/10.
- Direct loader audit verified every configured source payload against
  `/data/rise/android_stt/manifests/source-manifest-v1.json`; exact train/validation usable counts
  are Sotto 135,503/6,921, Disfl-QA 7,181/1,000, Nyra 4,458/250, and combined 147,142/8,171.
- Frozen evaluation overlap check found zero exact normalized raw/target matches in every direct
  train and publisher-validation split. The check uses frozen text only as a rejection fingerprint;
  no evaluation text enters model input, target, prompt examples, or retrieval.
- GPU preflight: NVIDIA RTX A6000, UUID `GPU-8d6979b1-ddb6-1476-40ce-4ab6cd4f527b`, driver
  550.144.03, 49,140 MiB total and 31 MiB used, 32 °C, idle at observation. Locked environment:
  PyTorch 2.6.0+cu124, CUDA 12.4, CUDA visible, BF16 supported.
- Final post-fix script suite: 98/98 passed; host suite: 10/10 passed.
- Successful smoke run:
  `/data/rise/android_stt/runs/direct-sotto-qwen3-0.6b-smoke2-seed23-20260817T121729Z`.
  It completed step 2 with train loss 1.4542877 and 5.019 seconds trainer runtime. The tokenization
  audit found zero over-limit rows in the 32-row train/validation subsets, with maxima 229/273.
  `checkpoint-2/trainer_state.json`, trainer state, and a 40,422,168-byte
  `final-adapter/adapter_model.safetensors` are present. The adapter has 10,092,544 trainable
  parameters over 606,142,464 total parameters.
- Failed smoke directories are retained for diagnosis. The `20260817T121432Z` attempt failed on
  mapped chat-template output; the `20260817T121559Z` attempt failed on the removed
  `overwrite_output_dir` argument. Both failed before optimizer step 1. The earlier tmux launch
  `20260817T121303Z` was externally terminated during tokenizer download and retains a stale
  `running` status; it produced no metric or checkpoint.

## 2026-08-18 — Hosted GPT-5.4 evaluation runner and evidence

- `python3 -m unittest scripts.tests.test_run_cleanup_openai scripts.tests.test_cleanup_openai_sharding scripts.tests.test_score_sotto_lfm_source_dev`
  passed 19/19.
- `git diff --check` passed.
- The sharded runner validated and merged all 8,519 mini rows and all 1,500 GPT-5.4 sample rows.
  Resume validation preserved the four GPT-5.4 shard prefixes across an intentional cancellation;
  live token monitoring then resumed without duplicate case IDs.
- GPT-5.4's seven production-cap hits were isolated and merged after publisher-cap repair. Final
  corrected sample has 1,500 unique case IDs, zero cap hits, and score SHA-256
  `8a52cbf4df8513c5bb05c8f33208de6cb13451571172fa0815157b28dbbf60c8`.
- The token monitor reported final GPT-5.4 campaign usage of 178,988 input and 33,031 output tokens
  (212,019 total), below the enforced 220k cutoff. No hosted runner remained after validation.

## 2026-08-18 — Personal-v3 hosted/local comparison publication gate

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v`
  passed 159/159 after the Luna extension, relaxed cross-model review, and Pixel integration
  handoff documentation.
- `git diff --check` passed.
- Verified that B epoch 2's `checkpoint-542/model.safetensors` exists on `dante` under the recorded
  run path and is 708,984,464 bytes. Its SHA-256 remains
  `5336415629256074cd265b95938b4803ab908e0ea8f6bb8cd8c5265bfc3338e6` from the checkpoint matrix.
- No checkpoint, raw personal-v3 API result, credential file, or personal transcript is included
  in the Git publication set.

## 2026-08-18 — B epoch-2 Pixel direct and joined benchmark

- Pixel 7 `panther`, serial `33040DLH20004E`; all direct and joined cases completed with maximum
  Android thermal status 0.
- Direct result/summary/power SHA-256:
  `828a945c94f1c8b9a17ab21d44ce3d17d133c2f3eaa67dfd531d2c8ab7a22e90`,
  `1053d5fe0341da89bc463f3dcb6a60241e1a7ac36157c0d60f3c5a25e32d5d18`, and
  `aa67b7bb757b8c756ec4bb7e54e7ac3b24fa456ecae274f9962065c7ddfa90f4`.
- Joined result/summary/STT-power/cleanup-power SHA-256:
  `0471a0083e291b7e974563c0479300ca2177f67198314474c41a0c0e3bf78d78`,
  `c355f398c18f76ea44ca0ba82a36150506707c1beb8eea76041eddfb9bfa93e1`,
  `06288157ef45928767749d950fae7733861e6d2ae0d663bc55e27a30b31b0cf3`, and
  `4e5006a7cd0622b47da001e65b5eeb7c652507331f5747d3fa52dc9ef0ff44cc`.
- `python3 -m unittest scripts.tests.test_cleanup_pixel_benchmark
  scripts.tests.test_score_joined_results scripts.tests.test_run_cleanup_openai -v` passes after
  adding direct, projection, power-name, and hosted-joined timing coverage.
- Full `scripts/tests` discovery currently has 161 passes and one unrelated macOS path-alias
  failure: the archive-target test expects `/var/folders/...`, while `Path.resolve()` returns the
  equivalent `/private/var/folders/...` on this host. No training/cleanup behavior failed.
- `. scripts/android-env.sh && ./gradlew --offline lintDebug testDebugUnitTest assembleDebug`
  succeeds: 55 actionable tasks, 12 executed and 43 up-to-date.
- Verified debug APK: 88,045,558 bytes, SHA-256
  `7d5ab0ef6ebc0c4ece8b8885b2a0aca19730ae05a619f727a762ee22fada2bc4`.
- `git diff --check`, Python byte compilation, and shell syntax checks pass for the benchmark
  publication set.

## 2026-08-18 — Usage-enabled Luna comparison completion

- Canonical direct/E2E/combined result SHA-256:
  `76d5da132656775bfe9dca4284f1c09d1ebe92aab0365344a3f9c984b174c1f7`,
  `dcd91a2baf0d843458e3be29742ef69ece0845ec06ddca36e6e3cb9bd0932666`, and
  `b88050098689975a00b5bb3edc6b9085bd89b9c9a60e5f13804a60d74238308d`.
- Request-extra/projection SHA-256:
  `12f869439a7657bc9980c9feabcb1f70c17f1ed0b11dcc40de4edde48912414b` and
  `027819989c3a7a31d83028a31f978f5c25c13d213084dbb880540f130300b78b`.
- All 80 hosted calls completed on attempt one with `stop`, non-empty output, and zero token-cap
  hits. The canonical 40 calls contain API-reported usage on every row.
- Manual raw review covers all 40 canonical outputs. Direct Luna has zero semantic failures; joined
  Luna has one protected-token/subject change on case 012. Guardrail fallback is recorded
  separately and does not alter qualification.
- The projection tool now rejects preservation anchors absent from the cleanup target, and the
  combined scorer reports missing hosted usage as `null` rather than silently converting it to
  zero. Focused benchmark/runner/scorer tests pass 23/23 after these regressions were added.
- Full `scripts/tests` discovery runs 164 tests: 163 pass and the same unrelated macOS
  `/var/folders` versus `/private/var/folders` path-alias assertion fails. No cleanup benchmark,
  API runner, projection, scorer, or Android behavior fails.
