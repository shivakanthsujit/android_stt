# Project handoff

Start here when resuming Local Flow in a new session.

| File | Purpose |
|---|---|
| [CURRENT_STATE.md](CURRENT_STATE.md) | What currently works, repository state, and known issues |
| [NEXT_STEPS.md](NEXT_STEPS.md) | Ordered work queue and acceptance criteria |
| [DECISIONS.md](DECISIONS.md) | Durable technical/product decisions and their rationale |
| [TEST_LOG.md](TEST_LOG.md) | Physical-device and build verification evidence |
| [SESSION_LOG.md](SESSION_LOG.md) | Append-only summary of completed work by date |
| [Pixel STT benchmark](../evaluation/STT_BENCHMARK.md) | File-fed corpus preparation, Pixel execution, WER, latency, CPU, memory, thermal, and power procedure |
| [Mac-local TTS fixtures](../evaluation/TTS_PIPELINE.md) | Pinned text-to-WAV setup, active personal-conversation suite, fast joined WAV/MP3 runner, hashes, resume, and offline cache |
| [Pixel Parakeet report](../evaluation/results/2026-08-18-pixel-parakeet-stt-probe.md) | F16/Q4_K/Moonshine measurements, decision, caveats, and reproducibility hashes |
| [Pixel S1-mini report](../evaluation/results/2026-08-21-s1-mini-v1-pixel.md) | Exact publisher-contract parity, personal-v3 quality, latency, memory, thermal, and power evidence |
| [Pixel S1-mini LEAP tuning report](../evaluation/results/2026-08-22-s1-mini-leap-pixel-tuning.md) | Thread/context/cache matrix, matched power traces, selected production settings, and reproducibility hashes |
| [Direct llama.cpp readiness and Pixel smoke](../evaluation/results/2026-08-22-s1-mini-direct-llamacpp-host-readiness.md) | Isolated runtime, pinned build manifest, exact prompt/token device smoke, hashes, and remaining parity/performance gates |
| [S1-mini Pixel inference optimization plan](../research/S1_MINI_PIXEL_INFERENCE_OPTIMIZATION_PLAN_2026-08-22.md) | Ordered LEAP tuning, same-GGUF direct llama.cpp, and S1-specific LiteRT-LM CPU/GPU program |
| [Streaming STT and S1-mini runtime contract](../research/STREAMING_STT_AND_S1_MINI_RUNTIME_CONTRACT_2026-08-21.md) | Realtime EOU model-card constraints, final-only cleanup ordering, 1,000-token sentence chunking, hashes, and release caveats |
| [Training-machine handoff](../../TRAINING_MACHINE_HANDOFF.md) | Complete RTX A6000 data/training/evaluation workflow |
| [Direct-source experiment plan](../training/DIRECT_SOURCE_EXPERIMENT_PLAN.md) | Immediate four-adapter Sotto/Disfl-QA/Nyra experiment and evaluation handoff |
| [Sotto recipe reference](../research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md) | Publisher model-card hyperparameters and comparison with the active Qwen LoRA run |
| [Public Sotto LFM screen](../evaluation/results/2026-08-18-sotto-lfm25-350m-public-screen.md) | Native-prompt quality screen of the publisher's finished 350M checkpoint |
| [Joined integration evidence](../evaluation/results/2026-08-18-parakeet-sotto-integration-build.json) | Reproducible model/APK hashes and sanitized Pixel pipeline smoke evidence |
| [Personal-v3 joined regression](../evaluation/results/2026-08-18-personal-v3-long-form-file-fed-integration.md) | Active no-phone 20-case workload, long-form latency, file-fed Pixel results, and checkpoint handoff |
| [Personal cleanup acceptance](../evaluation/PERSONAL_CLEANUP_ACCEPTANCE.md) | Default relaxed semantic product metric, strict diagnostic role, and non-negotiable failures |
| [Personal-v3 cross-model comparison](../evaluation/results/2026-08-18-personal-v3-relaxed-cross-model-comparison.md) | Relaxed ranking of all local Sotto variants and hosted GPT models |
| [Luna versus Sotto B Pixel comparison](../evaluation/results/2026-08-18-luna-vs-sotto-b-epoch2-pixel.md) | Direct and Parakeet-fed correctness, latency, memory, and power evidence supporting the provisional local baseline |
| [Sotto LFM correction-repair plan](../training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md) | Approved next-session continuation and clean-base experiments |

Maintenance rule: update `CURRENT_STATE.md`, `NEXT_STEPS.md`, and `SESSION_LOG.md` at the end of
every meaningful work session. Add stable decisions to `DECISIONS.md` and device evidence to
`TEST_LOG.md`. Do not store raw transcripts in diagnostic logs.

The full product plan remains in
[ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md](../../ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md).

Agents automatically receive the repository rules in [AGENTS.md](../../AGENTS.md). On the training
machine, read the complete training handoff and every document it marks required before fetching
data or starting a GPU job.
