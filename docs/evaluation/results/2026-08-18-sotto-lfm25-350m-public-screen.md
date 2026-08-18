# Sotto LFM2.5-350M public-checkpoint screen

Date: 2026-08-18

## Decision

Do not integrate or quantize the public Sotto checkpoint for Android yet. It is materially better
at transcript cleanup than the generic LFM2.5-350M baseline and it transcribed all 17 dictated
questions/commands instead of answering them, but it still made six clear meaning/protected-text
errors and missed seven important self-corrections. Those failures remain product-relevant even
when harmless wording, punctuation, contractions, and removal of disposable conversational
lead-ins are ignored.

## Artifact and runtime

- Model: `juanquivilla/sotto-cleanup-lfm25-350m`
- Immutable revision: `6df6f019170b8b5533c047b901886a51750a965`
- License label: MIT
- Artifact: BF16 `model.safetensors`, 708,984,464 bytes
- Weight SHA-256: `6e96eeffdcdd60f881e13eb2019b339b39d1a74951446f062e7e641a82f6422e`
- Config SHA-256: `37b433e53d0f903cc274563a8a9c5f53c69eeafe60fcadac19ac272d6e0a5387`
- Tokenizer SHA-256: `4905ab82b2cfc25e0c88adc8f4eeffe759c57c5626312b30b0aaeaf8ad3379bc`
- Host: RTX A6000, Torch 2.6.0+cu124, Transformers 5.14.1, BF16
- Prompt: publisher-native `### Input:\n{raw}\n\n### Output:\n`
- Decoding: greedy, repetition penalty 1.05, publisher output cap of at least 900 tokens, and the
  publisher's first-`###` delimiter parser

The publisher currently provides full BF16 and Apple-only MLX 4/5-bit variants, not a directly
deployable Pixel artifact. Android conversion and Pixel timing were intentionally skipped after
the raw quality failure.

## Results

| Metric | Result |
|---|---:|
| Retired diagnostics | 69 |
| Strict exact | 42/69 |
| Preservation anchors | 147/163 |
| Explicit self-corrections exact | 2/10 |
| Dictated questions/commands not answered | 17/17 |
| Empty outputs / output-cap hits | 0 / 0 |
| Guardrail flags | 19/69 |
| Concurrent A6000 median TTFT / total | 36.6 ms / 174.5 ms |

Strict exactness is retained for comparison, but it is not the rejection basis. Deleting a casual
lead-in such as “Yeah” or “Well,” changing punctuation, or using a meaning-preserving contraction
was treated as acceptable during the practical audit.

The six clear meaning/protected-text failures were:

- `cleanup-007`: changed “I got the file” into the question “got the file?”;
- `cleanup-011`: changed `./gradlew :app:assembleDebug` into the invalid
  `./gradlew:app:assembleDebug`;
- `heldout-015`: removed the literal brackets from `[assistant]`;
- `heldout-019`: changed `€1,249.99` to `$1,249.99`;
- `heldout-026`: changed `git diff -- app/src/main` into `Git Diff --app/src/main`;
- `heldout-031`: changed the name `佐藤さん` to `Sandro`.

Seven additional correction cases retained a superseded day, recipient, action, deployment
target, or retry count (`cleanup-003`, `cleanup-004`, `cleanup-021`, `heldout-006`,
`heldout-007`, `heldout-038`, and `heldout-039`). The final choice was usually present, but leaving
both alternatives is precisely the ambiguity cleanup is meant to remove. Two more cases failed to
remove a direct repetition. `heldout-042` removed the old version correctly but retained redundant
correction wording, so it was not counted as a meaning error.

## Reproducibility

The local-only runner is `scripts/training/infer_sotto_lfm.py`; its recorded run-time SHA-256 was
`9ba457d0d34dce20c37fb46476342386bba291b88da048a041c269d45c5a1a5d`. Raw results, provenance,
and the downloaded weights remain outside Git under
`/data/rise/android_stt/runs/sotto-public-lfm25-350m-6df6f019/` and
`/data/rise/android_stt/models/sotto-cleanup-lfm25-350m-6df6f019/`.

| Artifact | SHA-256 |
|---|---|
| Seed results | `58c61850b4f3378827bfb477eab569963713d03824dc87176d383ead2ad88173` |
| Seed provenance | `f08fd7bd2e8806b8c210f53f1e0ba54dbc2ccb4cea5570b640ed6ac07d2c9e59` |
| Heldout-v1 results | `09df873ffbeb4c66a64389cf8dd7cbf870a809b8b84a057cf4f2b282f0251ca7` |
| Heldout-v1 provenance | `a068eaf214fbd7fa4016e9d2aa29e866c2606e22b749221c8d7fdfaf059685b2` |

The two corpora were generated concurrently on the A6000. The latency figures are therefore only
a host throughput observation, not a standalone latency benchmark or a Pixel prediction. Quality
generation was greedy and complete. The committed corpora are retired diagnostics; no blind-v2
surface was opened or used.

Publisher source: [Sotto LFM2.5-350M model card](https://huggingface.co/juanquivilla/sotto-cleanup-lfm25-350m/tree/6df6f019170b8b55333c047b901886a51750a965).
