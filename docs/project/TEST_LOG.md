# Test log

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
