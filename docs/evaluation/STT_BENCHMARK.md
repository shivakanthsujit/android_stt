# File-fed Pixel STT benchmark

This debug-only harness runs identical audio directly through each on-device STT engine. It never
opens the microphone. WAV decoding, ADB transfer, and host scoring are outside the measured model
inference interval.

## Corpus

The initial probe uses 24 clips selected deterministically from the official LibriSpeech
`test-clean` split: the first two utterances from each of the first 12 speakers in the pinned
Hugging Face `openslr/librispeech_asr` test row order. This is a practical multi-speaker probe
subset, **not** the published full-test-clean WER. LibriSpeech is 16 kHz read English speech
distributed under CC BY 4.0.

Downloaded audio and generated WAVs stay under `.cache/stt-eval/` and must not be committed. The
preparation script requires dataset revision `71cacbfb7e2354c4226d01e70d77d5fca3d04ba1`, downloads
only the selected audio assets, records the official source archive MD5, converts every clip to mono
signed PCM16 WAV, and writes source/output SHA-256 hashes plus a manifest hash.

```bash
./scripts/prepare-librispeech-stt-eval.py
```

The fixed selection ID is
`first-2-utterances-from-first-12-speakers-in-hf-test-row-order-v1`. Changing the speaker or clip
counts creates a different probe and must be reported as such.

## Pixel run

Attach the Pixel, keep it on external power, and run:

```bash
./scripts/run-stt-eval.sh
```

For the pinned `parakeet.cpp` Android runtime, build the debug-only native libraries and supply a
downloaded GGUF explicitly:

```bash
./scripts/build-parakeet-android.sh
STT_EVAL_ENGINE=parakeet \
STT_EVAL_MODEL=.cache/stt-eval/models/tdt_ctc-110m-f16.gguf \
STT_EVAL_MODEL_VARIANT=f16 \
./scripts/run-stt-eval.sh
```

To add exact process CPU time and Pixel hardware CPU/GPU/memory power-rail measurements, download
the official Perfetto `trace_processor_shell` into the ignored tool cache and opt in:

```bash
./scripts/setup-stt-power-tools.sh
STT_EVAL_POWER_TRACE=1 \
STT_EVAL_ENGINE=parakeet \
STT_EVAL_MODEL=.cache/stt-eval/models/tdt_ctc-110m-q4_k.gguf \
STT_EVAL_MODEL_VARIANT=q4_k-energy \
./scripts/run-stt-eval.sh
```

The app marks the complete benchmark and every measured inference with async trace slices. The
power scorer prorates 250 ms on-device rail samples across the 72 inference slices, excluding WAV
decode, PSS sampling, result writes, UI work, and warm-up. It reports CPU, GPU, memory/fabric, and
total compute joules plus average watts. Raw battery current is also traceable but is not used for
comparison while USB power is connected; the hardware rails sit downstream of the battery/charger.

The native build script verifies `parakeet.cpp` v0.5.0 commit
`1bfbebfaaf493866f49597cd3b7901959d395c60`, ggml commit
`e705c5fed490514458bdd2eaddc43bd098fcce9b`, NDK `28.0.13004108`, and CMake `3.31.6`.
Generated `.so` files and model weights are ignored and must not be committed.

The script builds and installs the debug APK, pushes the corpus into app-specific external storage,
launches the exported debug benchmark Activity, waits for an atomic result file, pulls it, and
scores normalized WER. Default timing is one warm-up inference followed by three measured passes
per case. Override bounded settings with `STT_EVAL_WARMUPS` and `STT_EVAL_REPEATS`.

Each JSONL row preserves the raw hypothesis and reference, along with model load time, inference
time, process CPU time, average active CPU cores, audio duration, real-time factor, post-inference
PSS/native heap, thermal status, audio hash, phase, and repeat index. Transcript contents are never
written to Logcat. Raw results, power traces, and summaries stay under `.cache/stt-eval/results/`
until a reviewed, provenance-complete report is intentionally added under
`docs/evaluation/results/`.

WER is computed after Unicode NFKC normalization, case folding, punctuation-to-space conversion,
and whitespace collapse. Punctuation and case behavior must therefore be reviewed separately from
the raw hypothesis; they are not part of normalized WER.

## Comparison contract

Moonshine and Parakeet must use the same manifest and decoded PCM samples. Report at minimum:

- normalized corpus WER plus substitution/insertion/deletion counts;
- raw punctuation/case observations;
- cached model load time;
- median, p90, p99, and maximum per-clip inference time so catastrophic tails stay visible;
- corpus real-time factor and audio-seconds processed per wall-clock second;
- model bytes, peak process memory, thermal state, and output stability across repeats.
- process CPU time and, for power runs, inference-attributed CPU/GPU/memory rail joules and watts.

Do not select an engine from host timings or from Parakeet's upstream NeMo-parity fixture. Final
selection requires this Pixel path and a later dictation-focused corpus covering names, numbers,
corrections, technical terms, pauses, and long-form speech.
