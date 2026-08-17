# Cleanup model candidate research

Verified: 2026-08-17

## Conclusion

Do not replace Liquid LEAP in the Android app until a candidate first passes the fixed cleanup
corpus outside the app. The bounded screen proposed here is now complete: Granite 4.0 H 350M,
Qwen3-0.6B, Gemma 3 270M, Qwen3.5-0.8B, and Gemma 3 1B all failed the semantic safety or explicit
self-correction gate. Therefore none advances to Android runtime work.

The pre-test runtime recommendation remains useful if a future model passes quality: start with
LiteRT-LM for a supported LiteRT artifact and llama.cpp for GGUF portability. The next model search
should prioritize a task-specific dictation-cleanup fine-tune, not another generic tiny chat model.
Full results: `docs/evaluation/results/2026-08-17-cross-family-cleanup-screen.md`.

Follow-up outcome: the public VoiceInk Qwen3.5-2B task-tuned Q4_K_M checkpoint was also screened
with its exact author prompt. It reached only 2/10 exact corrections and produced ten critical
outputs, including six retained superseded edits, three meaning/fact changes, and one followed
instruction. It is rejected; see
`docs/evaluation/results/2026-08-17-voiceink-qwen35-2b-q4km.md`.

The latest Qwen3.5-0.8B is eligible, but it is not automatically the strongest candidate: its
official non-thinking instruction-following result is weaker than several older or differently
trained small models, its text model comes from a multimodal family, and its Android path is
currently less direct than Qwen3-0.6B. It belongs in the second wave, not at the front merely
because it is newest.

## What comparable products actually use

