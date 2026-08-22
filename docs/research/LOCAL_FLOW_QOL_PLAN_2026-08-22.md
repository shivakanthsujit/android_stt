# Local Flow quality-of-life plan

Date: 2026-08-22

## Goal

Make the daily-driver voice keyboard easier to read, trust, correct, and reuse without changing
the local Parakeet → S1-mini model contract or collecting transcript/audio history.

## Product references

Google's public Rambler/Gboard documentation is useful for interaction principles rather than
assets or model behavior: make recording state unmistakable, keep the editor visually stable while
listening, retain access to the original transcript, and make model-assisted changes undoable.
Local Flow remains Pixel 7-first, fully local, explicit Start/Stop, and final-only cleanup.

## Ordered work

1. **Transcript and undo fundamentals**
   - Give the Activity and IME bounded, independently scrollable transcript surfaces.
   - Follow the newest live partial by default, but preserve position when the owner scrolls up.
     Scrolling changes presentation only: microphone capture and streaming STT must continue. Resume
     tail-follow automatically when the owner returns to the bottom.
   - Keep up to five same-editor insertion undo records. Delete only an exact immediate suffix;
     clear history on an editor change or any surrounding-text mismatch.
   - Join consecutive dictations with a boundary space only when the text immediately around the
     cursor requires it. Include any added separator in the exact undo transaction.
2. **Clearer, calmer keyboard states**
   - Replace dense status copy with a compact recording/processing/result hierarchy.
   - Add an obvious, persistent listening indicator driven by the actual recording state—not a
     decorative animation—and make Stop the dominant action while recording. It must remain visible
     even while the transcript is manually scrolled away from the tail.
   - Keep Cancel, Undo, and keyboard switching reachable without accidental activation.
3. **Real audio waveform**
   - Feed a throttled RMS/peak envelope from project-owned `AudioRecord` chunks to a lightweight
     custom view. Never persist audio or amplitude history and never simulate microphone activity.
   - Pause/reset it immediately on Stop, Cancel, permission loss, or lifecycle teardown.
   - Verify drawing cost, accessibility, and reduced-motion behavior on Pixel before keeping it.
4. **Recovery and revision polish**
   - Add explicit retry for recoverable model/processing failures.
   - Evaluate a local raw-versus-cleaned review control without placing provisional text in the
     destination editor or weakening the insertion policy.
   - Consider redo only if the exact editor/cursor transaction can remain fail-closed.
5. **Daily-driver Pixel gate**
   - Check long live transcript scrolling, manual scroll hold, repeated dictations and multi-undo,
     cancel, focus switching, password/private fields, model failure, rotation/keyboard hiding,
     TalkBack labels, memory, thermal behavior, and true Stop-to-editor-commit latency.

## First slice acceptance

- A live transcript longer than five keyboard lines can be scrolled while recording.
- New partials follow the tail until the owner scrolls upward; manual position is then preserved
  without pausing capture or STT. Returning to the bottom resumes tail-follow.
- The Activity raw transcript has its own bounded scroll viewport and remains editable after Stop.
- Up to five consecutive Local Flow commits in the same unchanged editor can be undone in reverse
  order. An editor change or a non-matching suffix makes undo unavailable without deleting text.
- Consecutive end-of-field dictations receive one separating space; empty fields, existing
  whitespace, and punctuation boundaries do not receive a duplicate or inappropriate space.
- No audio, transcript history, expected cleanup output, or evaluation corpus is added to logs or
  storage.
