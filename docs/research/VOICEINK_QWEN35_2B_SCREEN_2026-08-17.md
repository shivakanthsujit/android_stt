# VoiceInk Qwen3.5-2B task-tuned cleanup candidate

Verified: 2026-08-17

## Decision

The internal host quality probe is complete and is a strict no-go. It produced only 38/69 raw exact
outputs and 2/10 exact self-corrections, with six retained superseded edits, three meaning/fact
changes, and one followed instruction. Full results:
`docs/evaluation/results/2026-08-17-voiceink-qwen35-2b-q4km.md`.

Do not redistribute it, bundle it in the Android app, or use it as an automatic labeler. The
upstream Qwen3.5-2B weights are Apache-2.0, but the published fine-tune repository and Ollama
artifact do not currently state a license.

Even if it passes quality, its 1.19 GiB Q4 artifact is probably too large for the target inline
keyboard. A pass would establish that task-specific training works and make the model useful as a
reviewed teacher for a smaller 0.6B/0.8B checkpoint.

## Pinned artifact

- Author project: [VoiceInk-Qwen3.5-2B-FT](https://github.com/hourliert/VoiceInk-Qwen3.5-2B-FT)
- Published model: [hourliert/voiceink-qwen3.5-2b](https://ollama.com/hourliert/voiceink-qwen3.5-2b:latest)
- Format: merged GGUF, Q4_K_M, reported 1.88B text parameters
- Size: 1,274,396,352 bytes (about 1.19 GiB)
- SHA-256: `343721d889adcec76725373f51be207e6a980eec8411e4e6c553dd6c8329d175`
- Stable blob URL:
  `https://registry.ollama.ai/v2/hourliert/voiceink-qwen3.5-2b/blobs/sha256:343721d889adcec76725373f51be207e6a980eec8411e4e6c553dd6c8329d175`

No author-published Hugging Face adapter, safetensors checkpoint, or alternate GGUF quantization was
found. The GitHub repository contains the training/evaluation pipeline but gitignores weights and
datasets.

## Training and prompt contract

The author fine-tuned `unsloth/Qwen3.5-2B` with text-only, completions-only LoRA SFT. The adapter
uses rank 32 and alpha 64 across language/attention/MLP layers, then is merged and exported as
Q4_K_M. See the author's
[`finetune.py`](https://github.com/hourliert/VoiceInk-Qwen3.5-2B-FT/blob/master/src/training/finetune.py).

A faithful screen must not reuse this project's generic cleanup prompt. It must:

1. Use the author's exact pinned
   [`docs/VOICEINK_PROMPT`](https://github.com/hourliert/VoiceInk-Qwen3.5-2B-FT/blob/master/docs/VOICEINK_PROMPT),
   including the outer `<SYSTEM_INSTRUCTIONS>` tags.
2. Send the raw text exactly as `<TRANSCRIPT>\n{raw}\n</TRANSCRIPT>`.
3. Use the Qwen3.5 chat template with non-thinking runtime mode; do not append `/no_think`.
4. Optionally stop on literal `</think>` because the author observed rare reasoning-tag leakage.

Optional context fields exist, but the fixed text-only screen omits them so every model receives
only the transcript being evaluated.

## Host launch

After downloading and verifying the artifact, launch the local server with:

```bash
llama-server \
  --model build/models/voiceink-qwen3.5-2b-q4_k_m.gguf \
  --alias voiceink-qwen3.5-2b \
  --ctx-size 16384 \
  --gpu-layers all \
  --flash-attn on \
  --jinja \
  --reasoning off \
  --host 127.0.0.1 \
  --port 18080
```

The project screening wrapper records the artifact checksum, corpus checksums, llama.cpp version,
server command, fixed decoding parameters, results, and scorer output. Preserve raw responses even
when Android-equivalent guardrails fall back.

## Acceptance interpretation

- Passing the old 24+45 cases is encouraging but not proof of generalization; both sets are now
  development/regression evidence.
- Manually audit every non-exact response plus all correction, must-not-answer, and adversarial
  cases.
- Any changed meaning, obeyed dictation, invented content, or unsafe correction is a no-go.
- If quality passes, use this checkpoint as an upper-bound/teacher while the leakage-isolated
  sub-1B training plan and blind-v2 set are built.
- If quality fails, classify the failure and use the author's training pipeline as evidence, not
  the checkpoint itself.

## Licensing blocker

The upstream [Qwen3.5-2B license](https://huggingface.co/Qwen/Qwen3.5-2B/blob/main/LICENSE) is
Apache-2.0. That does not automatically license the author's fine-tuned derivative. Internal
evaluation can proceed, but distribution requires explicit clarification from the fine-tune author.