| Project | Verified cleanup approach | Lesson for this project |
|---|---|---|
| [FluidVoice](https://github.com/altic-dev/FluidVoice) | Its optional local “Fluid Intelligence” model/runtime is private and about 3.5 GB. The open repository does not disclose the model or prompt. | It is evidence for a specialized cleanup component, not evidence for a generic tiny model. It is currently macOS-only. |
| [Lexo](https://play.google.com/store/apps/details?id=com.lexo.keyboard) | Closed-source Android keyboard. Its listing identifies Parakeet and a small Qwen2.5 model, but not exact variants, runtime, prompt, or whether every advertised cleanup operation is performed by Qwen. | Qwen2.5-0.5B is not a verified cleanup baseline. Public developer discussion emphasizes next-word prediction. |
| [localVoice](https://github.com/lighteningAB/localVoice) | Whisper plus Qwen3-1.7B Q4_K_M/llama.cpp for memo cleanup. The IME deliberately commits raw Whisper output and skips the LLM. | A roughly 1 GB model is workable for background memo cleanup, but inline keyboard latency/lifecycle is a different bar. |
| [Sasayaki](https://github.com/pluja/sasayaki) | Android client calls OpenAI-compatible servers. The maintainer fine-tunes Qwen3.5-2B on synthetic dictation and has explicit post-processing evals. | Task-specific training and a held-out cleanup eval matter more than generic benchmark rank. It also tests the failure where a model answers dictated questions. |
| [Outspoke](https://github.com/minburg/outspoke) | Fully local Android IME with Parakeet. Cleanup is deterministic: fillers, stutters, phrase loops, punctuation, spacing, and capitalization; word correction uses dictionary plus bigram data. | Establish a safe mechanical baseline. It may handle most common cases at near-zero latency and route only ambiguous corrections to an LLM. |
| [Dictate Keyboard](https://github.com/DevEmperor/DictateKeyboard) | Local sherpa-onnx STT; rewriting is cloud/self-hosted. Its format prompt preserves wording, uses examples, handles empty output, and detects prompt echo. | Copy the conservative prompt/eval failure checks, not its network architecture. |
| [VoiceInk Qwen3.5-2B fine-tune](https://github.com/hourliert/VoiceInk-Qwen3.5-2B-FT/blob/master/docs/BLOG_POST.md) | A task-tuned Qwen3.5-2B reportedly beats generic Qwen3.5 models up to 35B-A3B on a 161-case held-out dictation-cleanup set. These are the project author's task-specific, LLM-judged results. | If zero-shot small models fail, fine-tuning is the evidence-backed next move; adding more prompt text is not. |

No audited open Android project found here implements the complete target combination of local STT,
a small local generative cleanup model, and inline IME insertion. That means model/runtime claims
from adjacent projects are useful priors, not substitutes for Pixel 7 measurements.

## Candidate order

| Order | Candidate | Quantized artifact | Why it is in the test | Main caveat |
|---:|---|---:|---|---|
| 1 | [IBM Granite 4.0 H 350M](https://huggingface.co/ibm-granite/granite-4.0-h-350m) | [Q4_K_M GGUF, 223 MB](https://huggingface.co/ibm-granite/granite-4.0-h-350m-GGUF) | Apache-2.0, on-device positioning, strong small-model instruction following, architecture-diverse after three LFM failures. | Requires llama.cpp; hybrid Mamba2 performance must be measured on Android. |
| 2 | [Qwen3-0.6B](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF) | [LiteRT no-think INT4, about 329 MiB](https://huggingface.co/litert-community/Qwen3-0.6B-int4) | Apache-2.0 and the lowest-friction current Android path. The no-think export avoids reasoning text and has a short 1,280-token cache suitable for cleanup. | Qwen warns pure greedy decoding can repeat; use bounded seeded sampling and a hard output cap. |
| 3 | [Gemma 3 270M IT](https://huggingface.co/google/gemma-3-270m-it) | [QAT Q4_0 GGUF, 241 MB](https://huggingface.co/ggml-org/gemma-3-270m-it-qat-GGUF) | Tiny control and an interesting task-specific fine-tuning base. | Only about 100M parameters are transformer blocks; official IFEval is 51.2. Gemma terms are gated/custom. |
| 4 | [Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B) | [Q4_0 GGUF, 563 MB](https://huggingface.co/ggml-org/Qwen3.5-0.8B-GGUF) | Latest sub-1B Qwen, Apache-2.0, multilingual, and explicitly positioned for task-specific fine-tuning/prototyping. | Newer hybrid architecture, less direct Android package, and official non-thinking IFEval 52.1. |
| 5 | [Gemma 3 1B IT](https://huggingface.co/google/gemma-3-1b-it) | [LiteRT-LM INT4, about 584 MB](https://huggingface.co/litert-community/Gemma3-1B-IT) | Best supported mobile-oriented larger fallback; official IFEval 80.2 and official LiteRT CPU/GPU path. | Exactly 1B rather than sub-1B, gated Gemma terms, and materially larger memory/storage budget. |

Optional controls, not first-wave integrations:

- LFM2-700M has good author-reported instruction scores, but it is highly correlated with the LFM
  family already rejected on this exact task.
- SmolLM2-360M explicitly trained on rewriting, but its official instruction-following score is
  too low to justify Android integration before the candidates above.
- Qwen2.5-0.5B is useful only as a Lexo-adjacent control. There is no public evidence that Lexo
  uses it as the complete transcript cleanup engine.

## Runtime decision

Start with [LiteRT-LM 0.16.0](https://github.com/google-ai-edge/LiteRT-LM) for Qwen3-0.6B on the
Pixel. It has an official Kotlin API, Maven artifact, CPU and OpenCL GPU backends, and a ready-made
no-think model. Do not assume GPU or NPU performance: Pixel Tensor G2 has no promised LiteRT NPU
path, so CPU and GPU are both measurements, not conclusions.

Use [llama.cpp](https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md) for the portable
GGUF comparison and Granite. It has broad model support and a dependable ARM CPU path, but its
official Android sample is source-integrated rather than a stable Maven AAR. MLC, ExecuTorch,
ONNX Runtime GenAI, and maintenance-only MediaPipe LLM inference add export/build/runtime risk that
does not help the first comparison.

## Benchmark gate

### Stage 1: fixed-corpus quality screen

1. Freeze the existing 24 cases and prompt. Do not tune a separate prompt for every candidate.
2. Add a fresh held-out set before any fine-tuning; the original 24 cases have already influenced
   prompt and guardrail work.
3. Run Granite H 350M, Qwen3-0.6B no-think, and Gemma 270M with the same input, short context,
   deterministic/seeded decoding, and input-derived hard output cap.
4. Score raw output and post-guardrail output separately with the existing scorer.
5. Reject immediately on any polarity/number/name/uncertainty loss, answered instruction, invented
   fact, or failed explicit self-correction. Exact match is secondary to semantic safety.

### Stage 2: Pixel 7 performance screen

Only quality survivors advance. For each survivor, use a release build and record:

- model bytes and APK/runtime overhead;
- cold initialization and warm reuse;
- prompt/prefill throughput, TTFT, decode throughput, and total cleanup latency;
- peak PSS/RSS and simultaneous stability with Moonshine loaded;
- CPU versus GPU for LiteRT Qwen;
- at least five warmed repetitions plus thermal/battery drift;
- airplane-mode reuse after model setup.

The initial interactive target remains sub-second warm cleanup when possible, but semantic failures
are unconditional no-go results regardless of speed.

## Likely product architecture

Benchmark an Outspoke-style deterministic cleaner alongside the LLMs. Use it for high-confidence
filler removal, exact repeat collapse, spacing, capitalization, punctuation, and explicit correction
markers. Skip generation for already-clean/short inputs. Route only ambiguous self-corrections or
complex disfluencies to the model, and preserve raw text whenever a safety check fails. This reduces
latency, memory activity, and the number of opportunities for meaning-changing generations.
