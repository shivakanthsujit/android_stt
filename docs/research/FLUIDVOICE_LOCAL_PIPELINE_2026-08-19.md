# FluidVoice local pipeline inventory

Date: 2026-08-19

## Purpose and boundary

This note records a read-only inspection of the owner's local FluidVoice installation so its
fully local dictation path can serve as a Mac reference baseline for Local Flow. It does not make
FluidVoice, Fluid Intelligence, or their artifacts part of the Android product. Model files and
the complete bundled prompt remain ignored outside Git.

The Fluid Intelligence model card attached to the preserved GGUF permits personal,
non-commercial use but prohibits redistribution, hosting, bundling, fine-tuning, commercial or
organizational use, and research without written permission. Accordingly:

- do not commit or redistribute the weights or full system prompt;
- do not use Fluid-1 output as training data, generator demonstrations, retrieval context,
  preference pairs, or a teacher for Local Flow;
- keep evaluation-only project corpora and blind-v2 entirely away from this baseline; and
- treat the local smoke test as personal functional verification, not model qualification or a
  license conclusion.

## Installed application identity

The application updated during inspection from FluidVoice 1.6.0 (build 12) to 1.6.9 (build 20).
The current executable is:

- path: `/Applications/FluidVoice.app/Contents/MacOS/FluidVoice`
- bundle ID: `com.FluidApp.app`
- signing team: `V4J43B279J`
- size: 111,491,792 bytes
- SHA-256: `bc5cf0dfb852de2f6a57e829c35688090ebc478e5ec104bb0196a34737e9d8dd`

FluidVoice 1.6.0 source was pinned at commit
`fba0d315a1120fb69fca9c69da20ce5319816705`, and FluidAudio at commit
`72625bbccf9f6c797a540a1f1cb66a4cb60753eb`, in the ignored local research cache to anchor
source-level observations. The v1.6.9 private Fluid Intelligence implementation was inspected
from signed application resources, artifact manifests, symbols/strings, model metadata, and a
functional local run. Where only v1.6.0 source is available, this note says so rather than claiming
exact v1.6.9 source parity.

## Complete observed path

```text
AVAudioEngine microphone input
  -> arithmetic-mean channel downmix
  -> linear-interpolation resample to mono Float32 16 kHz
  -> complete buffered capture on Stop
  -> Parakeet TDT 0.6B v2 Core ML transcription
  -> FluidVoice filler-word removal
  -> optional custom-dictionary substitutions / word metadata
  -> trim and pass raw transcript as `{transcript}` to Fluid-1
  -> deterministic local generation with bundled system prompt + model chat template
  -> strip leading thinking markup
  -> optional FluidVoice GAAV formatting
  -> continuous-dictation casing/spacing
  -> insertion into the active target
```

The capture tap uses a 4,096-frame buffer at the hardware input format. Multichannel samples are
averaged and linearly resampled to 16,000 Hz. The source path does not apply amplitude
normalization or voice-activity detection before final ASR. Captures shorter than one second are
zero-padded for the recognizer. FluidVoice submits the complete stopped capture rather than
shipping partial hypotheses through the final cleanup path.

### Speech recognition

The active UI choice and preferences identify **Parakeet TDT v2**. The only installed STT artifact
found is:

`~/Library/Application Support/FluidAudio/Models/parakeet-tdt-0.6b-v2-coreml`

It occupies about 443 MB and contains compiled Core ML preprocessor, encoder, decoder, and joint
decision models plus vocabulary/config files. Important observed characteristics are:

- 16 kHz Float32 mono input;
- 15-second / 240,000-sample model windows;
- a 128-bin mel frontend and a 1,024-wide encoder;
- 6-bit-palettized encoder storage, with FP16 recurrent decoder/joint components;
- v2 blank token 1,024 and duration bins 0 through 4;
- greedy TDT joint decoding, at most 10 symbols per step and 150 tokens per chunk;
- roughly 14.88-second long-audio windows with 2-second overlap and token/timestamp merging; and
- SentencePiece reconstruction by joining tokens, replacing `▁` with spaces, and trimming.

Representative installed SHA-256 identities:

| Component | SHA-256 |
| --- | --- |
| Encoder weights | `4adc7ad44f9d05e1bffeb2b06d3bb02861a5c7602dff63a6b494aed3bf8a6c3e` |
| Decoder weights | `27d26890221d82322c1092fd99d7b40578e435d5cf4b83c887c42603caf97aba` |
| Joint model weights | `ca22a65903a05e64137677da608077578a8606090a598abf4875fa6199aaa19d` |
| Preprocessor weights | `a5f7df6c7f47147ae9486fe18cc7792f9a44d093ec3c6a11e91ef2dc363c48dc` |
| Vocabulary | `57019fe3c745772ca83a1b048a4bb951cd51329504ea33d4d83316b96e279a97` |

FluidAudio source identifies the repository as
`FluidInference/parakeet-tdt-0.6b-v2-coreml`; that source does not pin a repository revision. This
Apple-only 0.6B Core ML model is not the project's 110M `parakeet.cpp` GGUF and should not be used
as evidence about the Android artifact's size, speed, or quality.

