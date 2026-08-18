# Mac-local TTS evaluation pipeline

This pipeline turns literal text into reproducible local WAV fixtures for the file-fed Pixel STT
benchmark. It uses Qwen3-TTS 1.7B CustomVoice 8-bit through MLX-Audio on Apple Silicon, retains
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

## Cleanup regression and supplemental dictation corpus

The default batch contains the 45-case `cleanup_cases_heldout_v1.jsonl` suite plus 20 newly
authored dictation stress cases:

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

Both committed cleanup corpora are retired regression diagnostics, not untouched blind tests.
The generator projects only `id`, `spoken`, and `categories` into its generation plan. It never
passes `raw`, `expected`, `must_preserve`, prompts, captured model results, VoiceInk material, or
blind-v2 into the TTS backend. Android's `reference` is the human-readable `spoken` surface.

The 20 project-authored cases cover names and Unicode, times/dates/currency/phone numbers,
correction chains, uncertainty and negation, acronyms and letter-number identifiers, URLs and
paths, spoken punctuation, dictated questions/commands, intentional repetition, homophones,
numbered-list formatting, and longer dictation. They are also regression-only—not blind evidence
or training data.

## Pixel file-fed run

The generated manifest is already compatible with the existing debug benchmark. With the Pixel
attached, pass the corpus directory directly:

```bash
./scripts/run-stt-eval.sh \
  .cache/stt-eval/cleanup-heldout-v1-plus-dictation-tts-v1-qwen3-ryan
```

Set `STT_EVAL_ENGINE`, `STT_EVAL_MODEL`, and `STT_EVAL_MODEL_VARIANT` exactly as documented in
`STT_BENCHMARK.md` to use Parakeet. Unknown manifest fields are ignored by the current Android
reader; they retain TTS provenance, native hashes, stable seeds, signal statistics, and categories
for later staged scoring.

Before treating a clip as acoustic evidence, listen to technical, Unicode, correction, and
identifier cases for skipped or inserted speech and pronunciation errors. Literal WER also treats
many semantically equivalent number/symbol renderings as different; add protected-token and
numeric-equivalence scoring before making a dictation-quality decision.
