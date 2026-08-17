# Cleanup pilot: training data and evaluation

Status: pending human review and Gate A

This is the short description of what the first cleanup-model experiment trains on and how its
progress is evaluated. The detailed safety rules remain authoritative in
`ANNOTATION_POLICY_V2.md`, and the exact commands remain authoritative in `PILOT_RUNBOOK_V1.md`.

## What the pilot trains

The pilot uses **5,000 training rows** and **500 development rows**. Each row contains a simulated
raw transcript and the minimally cleaned target. Metadata records the edit type, text that must be
preserved or removed, provenance, license, semantic family, split, and human-review decision.
Only the fixed cleanup instruction plus the raw transcript reaches the model. Loss is applied only
to the target response tokens.

The train and dev targets are:

| Primary subset | Train | Dev | What it teaches |
|---|---:|---:|---|
| Explicit correction or false start | 950 | 95 | Keep the final correction and remove superseded wording |
| Fillers or immediate repetition | 550 | 55 | Remove clear fillers and accidental repeats |
| Clean/no-op | 500 | 50 | Preserve text that should not be rewritten |
| Disfl-QA corrections | 500 | 50 | Edit dictated questions without answering them |
| Protected literals | 400 | 40 | Preserve names, numbers, dates, versions, paths, negation, and uncertainty |
| Explicit list formatting | 300 | 30 | Apply an unambiguous spoken list directive without inventing items |
| Explicit paragraph formatting | 50 | 5 | Apply an explicit paragraph break at the stated boundary |
| Explicit spoken punctuation | 150 | 15 | Render named punctuation without changing content |
| Conservative grammar repair | 500 | 50 | Make only clear, local, meaning-preserving grammar fixes |
| Context-supported ASR repair | 500 | 50 | Repair only unambiguous recognition errors |
| Mixed or discourse cleanup | 300 | 30 | Handle reviewed combinations of allowed edits |
| Adversarial must-not-answer | 300 | 30 | Copy-edit instruction-like dictation without obeying it |
| **Total** | **5,000** | **500** | |

The selection must also meet overlapping minimums in each split: 20% dictated questions or
commands, 8% adversarial instructions, 25% protected literals, 12% negation/uncertainty, 10%
Unicode or multilingual spans, 20% technical text, 20% long-form text, and 2% high-stakes text.

## Source subsets

Only publisher training subsets can supply candidates. Publisher validation/test data is retained
for provenance and excluded from the project pilot.

| Source | Candidate subset | Excluded subset | Role |
|---|---|---|---|
| Sotto transcript cleanup | Canonical pinned Parquet train split (135,503 rows before filtering) | Sotto validation and overlapping legacy JSONL | Main source for cleanup operations |
| Disfl-QA | Publisher train (7,182 rows) | Publisher dev (1,000) and test (3,643) | Human-authored question corrections/restarts |
| Nyra Disfluency Speech English | Publisher train text fields (4,458 rows) | Publisher validation/test and embedded audio | Audio-backed filler/repetition supplement |
| Project supplement v1 | 2,800 deterministic pending candidates | None are automatically accepted | Fills measured paragraph, adversarial, and Unicode gaps |

The public import currently maps 147,142 rows into 63,990 ordinary candidates, 81,325 quarantine
candidates, and 1,827 rejected rows. Quarantine means “requires explicit review,” not “approved.”
The project supplement contains 720 adversarial-primary, 400 paragraph-primary, 960
protected-literal-primary, 480 filler/repetition-primary, and 240 correction-primary candidates.
Its overlapping safety labels include 1,440 adversarial, 1,576 Unicode/multilingual, 1,500
technical, 2,016 must-not-answer/question/command, 696 long-form, and 240 high-stakes rows.

Families, templates, exact duplicates, and near-duplicates are grouped before splitting. No family
or template may cross train/dev. Every selected row is checked against the two frozen 69-case
diagnostic corpora; those corpora, their expected outputs, historical model results, and blind-v2
references are never training or generation data.

## Generated variants

Supplement v1 is deterministic and uses multiple variants within a shared family ID so variants
cannot leak across splits:

- Adversarial families include clean punctuation variants, quoted/nested instruction variants,
  long-context variants, filler and repetition edits, and explicit correction variants.
- Paragraph families vary the explicit paragraph directive while preserving the same two content
  clauses and any Unicode span.
- Unicode families combine a reviewed non-ASCII span with technical literals and ordinary
  punctuation/capitalization cleanup.

Generated rows remain candidates. They do not become labels until a human approves the exact
raw/target pair under the annotation policy.

## Readiness gate

Training starts only after pilot Gate A passes. That means:

1. All 5,500 selected rows are human-approved, and all 500 dev rows are fully reviewed.
2. Source-license and human-review attestations are complete.
3. Schema, quota, provenance, source-holdout, frozen-overlap, family, and near-duplicate checks pass.
4. The sealed blind-evaluator contract exists, while blind-v2 references remain unavailable to
   the training context.
5. The sanitized Gate A report is committed before either base model is loaded.

## Training comparison

The same reviewed bytes and order train two LoRA adapters:

- `Qwen/Qwen3-0.6B` at pinned revision `61641f84fa567ab7b58e216b4930d2fe28bfd045`
- `Qwen/Qwen3.5-0.8B` at pinned revision `2fc06364715b967f1860aea9cf38778875588b17`

Both use assistant-only loss, seed 23, a 512-token maximum, effective batch size 32, three epochs,
learning rate 2e-4, and evaluation/checkpoint intervals of 50 optimizer steps. The expected pilot
length is about 471 optimizer steps per model; the trainer records the resolved value.

## Progress and evaluation harness

During training, `monitor_cleanup_run.py` watches one managed run every three minutes. It records
process/tmux identity, new console-log bytes, the latest training/evaluation metric, checkpoints,
GPU utilization and memory, temperature and power, disk space, and terminal status. It is
read-only: it never restarts or changes a run.

Training loss and held-out dev loss show optimization progress, but they are not the model-quality
decision. At saved checkpoints and at the final adapter, the evaluation harness:

1. runs deterministic raw adapter inference on all 500 reviewed dev rows;
2. scores raw exact match, preservation anchors, removal of superseded content, correction rows,
   clean/no-op rows, must-not-answer rows, per-category exactness, malformed/empty/capped output,
   and latency;
3. prepares every raw output for human semantic-safety review; and
4. runs the selected checkpoints on the retired 24-case and 45-case diagnostic corpora.

Raw output decides qualification. A guardrail fallback is reported separately and cannot turn an
unsafe model into a passing model. Checkpoint selection follows semantic safety first, correction
success second, exact match third, and latency only as a tie-breaker. Blind v2 is not used for
training progress or checkpoint selection.

The concrete launch, monitor, inference, and scoring commands are in `PILOT_RUNBOOK_V1.md`.
