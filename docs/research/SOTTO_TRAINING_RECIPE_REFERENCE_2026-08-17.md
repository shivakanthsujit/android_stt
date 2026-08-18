# Sotto training-recipe reference

Date checked: 2026-08-17

## Source status

No formal Sotto paper or archival preprint was found in the publisher's official dataset/model
links or in a targeted paper search. The publisher instead calls the Hugging Face model card the
"full training research document." Treat the material below as an evolving publisher model-card
record, not a peer-reviewed paper recipe. Historical cards are linked by immutable commit because
the current production card has changed repeatedly.

Primary sources:

- [Pinned transcript-cleanup dataset](https://huggingface.co/datasets/juanquivilla/sotto-transcript-cleanup/tree/183cc8fd58532f13fa192980185214de1bcd5acc)
- [Initial two-stage training card](https://huggingface.co/juanquivilla/sotto-cleanup-lfm25-350m/commit/1c9bfccbfa5ac3dd1b962c8a26248b34283af610)
- [Detailed full-fine-tuning card](https://huggingface.co/juanquivilla/sotto-cleanup-lfm25-350m/blob/69428acbdcaec008ce8b79096d762d0693c76912/README.md)
- [Detailed v23 SFT/GRPO card](https://huggingface.co/juanquivilla/sotto-cleanup-lfm25-350m/blob/15c2adb684a20577f84f8fe235471426974af494/README.md)
- [Current production/soup card](https://huggingface.co/juanquivilla/sotto-cleanup-lfm25-350m/blob/6df6f019170b8b55333c047b901886a51750a965/README.md)

## What Sotto published

There is no single stable recipe. The official record describes an evolving LFM2.5-350M lineage:

1. An early LoRA SFT card reported rank 64, 124K pairs, three epochs with early stopping, an RTX
   4090, and about nine minutes. It did not publish learning rate, batch size, optimizer, warmup,
   maximum sequence length, LoRA alpha/dropout, or seed.
2. The initial two-stage full-tuning card later reported full fine-tuning of
   LFM2.5-350M-Base: stage 1 on 124K pairs at learning rate 1e-5 for three epochs, followed by one
   epoch on 14K concentrated hard-pattern examples at 2e-6.
3. A later detailed full-tuning card reported 143K samples, three epochs, microbatch 1 with eight
   gradient-accumulation steps, AdamW, BF16+TF32, cosine scheduling, and learning rate 2.5e-5 on
   one RTX 4090. Its training progression explicitly says that full fine-tuning improved over the
   earlier LoRA lineage.
4. The most complete reproducible SFT description is v23: full-parameter SFT of
   LFM2.5-350M-Base on 157,556 rows at learning rate 3e-5 for three epochs; microbatch 1,
   accumulation 8, cosine decay, 50 warmup steps, AdamW beta2 0.95, weight decay 0.01, BF16+TF32,
   packed 4,096-token context, and seed 42. It then applied GRPO using LoRA rank 32, alpha 16,
   all linear layers, 5K samples with four generations, plus additional recovery/refinement stages.
5. The current production artifact is not the result of that SFT run alone. Its card describes a
   long SFT/GRPO chain, targeted number and anti-loop data, a two-epoch 2e-6 refinement, and a
   weight-space average of two checkpoints (`0.3 * v55 + 0.7 * v51`).

Dataset counts differ between historical cards and the project's pinned dataset revision. The
project must continue to use its verified 135,503 train and 6,921 publisher-validation rows rather
than silently substituting a later Sotto revision.

## Comparison with the active project run

| Setting | Active project run | Closest detailed Sotto SFT reference |
|---|---:|---:|
| Base | Qwen3-0.6B | LFM2.5-350M-Base |
| Adaptation | LoRA rank 16, alpha 32, dropout 0.05 | Full-parameter SFT |
| Train rows | 135,503 pinned rows | 157,556 evolving-lineage rows |
| Epochs | 1 | 3 |
| Microbatch / accumulation | 4 / 8 | 1 / 8 |
| Effective example batch | 32 | 8 |
| Learning rate | 2e-4 | 3e-5 |
| Schedule / warmup | Cosine / 3% | Cosine / 50 steps |
| Optimizer | Fused AdamW, framework-default betas | AdamW beta2 0.95 |
| Weight decay | 0.01 | 0.01 |
| Sequence handling | No packing; 2,112-token fail-closed ceiling | Packed 4,096-token context |
| Precision | BF16+TF32 | BF16+TF32 |
| Seed | 23 | 42 |

The learning rates are not directly comparable: 2e-4 updates only LoRA parameters, whereas 3e-5
updates the complete LFM model. The architectures, prompt formats, dataset revisions, batch sizes,
and sequence packing also differ. The official record therefore does not justify changing the
active run mid-flight.

## Decision basis for follow-ups

- Keep the current one-epoch Qwen LoRA run unchanged so it remains a controlled dataset
  experiment. Its 4,235 optimizer steps come from the pinned row count and effective batch, not
  from Sotto's training record.
- If validation and raw semantic evaluation show useful learning and the loss is still improving,
  run a separately named three-epoch continuation/comparison. Three epochs has a publisher basis;
  it must not replace the one-epoch result retroactively.
- If LoRA quality plateaus, compare a higher-capacity adapter or full BF16 tuning. Sotto's own
  progression reports full fine-tuning as an improvement over its early LoRA models, but that is
  evidence to test, not proof that Qwen will behave the same way.
- Do not copy Sotto's GRPO rewards or model soup without first defining leakage-safe preference
  data and semantic-preservation rewards. ROUGE/filler-oriented rewards alone do not satisfy this
  project's raw-output safety gate.
- Keep exact-match, protected-literal preservation, correction behavior, no-op behavior, and raw
  semantic review as the project decision metrics. Sotto's reported ROUGE-L and filler-free scores
  are useful context but are not interchangeable with these gates.

## Selected follow-up

After directly screening the publisher's finished checkpoint and calibrating every non-exact
output with the user, the approved next work is
`docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`. First continue the pinned public checkpoint
for two full-SFT epochs at `2e-6` on a deterministic correction-weighted source mixture; then,
after evaluating that arm, reproduce the disclosed three-epoch `3e-5` full-SFT design from a
pinned `LFM2.5-350M-Base`. This does not authorize copying the unpublished GRPO/reward/model-soup
lineage or using any evaluation-only case as training data.
