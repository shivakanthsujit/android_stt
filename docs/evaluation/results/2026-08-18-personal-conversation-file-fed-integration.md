# Personal-conversation file-fed joined integration

Date: 2026-08-18

Device: Google Pixel 7 (`panther`, Android ARM64)

Decision: integration path passes; public Sotto remains cleanup no-go

## Scope

This is the first joined Parakeet → public Sotto run on the product-calibrated personal-conversation
suite. The active 20 examples cover ordinary messages, journal entries, lists, natural
self-corrections, names, times, a phone number, uncertainty, repetition, and paragraph/list
directives. Developer-oriented git, URL, checksum, CLI, path, TLS, email-domain, and version-string
cases from the superseded v1 synthetic set are not part of this suite.

The runner feeds checksum-verified WAV files directly to the installed debug Activity. It never
opens the microphone. This isolates joined decoding/cleanup/guardrail behavior and is substantially
faster and more reproducible than speaker-to-microphone playback, but it does not test capture,
room acoustics, endpointing, real voices, or recorder lifecycle.

The suite and every captured output are evaluation-only. They must not be used for training,
generator demonstrations, retrieval, preference pairs, or checkpoint selection beyond their
declared regression role. Blind-v2 remains sealed and was not used.

## Reproducibility identities

- Cases: `docs/evaluation/stt_personal_conversation_tts_cases_v2.jsonl`
  - 20 rows
  - SHA-256 `2a8c6e247a47b6ad9a48a78e37c540ab44707cb546f53bef2b421c540a3103ba`
- Generated manifest:
  - ignored local path
    `.cache/stt-eval/personal-conversation-tts-v2-qwen3-ryan/manifest.jsonl`
  - SHA-256 `771d2fff6b1d9bf8c2e9492d483dbe461f07dd7176996ad6f817e9e5f7c62029`
  - Qwen3-TTS profile and model/runtime pins are recorded by `TTS_PIPELINE.md` and the ignored
    corpus metadata
- Parakeet TDT/CTC 110M Q4_K SHA-256
  `2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf`
- Public Sotto LFM2.5-350M Q4_K_M SHA-256
  `05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570`
- Tested debug APK: 88,044,472 bytes, SHA-256
  `0b594350f9239376a16b9abf508e9f51f64fa92651085d084a164afb6a91b654`
- Evidence timing run ID: `20260818T093938Z-joined-file`
- Ignored raw result SHA-256:
  `f25543e4f7447900069ce4d1acf49f20732e6dfc987ef8748b863ea2dad7d1a8`

The intended cleanup target is joined by case ID only after device inference. It is never passed to
Qwen TTS, Parakeet, or Sotto.

## Results

| Metric | Result |
|---|---:|
| Cases completed | 20/20 |
| Raw STT strict exact vs spoken reference | 6/20 |
| Raw STT normalized exact vs spoken reference | 16/20 |
| Raw Sotto strict exact vs intended cleanup | 8/20 |
| Raw Sotto normalized exact vs intended cleanup | 10/20 |
| Guarded strict exact vs intended cleanup | 8/20 |
| Guarded normalized exact vs intended cleanup | 10/20 |
| Guardrail fallbacks | 3/20 |
| STT inference median / p90 / max | 499 / 879 / 1,792 ms |
| Cleanup total median / p90 / max | 637 / 943 / 2,223 ms |
| Joined pipeline median / p90 / max | 1,135 / 1,842 / 4,017 ms |

The run completed in under a minute after model installation/push, instead of waiting for the full
synthetic audio duration plus manual capture control. It also verified that removed fillers are
serialized as a JSON array and nullable fields remain explicit. An earlier repeat demonstrated that
launching while the Pixel is asleep pauses the Activity and invalidates latency; the launcher now
wakes/dismisses keyguard before the measured start.

## Quality review

Parakeet was strong on the ordinary English surfaces. The four normalized STT misses were dominated
by synthetic-name pronunciation/transcription (`Aiko`, `François`, `Chloé`, `Shinagawa`, `Elena`)
and one spoken-time rendering. These errors reached Sotto unchanged; cleanup is not authorized to
guess protected names.

Public Sotto correctly handled the sentence-initial `Well`/filler/repetition examples, simple
no-op messages and journal text, and numeric surfaces such as `26`, `8`, `6:20`, `84`, and the
continuous phone digits. It did not consistently consume bullet/paragraph directives or the
bounded abandoned journal lead-in.

The three fallbacks were genuine model failures, not the earlier false guardrail behavior:

- `personal-tts-002`: retained both the old time and the corrected time.
- `personal-tts-011`: retained the superseded family-group recipient before Maya.
- `personal-tts-020`: retained five minutes, the correction marker, and ten minutes.

Returning raw STT on those failures preserves what was spoken but does not produce the desired
clean correction. This is containment, not successful cleanup. Raw public-Sotto output therefore
still fails the deployment gate even though no accepted output invented a new semantic fact beyond
the Parakeet hypothesis in this run.

## Guardrail finding and revision

The previous guardrail was materially too conservative because it treated lexical surface identity
as a proxy for meaning. That caused valid cleanup to fall back and made the joined output worse:

- sentence-initial `Well` was capitalized and therefore treated like a protected name;
- an explicit `beta, sorry, canary`-style replacement could be rejected for deleting the old word;
- spoken `twenty six` → `26` and `six twenty` → `6:20` were rejected even though the value was
  unchanged; and
- consuming explicit bullet-list, numbered-list, or paragraph directives looked like destructive
  deletion.

Android and host guardrails now accept those bounded edits. Numeric acceptance requires a
deterministic equivalent parse; `twenty six` → `25` still fails. Repeated-imperative `sorry`
corrections require the same bounded command verb and preservation of the replacement target.
Only explicit list/paragraph directive forms and one exact abandoned journal lead-in are optional.
Names, changed numeric values, negation, uncertainty, unsupported lexical additions, answered
content, and excessive contraction remain protected.

This revision reduces false rejection; it does not make guardrails a cleanup engine. A fallback
cannot turn an unsafe or under-cleaned raw checkpoint into a deployment candidate.

## Reproduction

```bash
TTS_OFFLINE=1 ./scripts/prepare-cleanup-tts-eval.sh --suite personal-v2 --resume
./scripts/run-joined-file-eval.sh \
  .cache/stt-eval/personal-conversation-tts-v2-qwen3-ryan
```

For one user recording:

```bash
JOINED_EVAL_REFERENCE="Optional literal spoken reference." \
  ./scripts/run-joined-file-eval.sh recording.mp3
```

## Decision

The file-fed joined harness is the primary fast synthetic regression path. The ordinary microphone
Activity remains the separate acoustic/lifecycle path. The personal-conversation v2 suite replaces
the technical v1 examples as the active product-facing synthetic regression set.

The public Sotto checkpoint remains integration-only: 10/20 normalized target matches and three
retained explicit corrections are not adequate cleanup quality. The training machine should focus
on ordinary-message/journal/list corrections represented by this product calibration while keeping
this committed suite strictly evaluation-only.
