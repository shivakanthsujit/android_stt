# Evaluation

This directory contains two independent evaluation tracks:

- transcript cleanup quality and semantic safety, using the committed evaluation-only text corpora;
- speech-to-text quality and Pixel performance, using file-fed public audio kept outside Git.

Do not use the committed cleanup evaluation corpora, expected outputs, or captured model results as
training data or generator examples.

## Dictation cleanup evaluation

`cleanup_cases.jsonl` is a deterministic seed corpus for evaluating transcript cleanup independently of speech recognition. It contains 24 cases, enough to support the first Pixel 7 go/no-go run while leaving room to grow toward the 50–100 case corpus described in the project context.

The cases cover filler removal, abandoned false starts, self-corrections, repeated words, punctuation and capitalization, conversational tone, names and Unicode, technical text, numbers and other facts, negation, uncertain wording, nearly unchanged inputs, and instructions or questions that must be transcribed rather than answered.

## Record schema

Each line is one JSON object with these fields:

- `id`: Stable unique case identifier.
- `spoken`: Human-readable representation of what was spoken. This is context only and is not provided to the cleanup model.
- `raw`: The simulated final STT transcript and the sole value inserted into the cleanup prompt.
- `expected`: The conservative reference output. It preserves meaning and tone, applies only obvious corrections, and contains no answer or newly introduced fact.
- `categories`: Stable labels used to aggregate results by behavior.
- `must_preserve`: Case-sensitive literal anchors that a candidate output must retain after normalization. These focus scoring on names, numbers, technical tokens, negation, uncertainty, and other meaning-bearing facts.

Do not silently change an existing case's meaning or expected output after results have been recorded. Add a new case ID or version the corpus when a reference policy changes.

## Deterministic run settings

Use the cleanup instruction from section 14 of `ANDROID_LOCAL_DICTATION_AGENT_CONTEXT.md`. Substitute only the case's `raw` value for the transcript. For every model:

1. Start from the same model state and prompt text.
2. Disable sampling, or use temperature 0 and the minimum supported randomness.
3. Use a fixed seed if the runtime exposes one.
4. Derive the same bounded maximum output length from the input length.
5. Capture the model output before application guardrails and the text selected after guardrails separately.
6. Trim leading and trailing whitespace before scoring. Do not otherwise repair model output.

Run cases in ascending `id` order. Run the no-cleanup baseline by returning `raw` unchanged.

## Automated scoring

Normalize the reference and candidate by converting to Unicode NFC, converting CRLF to LF, and trimming leading and trailing whitespace. Do not lowercase, remove punctuation, collapse internal whitespace, or normalize names and numbers; those are behaviors under test.

Report at least:

- `exact_match_rate`: Fraction whose normalized candidate equals normalized `expected`.
- `preservation_rate`: Fraction of all `must_preserve` anchors present as case-sensitive substrings in the normalized candidate.
- `case_preservation_pass_rate`: Fraction of cases containing every `must_preserve` anchor.
- `empty_output_rate`: Fraction with an empty normalized candidate.
- `expansion_guard_rate`: Fraction where candidate length exceeds 1.8 times raw length and would trigger raw-transcript fallback.
- Per-category exact-match and preservation rates.

Use Unicode code-point counts for the 1.8× length check. Score the raw model result even if the application would reject it, then score the post-guardrail selected text as a separate result. Exact match is intentionally strict; review non-exact outputs manually for meaning preservation, hallucination, and subjective preference rather than weakening the normalization rules.

For cases labeled `must_not_answer`, any answer, explanation, generated content, or command execution is a failure. The required behavior is only to clean the dictated request. Exact match remains the deterministic automated test for these cases.

## Benchmark use

For Pixel 7 model comparisons, store the case ID alongside model load time, peak-ish process memory, cleanup time to first token, cleanup total latency, and warm end-to-end latency. Compare the no-cleanup baseline, LFM2.5-230M, LFM2.5-350M, and future candidates against the identical corpus and run settings.

## OpenAI-compatible local endpoints

`scripts/run-cleanup-openai.py` runs the same corpus and Android prompt/settings against a local
OpenAI-compatible chat-completions endpoint. Streaming is enabled by default so TTFT is measurable;
use `--no-stream` only for endpoints without streaming support. For example:

```bash
python3 scripts/run-cleanup-openai.py \
  --base-url http://127.0.0.1:8080/v1 \
  --model candidate-model \
  --quantization Q4_K_M \
  --output build/evaluation-results/candidate.jsonl

python3 scripts/score-cleanup-results.py \
  build/evaluation-results/candidate.jsonl
```

The default is the frozen `baseline_rules` prompt, temperature 0.1, seed 23, and the same
input-derived 16–96 token cap used on Android. `--request-extra FILE` can add runtime-specific
options such as a no-thinking chat-template setting without overriding those fixed fields. The
runner writes and flushes each completed case immediately, preserving valid partial JSONL if a
later endpoint request fails. Raw model output and Android-equivalent post-guardrail selection are
recorded separately. The guardrail port is parity-tested against the Kotlin implementation.

The first cross-family screen and its decision are recorded in
`results/2026-08-17-cross-family-cleanup-screen.md`. Quality screening happens on the host before
any candidate runtime is added to the Android app.

For a task-specific GGUF, use the reproducible two-corpus workflow in
[`SPECIALIZED_CANDIDATE_SCREENING.md`](SPECIALIZED_CANDIDATE_SCREENING.md). It starts and stops a
local `llama-server`, records model/server provenance, and keeps candidate-native prompt/runtime
settings explicit.

## Speech-to-text evaluation

Use [`STT_BENCHMARK.md`](STT_BENCHMARK.md) to prepare the pinned 24-clip LibriSpeech probe and run
identical WAV files through Moonshine or `parakeet.cpp` on the Pixel without opening the
microphone. The harness scores normalized WER, repeat latency, output stability, process CPU, PSS,
thermal status, and optional Perfetto CPU/GPU/memory rail energy.

The initial F16/Q4_K/Moonshine measurements, limitations, artifact hashes, and provisional Q4_K
decision are recorded in
[`results/2026-08-18-pixel-parakeet-stt-probe.md`](results/2026-08-18-pixel-parakeet-stt-probe.md).
This small read-speech probe is not the official full `test-clean` score and does not replace the
planned dictation/streaming qualification.
