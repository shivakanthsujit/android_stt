# Local Flow agent instructions

This repository builds a Pixel-first, fully local Android dictation app. Cleanup-model quality is
the active bottleneck; the working Moonshine path is only the provisional STT input.

## Start here

Before changing the project, read:

1. `docs/project/README.md`
2. `docs/project/CURRENT_STATE.md`
3. `docs/project/NEXT_STEPS.md`
4. `docs/project/DECISIONS.md`

If the task involves dataset preparation, GPU training, checkpoint evaluation, quantization, or
the separate RTX A6000 machine, also read `TRAINING_MACHINE_HANDOFF.md` completely before acting.
That file routes to the authoritative training plan and dataset contract.

## Non-negotiable constraints

- Never use either committed cleanup evaluation corpus, its expected outputs, captured model
  results, or VoiceInk prompt as training data, generator demonstrations, retrieval context, or
  preference pairs.
- Treat `docs/evaluation/cleanup_cases.jsonl` and
  `docs/evaluation/cleanup_cases_heldout_v1.jsonl` as evaluation-only diagnostics.
- Optimize and select checkpoints on train/dev plus the retired diagnostics. Never use blind-v2
  for checkpoint selection, prompt tuning, data repair, or guardrail tuning.
- Raw model output must pass semantic safety. A guardrail fallback cannot turn a failed model into
  a deployment candidate.
- Preserve names, numbers, negation, uncertainty, versions, paths, identifiers, and dictated
  questions or commands. Cleanup edits the transcript; it never answers or executes it.
- Do not start LoRA/QLoRA training on the Mac. GPU training belongs on the separately identified
  RTX A6000 machine and only after its environment and Gate A data checks are recorded.
- Do not commit downloaded datasets, model weights, adapters, checkpoints, caches, secrets,
  personal transcripts, or unsealed blind references.
- Use monitoring for long-running jobs, retain logs and resumable checkpoints, and report failures
  instead of silently restarting with changed settings.

## Session durability

At the end of meaningful work, update `CURRENT_STATE.md`, `NEXT_STEPS.md`, and `SESSION_LOG.md`.
Record stable choices in `DECISIONS.md`, evaluation evidence under `docs/evaluation/results/`, and
reproducibility hashes in manifests. Commit and push coherent checkpoints without including large
or sensitive artifacts.
