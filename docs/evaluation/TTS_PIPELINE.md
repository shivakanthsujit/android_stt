# Mac-local TTS evaluation pipeline

This pipeline turns literal text into reproducible local WAV fixtures for the file-fed Pixel STT
and joined STT→cleanup benchmarks. It uses Qwen3-TTS 1.7B CustomVoice 8-bit through MLX-Audio on
Apple Silicon, retains
the model's native 24 kHz master, and derives a 16 kHz mono signed-PCM16 WAV accepted by the
Android harness.

Synthetic speech is useful for end-to-end plumbing, repeatability, and lexical stress. A single
clean synthetic voice does **not** qualify real dictation quality, microphones, background noise,
accents, streaming responsiveness, or endpointing. Keep the existing real-speech and future
human-recorded dictation gates.

## Pins and artifact boundary

- MLX-Audio `0.4.6`, source commit `d28d68c6ac4e28f7d2d66007f640b06cf3fd8ceb`, MIT.
- `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit`, revision
  `41d3337e8b7f2843a75841595fc14e4b9a7a4b96`, Apache-2.0.
- Built-in English voice `Ryan`; no reference recording or voice cloning is used.
- Sampling is explicit and each case receives a stable case/text-derived MLX seed. The resulting
  master and canonical audio hashes are authoritative; bit-identical output is not promised across
  different MLX, model, Metal, macOS, or hardware versions.

The dependency lock is committed under `tts/`. The environment, model cache, masters, derived
audio, progress, and manifests stay under ignored `.cache/tts-eval/`. Do not commit generated
audio or downloaded model weights.

The separately inspected MLX-Audio source checkout is at `~/Documents/projects/mlx-audio` and is
detached at the pinned release commit. The runtime itself is installed only in this repository's
isolated ignored environment.

## Setup and a single clip

```bash
./scripts/setup-tts-env.sh

./scripts/generate-tts-audio.sh \
  --text "This is a local text to speech fixture." \
  --case-id manual-tts-001 \
  --output .cache/stt-eval/manual-tts-001
```

The first generation downloads about 3.08 GB of model files into
`.cache/tts-eval/huggingface/`. Later runs reuse that cache. A one-clip output is also a complete
Android-compatible corpus with `audio/`, `master-audio/`, `manifest.jsonl`, provenance metadata,
and hashes.

After the first successful download, verify the same cache without network access with:

```bash
TTS_OFFLINE=1 ./scripts/generate-tts-audio.sh \
  --text "Offline cache verification." \
  --case-id offline-cache-check \
  --output .cache/stt-eval/offline-cache-check
```

## Active personal-conversation corpus

The default batch is the 20-case
`docs/evaluation/stt_personal_conversation_tts_cases_v3.jsonl` suite. It reflects the intended
personal-phone workload: ordinary messages, journal entries, grocery/household lists, common
names, times, uncertainty, intentional repetition, natural corrections, and four 3–5 sentence
long-form latency cases. Phone-number dictation is intentionally excluded:

```bash
./scripts/prepare-cleanup-tts-eval.sh
```

Resume an interrupted model download or generation without changing its plan/profile identity:

```bash
./scripts/prepare-cleanup-tts-eval.sh --resume
```

Other bounded suites are available without allowing arbitrary evaluation paths:

```bash
./scripts/prepare-cleanup-tts-eval.sh --suite heldout-v1
./scripts/prepare-cleanup-tts-eval.sh --suite seed \
  --output .cache/stt-eval/cleanup-seed-v1-qwen3-ryan
./scripts/prepare-cleanup-tts-eval.sh --suite all-regressions \
  --output .cache/stt-eval/cleanup-all-regressions-qwen3-ryan
```

Both committed cleanup corpora available through the non-default options are retired regression
diagnostics, not untouched blind tests.
The generator projects only `id`, `spoken`, and `categories` into its generation plan. It never
passes `raw`, `expected`, `must_preserve`, prompts, captured model results, VoiceInk material, or
blind-v2 into the TTS backend. Android's `reference` is the human-readable `spoken` surface.

The active 20 cases intentionally exclude git commands, URLs, checksums, CLI flags, filesystem
paths, TLS, version strings, and similar developer stress text. The superseded v1 technical source
was removed from the active corpus after product calibration showed that it did not represent the
personal mobile workload. Historical reports remain historical evidence only.

The `expected` field is used only by the host result scorer after inference. It is never included
in the TTS generation plan or supplied to the speech generator, Parakeet, or Sotto. This suite is
evaluation-only: do not use its spoken text, expected cleanup, generated audio, or captured model
outputs for training, prompt demonstrations, retrieval, or preference pairs.

## Fast joined Pixel run

With both integration models staged and the Pixel attached, pass the generated directory to the
debug-only joined runner:

```bash
./scripts/run-joined-file-eval.sh \
  .cache/stt-eval/personal-conversation-tts-v3-qwen3-ryan
```

This runner never opens the microphone. It loads the staged Parakeet and Sotto artifacts once,
verifies every WAV hash, executes the complete joined pipeline, pulls raw JSONL results, and
automatically joins the active suite's intended cleanup targets for scoring. A single WAV or MP3
can be passed instead; ffmpeg canonicalization happens on the host:

```bash
JOINED_EVAL_REFERENCE="Optional literal spoken reference." \
  ./scripts/run-joined-file-eval.sh recording.wav
```

Use `run-stt-eval.sh` when measuring STT alone with repeats, WER, memory, thermal, or Perfetto power
telemetry. Use the ordinary microphone Activity for capture/lifecycle and real acoustic testing.

Before treating synthetic speech as acoustic evidence, listen for skipped or inserted speech and
name pronunciation errors. Literal WER also treats many semantically equivalent number/symbol
renderings as different; the joined target score is a cleanup regression metric, not a final
dictation-quality or real-speaker claim.
