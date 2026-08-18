# Project handoff

Start here when resuming Local Flow in a new session.

| File | Purpose |
|---|---|
| [CURRENT_STATE.md](CURRENT_STATE.md) | What currently works, repository state, and known issues |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Ordered work queue and acceptance criteria |
| [DECISIONS.md](DECISIONS.md) | Durable technical/product decisions and their rationale |
| [TEST_LOG.md](TEST_LOG.md) | Physical-device and build verification evidence |
| [SESSION_LOG.md](SESSION_LOG.md) | Append-only summary of completed work by date |
| [Training-machine handoff](../../TRAINING_MACHINE_HANDOFF.md) | Complete RTX A6000 data/training/evaluation workflow |
| [Direct-source experiment plan](../training/DIRECT_SOURCE_EXPERIMENT_PLAN.md) | Immediate four-adapter Sotto/Disfl-QA/Nyra experiment and evaluation handoff |
| [Sotto recipe reference](../research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md) | Publisher model-card hyperparameters and comparison with the active Qwen LoRA run |
| [Public Sotto LFM screen](../evaluation/results/2026-08-18-sotto-lfm25-350m-public-screen.md) | Native-prompt quality screen of the publisher's finished 350M checkpoint |

Maintenance rule: update `CURRENT_STATE.md`, `NEXT_STEPS.md`, and `SESSION_LOG.md` at the end of
every meaningful work session. Add stable decisions to `DECISIONS.md` and device evidence to
`TEST_LOG.md`. Do not store raw transcripts in diagnostic logs.

The full product plan remains in
[ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md](../../ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md).

Agents automatically receive the repository rules in [AGENTS.md](../../AGENTS.md). On the training
machine, read the complete training handoff and every document it marks required before fetching
data or starting a GPU job.
