# Parakeet → Sotto acoustic TTS integration run

Date: 2026-08-18  
Decision scope: joined-pipeline regression evidence only; not STT or cleanup qualification

## Result

The installed joined Activity completed all 20 project-authored synthetic dictation stress cases
through the physical Pixel 7 microphone without a crash, stuck recorder, failed model state, or
missing cleanup result. Parakeet and Sotto stayed warm between utterances, the microphone stopped
after every Stop tap, and the final post-run thermal status was `0`.

The integration works, but the current model behavior is not deployable:

- Parakeet produced 4/20 strict exact and 11/20 lowercase/punctuation-normalized exact transcripts.
  A simple word diagnostic counted 46 errors over 344 reference words (13.37%); this uncontrolled
  speaker-to-microphone run is not comparable with the file-fed LibriSpeech benchmark.
- Sotto returned five outputs that passed the current guardrail and fifteen that fell back to the
  deterministic model input. Four accepted outputs were no-ops. The remaining accepted output,
  case 014, changed a dictated technical command and is a substantive guardrail miss.
- Case 011 showed the opposite failure mode: Sotto correctly applied the explicit beta-to-canary
  correction, but the lexical guardrail rejected deletion of the superseded `Beta` span.
- The long-form case completed successfully, but Parakeet changed `maintenance window` to
  `mainten` and `Ravi` to `Robi`; Sotto retained the five-to-three-minute correction chain and its
  unsupported `mainten` → `maintain` repair was rejected.

Raw model output, not fallback output, remains the semantic-safety gate. This run does not change
the public Sotto no-go decision.

## Method

- Device: Pixel 7 (`panther`), Android 17 build
  `google/panther/panther:17/CP2A.260705.006/15641320:user/release-keys`.
- App: `dev.localflow.dictation` 0.1.0, installed APK 88,044,124 bytes, SHA-256
  `a00353b6b1975f6a016878fdd694f33e9668eb25f8a3eaed2a67938b55239865`.
- Parakeet: TDT/CTC 110M Q4_K, SHA-256
  `2d1d90edac07326b20a896440628c50323530cf28c7e7ca99d439bad1dee9abf`.
- Sotto: public LFM2.5-350M Q4_K_M integration placeholder, SHA-256
  `05385da14474f3e488c7611edbb1e7065b3ccb07862e3c93ec1ccbd267b2e570`.
- Fixture manifest: 65-case Qwen3-TTS/Ryan corpus SHA-256
  `10a06cdece044e4c0383eb5719461fdba3b74cb6638efd9d5c238cf7728964cf`;
  this run used only `dictation-tts-001` through `dictation-tts-020`.
- Acoustic path: canonical 16 kHz WAVs played from the MacBook Air speakers at system volume 56
  into the Pixel microphone in the existing, uncontrolled desk setup. No distance or sound-pressure
  level was measured. Capture included approximately one second before and after playback.
- Both models were loaded once. Measured load times were 269 ms for Parakeet and 1,003 ms for
  Sotto. UI automation collected raw STT, exact post-filler model input, raw Sotto output, guarded
  output, and timing after every case. Transcript text did not enter Logcat.

## Aggregate timing

| Metric | Median | p90 (nearest rank) | Maximum |
|---|---:|---:|---:|
| Recording | 9,335 ms | 13,881 ms | 37,949 ms |
| Stop-to-STT final | 934 ms | 1,333 ms | 3,350 ms |
| Cleanup TTFT | 282.5 ms | 322 ms | 618 ms |
| Cleanup total | 564.5 ms | 655 ms | 2,125 ms |
| Stop-to-cleanup complete | 1,465.5 ms | 1,950 ms | 5,484 ms |

The maximums are from the 35.12-second long-form fixture. Post-run thermal status was `0`; battery
temperature was 30.5 °C and the virtual skin sensor reported 37.0 °C.

## Case review

| Case | STT observation | Raw cleanup / final selection |
|---|---|---|
| 001 | `Niamh O'Rourke` → `Nema Rock` | `nine fifteen` → `9:15`; fallback |
| 002 | Correction words recognized | Corrupted identifier and retained both values; fallback |
| 003 | Version words recognized | Dropped `.12` from the intended version; fallback |
| 004 | `code`, `client`, `git` misrecognized | Reconstructed a different URL surface; fallback |
| 005 | `CSV` collapsed to `dotcsv` | Path normalization introduced a new surface; fallback |
| 006 | Spelled acronym grouped as `SRE` | Identifier digits normalized; fallback |
| 007 | Normalized exact | `twenty six` → `26`; fallback |
| 008 | Exact | Exact safe no-op; accepted |
| 009 | Exact question | Preserved question, did not answer; time normalization fell back |
| 010 | `build` → `bill`; `retry` → `retribution` | Removed one `uh`; Sotto dropped `Well`; fallback |
| 011 | Normalized exact correction chain | Correctly selected canary, but guardrail rejected removal of `Beta` |
| 012 | All four protected names materially wrong | No-op relative to STT; accepted |
| 013 | `ops` → `obs`; letter grouping changed | Damaged email-like surface; fallback |
| 014 | Normalized exact technical dictation | Changed `dot slash verify dash release` to `/ verify release`; **accepted unsafe edit** |
| 015 | Normalized exact phone digits | Collapsed digits to `07041862903`; fallback |
| 016 | Normalized exact date/currency/card text | Normalized all protected numbers; fallback |
| 017 | Normalized exact formatting directive | No-op; failed to create numbered formatting; accepted |
| 018 | Exact homophone sentence | Exact safe no-op; accepted |
| 019 | Dropped `zero`; `returned` → `return` | Converted remaining words to `503`; fallback |
| 020 | `maintenance window` → `mainten`; `Ravi` → `Robi` | Unsupported repair; correction retained; fallback |

### Critical raw-output evidence

Case 011 raw STT:

> Deploy to Beta sorry Deploy only to canary after lunch.

Sotto raw output:

> Deploy only to canary after lunch.

The raw edit is the intended correction, but the guardrail returned the pre-clean input because it
treated `Beta` as protected lexical content.

Case 014 raw STT:

> Set max underscore retries equals five then run dot slash verify dash release.

Sotto raw and guarded output:

> Set max underscore retries equals five then run / verify release.

This loses dictated command punctuation/surface and passed the guardrail. It is the run's clearest
semantic-safety failure.

Case 020 raw Sotto output retained both the superseded five-minute value and the later three-minute
correction. Its only edit was `mainten` → `maintain`, which the guardrail rejected as unsupported
new lexical content.

## Follow-up

1. Keep public Sotto integration-only and use this suite as a regression check after the approved
   correction-repair checkpoint passes independent raw semantic safety.
2. Add correction-aware guardrail handling that can distinguish an explicitly superseded span
   from protected content, without weakening names, numbers, negation, identifiers, or command
   surfaces. Case 014 must become a permanent guardrail regression.
3. Investigate Parakeet protected-name, spelled-letter, URL/path, and long-form proper-name errors.
4. Keep the synthetic suite as plumbing evidence. Add controlled playback plus human, multi-speaker
   recordings before making a dictation-quality claim.
