# Cleanup base-model reassessment

Date: 2026-08-17
Status: research decision for the direct-source experiment

## Decision

Keep `Qwen/Qwen3-0.6B` as the base for the first four direct-source adapters and use the fixed BF16
LoRA rank-16 recipe. This is the easiest reproducible launch because the repository already pins
its revision, chat-template behavior, LoRA modules, generic baseline, inference path, and mobile-size
artifact. Changing the base now would confound the intended dataset comparison.

If Sotto produces useful learning but appears capacity-limited, compare the best data recipe on
`Qwen/Qwen3.5-0.8B` next. It is the strongest current sub-1B candidate on capability and has an
official base checkpoint whose control tokens are explicitly designed to permit LoRA PEFT without
tuning the unusually large embedding table. Its hybrid Gated DeltaNet/full-attention architecture,
multimodal wrapper, and newer library path still make it a higher-risk first trainer than Qwen3.

Do not start with a full-parameter tune. A 0.6B or 0.8B full BF16 tune fits the RTX A6000, but LoRA
is faster to iterate, yields small resumable/mergeable artifacts, and preserves the controlled
dataset comparison. If the best direct-source LoRA plateaus, run a separately named matched
adaptation study: rank-16 LoRA, higher-capacity/all-linear LoRA, then full BF16 fine-tuning. Full
fine-tuning is especially reasonable for a later 270M/350M candidate, where its cost is much lower.

## Candidate comparison

| Candidate | Relevant evidence | Adaptation and deployment assessment | Place in queue |
|---|---|---|---|
| Qwen3 0.6B | Standard dense causal architecture; Apache-2.0; existing project baseline was 25/45 exact but unsafe zero-shot | Lowest training integration risk; existing prompt, targets, revision, and LoRA module list; plausible Q4 mobile size | First, fixed for source comparison |
| Qwen3.5 0.8B / 0.8B-Base | Current sub-1B Qwen generation; 0.8B language model, 248K vocabulary, hybrid linear/full attention; Apache-2.0; project zero-shot was 17/45 | Official base card explicitly supports LoRA-style PEFT without embedding tuning; likely higher ceiling, but model class and hybrid LoRA targets require dedicated smoke validation | First stronger-base follow-up |
| Gemma 3 1B IT | Strongest project generic screen at 32/45 exact, but three critical unsafe outputs | Mature Transformers/PEFT/TRL and official QLoRA guidance; gated Gemma terms and different prompt semantics add friction; Q4 artifact was 806 MB | Quality-oriented comparison after Qwen3.5 if needed |
| Gemma 3 270M IT | Designed by Google for rapid task-specific tuning and on-device use; project zero-shot was only 3/45 | Easiest/cheapest Gemma to tune, but measured capability is too low to displace Qwen first | Efficiency ablation, not first run |
| Gemma 4 E2B | Latest Gemma family, but 2.3B effective and 5.1B including embeddings | Official tuning support exists, but total size and multimodal architecture are outside this sub-1B/mobile cleanup experiment | Exclude |
| LFM2.5 350M | Latest small text LFM; 28T-token training; official strong instruction benchmarks and very fast mobile claims; project generic cleanup was a semantic no-go | First-party TRL/Unsloth LoRA recipes and GGUF/ONNX/LEAP paths are attractive; hybrid convolution/attention LoRA targeting and LFM Open License add integration/release work | Deployment-speed wildcard after the data experiment |
| LFM2.5 1.2B Instruct | Stronger LFM and measured Android runtime, but project cleanup remained unsafe and slow | Official LoRA support, but above target size and already rejected as an automatic generic cleaner | Exclude from sub-1B base comparison |

General-purpose benchmark scores are only capability priors. Selection remains based on raw
project semantic safety, correction success, exactness, and only then latency. None of the vendor
benchmarks qualifies a model for cleanup.

## Primary sources checked

- Qwen3.5 0.8B and 0.8B-Base official Hugging Face model cards, including architecture, license,
  and LoRA-oriented control-token guidance.
- Qwen's official Qwen3 release for the 0.6B architecture and Apache-2.0 release.
- Google's Gemma 3 270M announcement, Gemma 3 model card, and official Transformers/TRL QLoRA
  guide.
- Google's Gemma 4 model card for current family sizes and effective versus total parameters.
- Liquid AI's official LFM2.5-350M and LFM2.5-1.2B cards for architecture, benchmark, mobile,
  format, license, and fine-tuning support.

Web sources were consulted on 2026-08-17. Exact model revisions must be pinned and reverified before
each new base enters a training configuration.