The 1.6.0 UI/source also exposes or references Parakeet v3, Parakeet Flash, Cohere, Nemotron
offline/streaming, Apple Speech, Whisper sizes, and Qwen beta choices. Newer binary registry
strings contain additional variants. These are selectable or historical registry entries, not
evidence that their weights are installed: only Parakeet TDT v2 was present locally.

### Transcript preprocessing

After ASR, FluidVoice first removes its configured filler words. The v1.6.0 default list is:

`um`, `uh`, `er`, `ah`, `eh`, `umm`, `uhh`, `err`, `ahh`, `ehh`, `hmm`, `hm`, `mm`, `mmm`,
`erm`, `urm`, and `ugh`.

It then applies word-boundary custom-dictionary substitutions and related vocabulary metadata when
enabled. The owner's dictionary contents are device-specific personal data and are deliberately
not recorded here. The resulting transcript is trimmed before cleanup. If cleanup fails,
FluidVoice falls back to this preprocessed transcript.

### Fluid-1 prompt and input rendering

FluidVoice 1.6.9 bundles its active system prompt at:

`FluidIntelligence_FluidIntelligenceCore.bundle/Contents/Resources/Prompts/fluid1_dictation_default.md`

Observed prompt identity:

- registry profile: `fluid1.dictation.default`
- registry version: `2026-05-20.1`
- user template: exactly `{transcript}`
- bundled prompt size: 4,945 bytes
- bundled prompt SHA-256:
  `e542001e392bb201fd975c7981bdfbf27833c07d0468b181c24f12db1278037a`

The system prompt instructs the model to emit cleaned text only and covers self-correction,
number/time/currency and spoken-punctuation transforms, explicit Markdown/list formatting,
filler and stutter cleanup, spelling hints, narrow ASR homophone repair, command scope, quote
delimiters, and in-place reference edits. This summary is sufficient for provenance; the complete
proprietary prompt is retained only in the ignored local cache.

The old GGUF embeds a Gemma 4 tokenizer chat template. For one system message and one user
transcript, the rendered token text is structurally:

```text
<bos><|turn>system
SYSTEM_PROMPT<turn|>
<|turn>user
TRANSCRIPT<turn|>
<|turn>model
```

The new MLX artifact supplies `chat_template.jinja` and tokenizer configuration beside its
weights. The FluidVoice helper receives the model directory, system-prompt file, raw text, and
generation limit, and can also load the bundled MTP drafter.

### Cleanup output processing

The Fluid Intelligence runtime includes a leading-thinking-markup stripping step before returning
text. FluidVoice then applies its optional GAAV formatting preferences (including trailing-period
and initial-case behavior) and continuous-dictation spacing/casing before insertion. These final
surfaces can therefore differ from raw Fluid-1 output. Local Flow evaluations must preserve and
review raw model output independently; postprocessing or fallback cannot turn an unsafe raw result
into a deployment candidate.

## Cleanup artifacts found

### Preserved GGUF baseline

The pre-update model remains available in the ignored project cache as:

`.cache/fluidvoice-reverse/weights/fluid-1-v1.6.0-q4_k_m.gguf`

- installed filename: `fluid-1-q4_k_m.gguf`
- size: 3,427,878,144 bytes (3.19 GiB)
- SHA-256: `38fafbfaab6504b7ad125523f0b993d52112c3cc7e20543f4929e619022bc7d8`
- format: GGUF `Q4_K_M`
- architecture/name: Gemma 4, `Merged 50`
- parameter count: approximately 4.6B
- blocks / embedding width: 35 / 1,536
- declared context: 131,072; sliding window: 512
- attention heads / KV heads: 8 / 1
- tokenizer: Gemma 4, BOS 2, EOS 106, PAD 0
- historical pinned model revision: `660dda67dfab6ab968662c59078f6721310a79f5`

The source download endpoint was
`altic-dev/FluidIntelligence/models/fluid-1-q4_k_m.gguf` at that fixed revision. The ignored copy
was hash-checked after preservation.

The reproducible personal smoke command is:

```bash
scripts/run-fluidvoice-fluid1-baseline.sh \
  --backend gguf \
  --text 'um send the package on tuesday' \
  --max-tokens 64
```

With the bundled prompt, embedded template, greedy sampling, and local `llama-completion`, it
returns only:

```text
Send the package on Tuesday.
```

This is an ad hoc functional smoke input, not a project evaluation case and not quality evidence.

### FluidVoice 1.6.9 MLX baseline

FluidVoice 1.6.9's signed `FluidIntelligenceMLXArtifacts.json` pins:

- repository/revision: `altic-dev/FluidIntelligence@42346eacdd0c2ff0d82f65c28dac9f5c767741b2`
- main directory: `fluid-1-nvfp4-mlx`
- format/architecture: 4-bit NVFP4 Gemma 4, matching the 35-layer, 1,536-wide text architecture
  and 131,072-token declared context of the prior model
