# Live dictation diagnostics and performance plan

Date: 2026-08-22

## Why this is separate from QoL work

The owner reports that some deliberately modulated speech produces no visible text even though
speech was spoken. The current code does not gate or filter PCM before Parakeet: every successful
16 kHz mono PCM16 `AudioRecord` read is normalized to float and queued intact. The high-pass,
noise gate, smoothing, and quantization added for the waveform run on a read-only display branch.
The JNI bridge also forwards that original float array directly to Parakeet's required incremental
mel frontend.

There are still several unmeasured boundaries that can explain the observation:

- Android's `MIC` source or device audio stack may alter the captured signal even though the app
  does not explicitly enable AGC, noise suppression, echo cancellation, or a VAD.
- The Realtime EOU model may not decode unusual pitch, cadence, volume, or other modulation.
- Live presentation receives only text committed by the streaming decoder; right-context and final
  tail handling can delay text until more audio or Stop.
- Capture read gaps, native feed backlog, or an error near Stop may make audio incomplete.
- Raw STT can be correct while later cleanup, editor commit, or presentation is the failing stage.

Do not change microphone preprocessing, model thresholds, chunk sizes, audio source, or cleanup
behavior from this report alone. First capture evidence that identifies the boundary.

## Diagnostic-mode guardrails

Implement this as a dedicated debug-only session mode, disabled by default. Enabling it must be an
explicit owner action for the current session and must visibly state that microphone audio and
transcript text will be retained locally.

- Ordinary app and IME use continues to persist no audio, transcript, waveform, or amplitude
  history.
- Store captures only under an app-private no-backup diagnostics directory. Never put audio,
  personal transcripts, cleanup text, or exported sessions in Logcat, Git, test fixtures, or
  evaluation result documents.
- Use an unpredictable session ID, a maximum duration/utterance/byte budget, automatic stop at the
  bound, and visible Delete Session/Delete All actions. Export is a separate explicit owner action.
- Keep timing-only diagnostics independently selectable from payload capture when practical.
- Never include committed cleanup evaluation cases, expected outputs, captured model results, the
  VoiceInk prompt, or blind references in a diagnostic session.
- Treat captured personal speech and every derived text as diagnosis-only. Do not reuse it for
  training, demonstrations, retrieval, prompt tuning, preference pairs, or checkpoint selection
  without a separately scoped and explicitly authorized data contract.
- Measure diagnostic overhead. Payload persistence must not block `AudioRecord` or Parakeet. Use a
  bounded asynchronous writer, mark any dropped diagnostic chunk, and invalidate incomplete audio
  replays instead of hiding the loss.

## Per-session artifacts

Record a machine-readable manifest with the APK/version, device/build fingerprint, monotonic start
time, audio format, capture source, model filenames/hashes, runtime configuration, diagnostic
limits, and file hashes. For each utterance, retain:

1. The exact 16 kHz mono PCM16 samples returned by `AudioRecord`, wrapped as WAV after capture and
   copied before the waveform meter. Also retain the original read sizes and chunk ordering needed
   to reproduce the live feed schedule.
2. Capture events with monotonic timestamps: Start, `startRecording`, first sample, every read
   duration/count/error, Stop tap, `AudioRecord.stop`, final read, and capture-thread exit.
3. Streaming events with monotonic timestamps: queue depth, each native feed start/end, returned
   text delta, EOU/EOB events, native finalize start/end, and final raw STT. Do not write transcript
   payloads to Logcat.
4. Cleanup evidence: the exact final raw transcript, exact per-pass S1 input, raw model output,
   selected output, cap/blank fallback metadata, prompt/completion token counts, TTFT, total time,
   and pass ordering.
5. Pipeline and device measurements: stop-to-raw-STT, stop-to-cleanup-start, stop-to-selected-text,
   editor-commit duration/result, process CPU, PSS/native heap, thermal status, and optional
   Perfetto trace markers around capture, Parakeet chunk decode/finalize, each S1 pass, and commit.

Use monotonic time for all durations. Wall-clock time is optional session metadata only.

## Reproduction matrix

Run a small owner-authored script of normal and deliberately modulated phrases. Repeat each enough
to distinguish a stable failure from a one-off, while keeping wording and acoustic conditions
fixed within a comparison.

1. **Boundary classification:** listen locally to the saved WAV and compare live display, final
   raw STT, selected cleanup text, and editor text.
2. **Exact replay:** feed the saved PCM through the same native streaming session with the recorded
   chunk boundaries. Also replay with fixed real-time-sized chunks and fastest-possible feed to
   test whether scheduling changes output.
3. **Capture-source A/B:** only after the baseline, compare `MIC` with Android `UNPROCESSED` when
   the device reports support. Record the resolved source; never silently fall back or claim that
   `MIC` is processed without device evidence.
4. **Model A/B:** compare the selected Realtime EOU artifact with the retained offline Parakeet
   reference on the same saved PCM. Keep model hashes and decoder paths explicit.
5. **Performance profile:** compare diagnostics-off and timing-only runs before using payload-mode
   latency. Separate Parakeet feed/finalize, S1 TTFT/total per pass, queue wait, and editor commit so
   an aggregate Stop-to-result number cannot hide the bottleneck.

## Interpretation rules

- Missing or heavily altered speech in the saved WAV points to capture source, device processing,
  microphone acoustics, or lifecycle—not cleanup.
- Audible complete speech in WAV plus empty/wrong final raw STT points to Parakeet/model frontend or
  streaming integration.
- Different output from exact saved-audio replay points to chunk scheduling, state, or a capture
  handoff defect.
- Missing live text with correct final raw STT points to streaming presentation/finalization timing.
- Correct final raw STT with wrong selected or committed text points downstream to cleanup or the
  editor transaction.
- Queue growth or native feed duration consistently exceeding incoming audio duration is a real-time
  backlog. Total model latency alone is not evidence that audio was dropped.

## Exit criteria

- At least one reported failure is captured with complete PCM and complete boundary timings.
- The failure is assigned to capture, Parakeet, live presentation, cleanup, or editor commit with a
  replayable artifact.
- Parakeet chunk/finalize and S1 per-pass TTFT/total bottlenecks are reported independently, with
  CPU, memory, and thermal context.
- Any proposed change is tested against the same saved audio with diagnostics overhead accounted
  for; no microphone filter or recognition gate is introduced without evidence.
- Personal payload artifacts remain app-private or explicitly exported outside the repository, and
  the session is deleted when the owner no longer needs it.
