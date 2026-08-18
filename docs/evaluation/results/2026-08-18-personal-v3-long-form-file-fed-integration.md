# Personal-v3 long-form file-fed integration

Date: 2026-08-18

Device: Google Pixel 7 (`panther`, Android ARM64)

Decision: personal v3 becomes the active product/checkpoint regression; public Sotto remains no-go

## Change from v2

Personal v3 removes the mobile phone-number dictation case. It retains the useful short and medium
messages, journals, lists, names, numbers, uncertainty, repetition, formatting, and correction
cases, and adds four longer everyday utterances:

| Case | Shape | Synthetic audio |
|---|---|---:|
| `personal-v3-015` | Four-sentence journal entry | 20.00 s |
| `personal-v3-018` | Three-sentence movie message | 14.88 s |
| `personal-v3-019` | Five-sentence journal/paragraph entry | 24.32 s |
| `personal-v3-020` | Four-sentence planning/correction note | 25.84 s |

V2 remains immutable historical evidence. V3 must be versioned again rather than edited after
checkpoint results are recorded.

## Reproducibility

- TTS cases: `docs/evaluation/stt_personal_conversation_tts_cases_v3.jsonl`
  - SHA-256 `f3939fd89d9512e3599d875d5b8391aa3267dd4556ae21b2889903bfe1026791`
- Direct checkpoint cases: `docs/evaluation/cleanup_personal_conversation_v3.jsonl`
  - SHA-256 `667715109afdf2e0e907d25c875ec7a8645f518c8ae690924128bc58a7482ac0`
- Generated TTS manifest SHA-256
  `35f43e00b8e2a6fa7d95ae15de96ed75db5af82a62ca95dcd9ce079a6b69794e`
- Tested APK: 88,044,569 bytes, SHA-256
  `40ab366fbdf24aa15cfcff11a1ea8ce947c7106d7d65d249c4f22ab581e102a8`
- Parakeet Q4_K SHA-256
  `2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf`
- Public Sotto Q4_K_M SHA-256
  `05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570`
- Run ID: `20260818T095822Z-joined-file`
- Ignored raw result SHA-256
  `4567490e2d7e00039c95b12fd7db65e30f482c0f16f86cda386b6df5b20b90f9`

Both committed v3 files and all results are evaluation-only. They must never become training rows,
prompt demonstrations, retrieval context, preference pairs, or repair-generation examples.

## Overall results

| Metric | Result |
|---|---:|
| Cases complete | 20/20 |
| Raw STT strict / normalized exact | 8/20 / 15/20 |
| Raw Sotto target strict / normalized exact | 8/20 / 10/20 |
| Guarded target strict / normalized exact | 8/20 / 10/20 |
| Guardrail fallbacks | 3/20 |
| STT median / p90 / max | 625 / 1,903 / 2,470 ms |
| Cleanup median / p90 / max | 645 / 1,713 / 2,275 ms |
| Joined median / p90 / max | 1,261 / 3,716 / 4,746 ms |

The three fallbacks remain genuine retained corrections in cases 002, 011, and 020. Public Sotto
also retained the repeated phrase in case 010 and did not consume the bullet or paragraph
directives. Name recognition remained weak on the synthetic voice (`Aiko` and related Unicode
names); cleanup correctly cannot guess those protected identities.

## Long-form latency

| Case | STT | Cleanup | Joined | Fallback |
|---|---:|---:|---:|---:|
| `personal-v3-015` | 1,903 ms | 2,065 ms | 3,970 ms | no |
| `personal-v3-018` | 1,236 ms | 1,304 ms | 2,543 ms | no |
| `personal-v3-019` | 2,002 ms | 1,713 ms | 3,716 ms | no |
| `personal-v3-020` | 2,470 ms | 2,275 ms | 4,746 ms | yes |

The 14.88–25.84 second fixtures completed without microphone use, crash, missing output, or model
reload. Latency scales visibly with utterance length, and the longest correction case remains the
worst joined tail. These are single-run integration timings, not sustained-performance or
real-speaker qualification.

## Training-machine checkpoint use

Every public-start/Experiment-A/Experiment-B checkpoint must run the direct-text
`cleanup_personal_conversation_v3.jsonl` file with the fixed Sotto native prompt and greedy decoder.
The exact hash-pinned command and manual-review requirements are in
`docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`. Report raw output before guardrails, all
non-exact cases, long-form per-case latency, correction deletion, repetition, formatting, names,
numbers, negation, and uncertainty.

## Reproduction

```bash
TTS_OFFLINE=1 ./scripts/prepare-cleanup-tts-eval.sh --suite personal-v3 --resume
./scripts/run-joined-file-eval.sh \
  .cache/stt-eval/personal-conversation-tts-v3-qwen3-ryan
```
