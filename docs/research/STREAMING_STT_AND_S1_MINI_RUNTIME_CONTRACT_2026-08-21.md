# Streaming STT and S1-mini runtime contract

Date checked: 2026-08-21

This note records the publisher guidance that affects the ordinary local dictation path. It is an
integration contract, not new STT or cleanup quality evidence.

## Parakeet Realtime EOU 120M v1

Sources:

- NVIDIA model card: <https://huggingface.co/nvidia/parakeet_realtime_eou_120m-v1>
- converted GGUF collection: <https://huggingface.co/mudler/parakeet-cpp-gguf>
- pinned runtime: `parakeet.cpp` `v0.5.0`, commit
  `1bfbebfaaf493866f49597cd3b7901959d395c60`

Relevant publisher/runtime facts:

- The model is a 120M-parameter, English-only, cache-aware streaming FastConformer RNNT with
  end-of-utterance (`<EOU>`) output. It expects single-channel 16 kHz audio and at least 160 ms of
  input.
- It does not produce punctuation or capitalization. S1-mini therefore remains responsible for
  those written-text transformations after the final transcript is available.
- NVIDIA reports 80–160 ms model latency, 9.30% average WER over its listed normalized streaming
  benchmark, and EOU latency of 160/280/320 ms at p50/p90/p95 on TTS DialogStudio audio with three
  seconds of appended silence. Those are publisher measurements on NVIDIA inference hardware and
  are not Pixel claims.
- `parakeet.cpp` 0.5.0 exposes stateful `stream_begin`, `stream_feed_json`,
  `stream_finalize_json`, and `stream_free` C APIs. A stream carries encoder and RNNT decoder state;
  each feed returns only newly finalized text plus EOU/EOB events, and finalization flushes the
  remaining audio tail.
- The converted collection recommends F16. It labels WER-versus-NeMo as **not measured** for every
  published Realtime EOU quantization, including the selected Q4_K file. The Q4 integration is
  therefore provisional until direct Pixel dictation quality, responsiveness, memory, thermal,
  and power checks are complete.

Pinned development artifact (kept outside Git):

- file: `realtime_eou_120m-v1-q4_k.gguf`
- bytes: `129133984`
- SHA-256: `ac9109d0e422bd8aafa899c0f58e1938f4a2846838797a29c04f6a8729033c3c`

The NVIDIA source model is under the NVIDIA Open Model License, while the converted GGUF
collection declares CC-BY-4.0. Before redistributing or bundling the GGUF, retain applicable
notices and reconcile the source and conversion terms. Current app-private sideloading is a
development workflow, not a release package.

## S1-mini v1 by Superwhisper

Source: <https://huggingface.co/superwhisper/s1-mini/tree/v1>

Pinned local model-card evidence:

- revision: `9ee216462e64daa21d6ce07c8a3c343e1ce43261`
- README SHA-256: `b22a4ce83218b21af2e71c7e0d28b686239a0028299cdbc87e4238b2568cfd97`
- license SHA-256: `d956d2d305a0639211c9cbde71501accb0e1474cc9ddf79a47820a522aff6f98`

The runtime-relevant contract is:

1. Treat S1-mini as an English-only transcript normalizer, not a chat model. Its expected input is
   raw ASR text, usually lowercase and unpunctuated.
2. Preserve the exact publisher system prompt and a trained control line. This app fixes
   `[Styling: semi-formal] [Structure: prose] [Context: general]`. Unsupported values or prompt
   rewrites can hallucinate or garble output. All supported styling/structure/context combinations
   were trained, but changing product controls needs explicit UI/product work rather than an
   improvised prompt.
3. Disable Qwen3 thinking with the template's `enable_thinking=false` behavior. The empty think
   block in the assistant prefix is part of the trained input format; a generic reasoning-budget
   substitute is not equivalent.
4. Use greedy decoding (`temperature = 0`) and set each pass's output ceiling to
   `ceil(1.3 * raw_input_tokens) + 32` (implemented with the equivalent integer ceiling).
5. Keep each pass below roughly 1,000 input tokens and chunk longer completed transcripts at
   sentence boundaries. Local Flow counts tokens with the loaded S1 tokenizer, greedily packs the
   final transcript to at most 1,000 raw tokens per pass, prefers Parakeet EOU and punctuation
   offsets, and falls back to whitespace only when one unpunctuated span is itself too long.
6. Do not call S1-mini on streaming partials. The entire final STT result is available before
   chunking; all cleanup passes then run sequentially and their outputs are rejoined in source
   order. This preserves cross-sentence context up to the model-card ceiling without sending
   intermediate hypotheses.
7. Plain text is normal for the selected prose/general controls. Other trained controls may return
   Markdown bullets (`Structure: lists`) or blank-line email layout (`Context: email`).
8. Filler-only input can validly produce an empty string. The publisher behavior does not override
   this personal-use app's runtime policy: blank or token-capped output falls back to raw text;
   every other sanitized output is used and remains visible for review.

S1-mini's license is described as Apache 2.0 plus a naming clause. Distribution must retain the
license and attribution and preserve the exact name `S1-mini` by `Superwhisper`; material changes
should be identified. Confirm the term against the intended release packaging before bundling
weights.

## Pipeline ordering

```text
Start -> AudioRecord -> cache-aware Parakeet stream -> live raw transcript display
Stop  -> stop microphone -> drain queued audio -> flush Parakeet tail -> final raw transcript
      -> tokenize/chunk final transcript -> S1-mini pass(es) -> join -> insert/display
```

EOU events are used only as preferred final-cleanup boundaries. V1 still uses explicit Start/Stop;
an EOU event does not stop recording or invoke cleanup by itself.