- main weights: 3,550,633,590 bytes, SHA-256
  `8211486bf8299f4e59e691c12d90fac1a264fc27a93df646d927d46fc4f25b51`
- MTP drafter directory: `gemma-4-E2B-it-qat-assistant-bf16-mlx-mtp`
- MTP weights: 156,516,674 bytes, SHA-256
  `0c812de6644d0f34ec9d75ee78f2799e31d0f3b781f823920f80db70f8e7fccd`
- signed total: 3,771,739,114 bytes, matching the UI's rounded 3.77 GB display
- artifact-manifest SHA-256:
  `955151003cdc02df81f4183190be49c7ad4c6739db7e7516b79f30dfc61f89aa`

The app's Apple-MLX inference helper is 36,431,632 bytes with SHA-256
`67816c7782a5d99877440fe9d359ec841d1284c66235cc4ecec32a1f08ae2efd`. The helper exposes local
status, warmup, run, benchmark, and batch modes; it supports a system-prompt file and optional MTP
draft decoding with block size 6.

FluidVoice completed and configured the eight-file main model, totaling 3,583,024,557 bytes. The
live install and ignored backup both match all eight manifest byte counts and SHA-256 values. The
backup is:

`.cache/fluidvoice-reverse/weights/fluid-1-nvfp4-mlx`

The helper, Fluid Intelligence resource bundle, and MLX `default.metallib` bundle are preserved
under `.cache/fluidvoice-reverse/v1.6.9/runtime/`, making the ignored snapshot runnable without
relocating the signed application. The optional eight-file MTP drafter accounts for the remaining
188,714,557 manifest bytes but was not downloaded by the app in this session; only its signed
filenames, sizes, and hashes are known locally. The runner detects and uses it if it is later
present, but does not require it.

The runner's MLX mode is:

```bash
scripts/run-fluidvoice-fluid1-baseline.sh \
  --backend mlx \
  --text 'um send the package on tuesday' \
  --max-tokens 64
```

The independently preserved helper and main model return `Send the package on Tuesday.` for the
same ad hoc input, followed by helper timing/token key-value lines. One measured preserved-helper
run reported 5,706 ms total, 5,552 ms TTFT, 6 generated tokens, and 41.99 tokens/s. This is a
functional reproducibility check, not a benchmark campaign.

## What the “100K+” claim does and does not tell us

FluidVoice displays the exact marketing sentence:

> Trained on 100K+ dictation data points to polish your words.

It is present in the v1.6.0 source onboarding view and remains a useful scale datum for our own
fine-tuning planning. It is a vendor-reported claim, not a disclosed dataset card. “Data points”
does not establish paired raw/clean examples, unique utterances, human review, speaker/domain
coverage, source licenses, train/dev/test separation, filtering, augmentation, or whether the
count includes synthetic variants. It therefore cannot validate provenance or justify copying a
100K target mechanically.

Local Flow's current 135,503-row Sotto-derived training stream is numerically in the same broad
order of magnitude, but the counts are not directly comparable. Task fit, correction and
formatting coverage, semantic preservation, deduplication, source diversity, and reviewed dev
evidence are more informative than row count alone. The claim is retained as a scale heuristic,
never as training data or evidence that Fluid-1's private corpus is available locally.

## Pixel applicability

Neither discovered FluidVoice cleanup artifact is a practical Pixel 7 drop-in:

- the old GGUF alone is 3.19 GiB and uses a roughly 4.6B-parameter Gemma 4 architecture;
- the new signed MLX manifest totals 3.77 GB, of which the complete preserved main model is
  3.58 GB and the optional undownloaded MTP drafter is 188.7 MB;
- the new helper and weights target Apple MLX, not Android; and
- device deployment would also require KV/cache memory, runtime code, STT, and app headroom.

These assets are worthwhile as owner-local Mac behavioral baselines, but they do not replace the
project's Pixel-sized model search. No conversion, quantization, fine-tuning, or Android bundling
should be attempted without both explicit license permission and a separately reviewed technical
plan.

## Public provenance references

- FluidVoice source: <https://github.com/altic-dev/FluidVoice>
- FluidVoice releases: <https://github.com/altic-dev/FluidVoice/releases>
- FluidVoice product page: <https://altic.dev/fluid>
- Fluid Intelligence repository: <https://huggingface.co/altic-dev/FluidIntelligence>
- Historical pinned model card:
  <https://huggingface.co/altic-dev/FluidIntelligence/blob/660dda67dfab6ab968662c59078f6721310a79f5/README.md>

## Remaining uncertainty

- FluidVoice 1.6.9's complete private Swift source was not available; postprocessing details beyond
  the public 1.6.0 source and current binary symbols should be treated as observed behavior, not a
  source reconstruction.
- Registry strings show more model names than installed artifact directories. Screenshots can help
  map exact current UI labels, but they are not needed to preserve or run the active assets.
- The Fluid-1 private training corpus, preprocessing code used to create it, and its provenance are
  not shipped with the inference artifacts. The `100K+` sentence is the only located scale claim.
- Personal custom-dictionary contents and transcripts were deliberately excluded from inspection
  records.
