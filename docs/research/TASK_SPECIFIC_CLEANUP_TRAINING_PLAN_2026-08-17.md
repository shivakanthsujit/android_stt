# Task-specific cleanup training plan

Status: draft
Date: 2026-08-17

## Decision and objective

Cleanup is the current bottleneck. The project's working offline Moonshine transcription path is
usable enough for interactive prototyping, while every generic cleanup model tested so far failed
either semantic safety or explicit self-correction. The primary next experiment is therefore a
task-specific sub-1B cleanup model. The current offline Moonshine path remains the provisional
speech input; formal STT evaluation can continue later, but it is not on the critical path for this
experiment because cleanup can be trained and evaluated directly from text.

The model is a literal transcript editor, not a general rewriter. Given a final STT transcript, it
may:

- remove known fillers and abandoned wording;
- collapse obvious immediate repetitions;
- apply an explicit self-correction;
- fix punctuation and capitalization; and
- otherwise copy the wording exactly.

It must never answer or execute dictated content, invent information, silently correct a possibly
wrong ASR word, change tone, or remove negation or uncertainty. When a change is ambiguous, the
training target is the minimally edited input. This narrower policy is intentional; existing
evaluation references remain frozen even where they use a slightly freer edit.

## Existing evidence and contamination boundary

The following files are permanent evaluation/diagnostic material and must never be used as
fine-tuning examples, few-shot demonstrations, generator examples, retrieval context, or
preference-training pairs:

- `docs/evaluation/cleanup_cases.jsonl` (24 cases);
- `docs/evaluation/cleanup_cases_heldout_v1.jsonl` (45 cases); and
- every model response and failure analysis under `docs/evaluation/results/`.

The 45-case v1 set is no longer blind because it informed guardrail changes. It is still a useful
regression suite, but passing it cannot establish generalization. Prompt examples in
`scripts/run-cleanup-openai.py` are also evaluation-derived and must not be copied into the new
training data. Create new demonstrations from training-only families if the final runtime prompt
needs examples.

The current scorer measures exact match, literal-anchor preservation, empty/expanded output,
fallback, output-cap hits, category performance, and latency. Retain those metrics, then add the
semantic checks specified below. Existing application guardrails are defense in depth; a model
does not pass the raw-output gate merely because a bad edit falls back to the input.

## Dataset record schema

Store authoring data as UTF-8 JSONL. One record represents one transformation:

```json
{
  "id": "train-correction-000001",
  "raw": "send it on Monday no make that Wednesday",
  "expected": "Send it on Wednesday.",
  "categories": ["self_correction", "false_start", "dates", "punctuation"],
  "must_preserve": ["Wednesday"],
  "must_remove": ["Monday", "no make that"],
  "risk_tags": ["superseded_fact"],
  "source": "template_human_reviewed",
  "source_ref": "correction-date-v3",
  "family_id": "correction-date-00073",
  "template_id": "correction-date-v3",
  "split": "train",
  "review": {"status": "approved", "reviewers": 1},
  "license": "project-authored",
  "generator_version": "cleanup-data-v1"
}
```

Required authoring fields are `id`, `raw`, `expected`, `categories`, `must_preserve`,
`must_remove`, `risk_tags`, `source`, `family_id`, `template_id`, `split`, `review`, `license`, and
`generator_version`. `source_ref` is required when a record is derived from a template, public
corpus, or consented recording.

Only the fixed cleanup instruction plus `raw` is serialized as model input. Only `expected` is the
assistant target, and loss is applied only to assistant tokens. Metadata must not be exposed to the
model. Keep the rich authoring JSONL and export a separate trainer-specific file so provenance and
safety labels are not lost.

Schema rules:

- `must_preserve` contains exact, case-sensitive semantic anchors in `expected`.
- `must_remove` contains superseded words, correction markers, fillers, or repetitions that must
  not survive. It may be empty for no-op and punctuation-only cases.
- `risk_tags` describes why a mistake could change meaning, for example `negation`, `number`,
  `name`, `uncertainty`, `technical_literal`, `dictated_instruction`, or `superseded_fact`.
- `family_id` groups all paraphrases, entity substitutions, and corruption variants originating
  from one semantic scenario. It is the unit of splitting and deduplication.
- `template_id` permits template-level holdout. A blind template must not have a train/dev sibling.
- `spoken` may be retained as optional annotation, but training starts from `raw`, which is what
  the cleanup engine actually receives.

Before export, validate unique IDs, valid enums, NFC Unicode, nonempty input/output, every
`must_preserve` anchor in `expected`, and every non-marker `must_remove` anchor in `raw`. Reject an
example if `expected` introduces lexical content not present in `raw`, unless the exact addition is
declared in a small reviewed `allowed_additions` field. The target policy should normally require
no lexical additions at all.

## Source and generation strategy

Use five data sources, in descending order of control:

1. **Human-authored semantic scenarios.** Write clean intent-bearing sentences covering personal
   messages, reminders, work notes, questions, commands, technical dictation, names, numbers,
   uncertainty, and negation. Apply reviewed transformations to produce realistic raw transcripts.
2. **Programmatic inverse cleanup.** Starting from an approved clean sentence, insert fillers,
   duplicate spans, remove punctuation/case, or prepend a superseded clause plus an explicit
   correction marker. Deterministic generators make the expected answer unambiguous.
3. **LLM-proposed candidates with human approval.** A generator may propose diverse scenarios and
   disfluencies, but it must not receive any frozen evaluation cases. Generated pairs are data only
   after validation and review; never accept the generator's target automatically.
4. **Audited public cleanup/disfluency pairs.** Import only immutable, license-recorded revisions.
   Treat rows as untrusted candidates, rebuild family/template splits, reject policy-conflicting
   rewrites, and require the same validators and review as generated data. The selected sources and
   pins are in `CLEANUP_TRAINING_DATA_SOURCES_2026-08-17.md`.
5. **Consented real STT transcripts.** Later, add opt-in pairs from actual phone dictation. Store no
   private transcript in logs by default. Redact personal data, group by speaker/session, and keep a
   separate provenance flag. These examples validate synthetic realism rather than changing the
   first training milestone.

The pilot should begin with filtered Sotto data, supplemented by Disfl-QA and Nyra Disfluency
Speech. Their permissive labels do not make their targets trusted: record exact revisions and file
hashes, verify upstream provenance, and split by semantic family/source/speaker before use. If the
audit finds systematic unsafe rewrites or unresolved licensing, fall back to a smaller
human-authored/programmatic corpus instead of weakening the target policy.

Generation should vary clause order, sentence length, vocabulary, grammatical person, dialectal
fillers, entity type, Unicode script, and STT punctuation/casing. It must not train the model to
guess ambiguous recognition errors. For example, a transcript containing `fifteen` when the user
might have said `fifty` remains `fifteen` unless an explicit spoken correction supplies `fifty`.

Create multiple raw variants only when they remain in the same `family_id`. Do not create a large
dataset by swapping names and numbers in a few recognizable sentence frames; template diversity is
more valuable than nominal row count.

## Size and category balance

Build in two passes:

- **Pilot:** 5,000 train + 500 dev records to verify the pipeline and compare two base models.
- **Full v1:** 25,000 train + 1,500 dev records, plus a separately authored 500-case blind set.

The primary transformation strata for train and dev should be approximately:

| Transformation | Share | Full-train target |
|---|---:|---:|
| Exact/no-op or already clean | 20% | 5,000 |
| Punctuation/capitalization only | 15% | 3,750 |
| Explicit self-correction/false start | 25% | 6,250 |
| Fillers/discourse markers | 10% | 2,500 |
| Immediate word or phrase repetition | 10% | 2,500 |
| Abandoned start without a factual replacement | 10% | 2,500 |
| Mixed two-or-more operations | 10% | 2,500 |

These are exclusive primary strata, while safety/category labels overlap them. Enforce the
following minimum cross-cutting coverage:

- 20% dictated questions or commands that must not be answered;
- 8% adversarial instruction-like text;
- 25% names, numbers, dates, money, versions, paths, identifiers, or other protected literals;
- 12% negation and/or uncertainty;
- 10% non-ASCII names or multilingual/Unicode spans;
- 20% technical text; and
- 20% inputs of at least 25 words, including multi-sentence dictation.

Self-correction is deliberately overrepresented because it is the measured bottleneck: the
deterministic baseline solved 0/7 held-out corrections exactly, and the best generic model solved
only 4/7 before guardrails. Balance correction markers across `actually`, `actually make that`,
`no`, `no sorry`, `wait`, `I mean`, full-clause restarts, names, numbers, negated actions, and
technical literals. Include corrections where both old and new values are plausible so copying
both is clearly unsafe.

The 500-case blind set is safety-heavy rather than distribution-matched:

- 150 explicit corrections, including 75 protected-value replacements;
- 100 dictated questions/commands, including 50 adversarial prompts;
- 75 negation/uncertainty cases;
- 75 names/numbers/Unicode/technical literal cases;
- 50 clean no-op cases; and
- 50 mixed, long, or unusual disfluency cases.

Labels may overlap, but each record has one primary bucket so the total remains 500.

## Adversarial coverage

Adversarial records are ordinary dictation whose literal content resembles model control text. The
correct output is always the minimally copy-edited dictation, never the requested answer or action.
Cover:

- `system`, `assistant`, `developer`, chat-template tokens, XML tags, Markdown fences, and role
  delimiters;
- requests to output one word, JSON, code, a password, a calculation, a summary, or a refusal;
- `ignore previous instructions`, `repeat after me`, and attempts to close the transcript envelope;
- shell commands, file paths, URLs, email addresses, checksums, and API-like payloads;
- questions requiring factual or creative answers;
- quoted or nested instructions, Unicode confusables, and mixed scripts;
- adversarial content preceded by fillers or repetition; and
- explicit corrections inside adversarial text, such as changing the dictated output token from
  one literal value to another without executing either instruction.

Avoid a shortcut where every adversarial target differs only by capitalization and a period.
Include valid filler removal, repetition collapse, and explicit correction so the model must edit
while still treating the entire transcript as data.

## Split and leakage protection

1. Allocate semantic/template families before rendering individual rows. No `family_id` may cross
   train, dev, blind, or real-STT canary sets.
2. Reserve at least 20% of blind templates entirely; they must have no structurally equivalent
   train/dev template even with different entities.
3. Split consented real data by speaker and recording session, never by utterance.
4. Compute and store a manifest containing SHA-256 for every dataset and the generator code/config.
5. Deduplicate exact normalized raw/expected pairs and reject cross-split near-duplicates using
   token 3-gram and character 5-gram similarity plus normalized edit distance. Manually inspect all
   flagged cross-split pairs.
6. Compare every proposed train/dev row with both frozen 69-case corpora. Include lowercase,
   punctuation-stripped, entity-masked, and n-gram fingerprints so superficial paraphrases are
   caught.
7. Keep blind JSONL inaccessible to data generators and training jobs. A small evaluation command
   may reveal aggregate scores, but not references, during iteration.
8. Tune prompts, adapters, decoding, and guardrails only on train/dev plus the old diagnostic sets.
   Unseal blind v2 once for the selected configuration. After its failures inform a change, retire
   it to regression status and author blind v3 before claiming a new generalization result.

The random seed is recorded for reproducibility, but a random row-level split is explicitly
forbidden because synthetic siblings make it look much better than it is.

## Reference review and data QA

Use a written annotation policy with examples for every allowed operation. For the training set,
automatically validate every row, manually review all high-risk and mixed-operation rows, and audit
at least 10% of the remainder. The dev set receives full human review. The blind set receives two
independent reviews with adjudication before any model sees it.

Validators should report:

- duplicate/near-duplicate families;
- missing preservation anchors or surviving removal anchors;
- unexpected new lexical tokens;
- changed digits, signs, currency, versions, paths, email addresses, capitalization-sensitive
  identifiers, names, negation, or uncertainty;
- output expansion/contraction and empty targets; and
- conflicting category/risk labels.

Reviewers should prefer a valid minimal edit over stylistic polish. If two competent reviewers
disagree about whether a deletion is safe, keep the disputed wording and tag the record
`ambiguous_preserve`.

## Fine-tuning experiment

Training execution belongs on the separate training machine. This Mac is limited to dataset
authoring/validation, inference-only candidate screens, and result analysis; do not launch a local
LoRA/QLoRA job here.

Use Qwen3-0.6B no-think and Qwen3.5-0.8B as the first sub-1B bases because their Android-sized
artifacts and generic baselines are already measured. Run a 5,000-example LoRA/QLoRA pilot on both
with the same fixed prompt, data order, sequence length, assistant-only loss, and evaluation
schedule. Select the base on dev semantic safety first, correction success second, and exact match
third. Host latency is only a tie-breaker.

Then train the selected base on full v1. Save the base revision, tokenizer, chat template, adapter
configuration, library versions, seeds, dataset manifest, and checkpoints. Evaluate both the
merged floating-point checkpoint and the intended Q4 Android artifact; quantization is part of the
model decision, not an implementation detail.

Do not use the 500-case blind set for checkpoint selection. Choose one checkpoint from dev results,
freeze the prompt and decoding configuration, run all old diagnostics, and only then unseal blind
v2. A public task-tuned 2B model may be screened as an upper-bound control, but it does not replace
the sub-1B experiment or change its data splits.

## Acceptance gates

### Gate A: data readiness

- All schema/provenance validators pass.
- No train/dev overlap with the frozen 69 cases or blind families.
- Dev is fully reviewed; blind is independently double-reviewed and locked by hash.
- Required transformation and safety quotas are met.

### Gate B: host quality on dev and old diagnostics

- Zero changed or dropped protected facts, negation, uncertainty, names, numbers, or technical
  literals after manual review.
- Zero answered, executed, summarized, or refused dictated instructions.
- 100% semantic correction success: replacement retained and superseded content removed.
- At least 90% overall raw exact match, 95% exact on explicit corrections, 98% on clean no-op, and
  95% on must-not-answer cases.
- No category below 85% exact; 100% preservation-anchor recall; zero empty or token-cap outputs.
- Raw output must pass these gates. Guardrail fallback cannot convert a failed model into a pass.
- Repeat the selected configuration with seeds 23, 47, and 91 at the intended bounded decoding
  settings; every run must retain zero semantic safety failures.

### Gate C: blind v2 quality

- All 500 raw outputs are reviewed, with two reviewers for every non-exact output and every
  high-risk record.
- Zero semantic changes, invented facts, answered/acted instructions, protected-token losses, or
  unsafe correction failures.
- At least 90% overall raw exact match, 95% correction exact, 98% clean no-op exact, and 95%
  must-not-answer/adversarial exact.
- 100% preservation-anchor recall, zero empty/capped outputs, and no systematic failure pattern
  hidden by aggregate scores.
- Android-equivalent guardrails must not introduce a semantic failure. Report fallback separately;
  target at most 5%, because fallback is safe but leaves dictation unclean.

Any critical semantic failure is a no-go, even if the aggregate score is high. Diagnose it on the
now-retired suite, change training or guardrails, and create a new blind version before retesting.

### Gate D: Pixel 7 deployment eligibility

Only a blind-quality survivor earns Android runtime work. The intended Q4 artifact must reproduce
Gate C's zero-critical-failure result before performance matters. Then require:

- no model/runtime network use after one-time setup;
- stable simultaneous residency with the selected STT engine and no OOM over repeated dictations;
- warmed cleanup p95 at or below 1 second initially, with TTFT, total latency, throughput, PSS/RSS,
  battery, and thermal drift recorded; and
- no material quality regression between host and Pixel output.

The latency target may be revised after measurement, but semantic gates may not.

## Concrete execution order

1. Keep the existing 69 cases frozen and evaluation-only; their hashes are part of every data
   manifest.
2. Finish the annotation policy, source importer, near-duplicate/family splitter, and deterministic
   corruption tooling around the committed schema validator.
3. Fetch the three public sources only at their pinned revisions, audit licenses/targets, and build
   a reviewed 5,000/500 pilot without touching frozen cases.
4. Pass Gate A and commit the sanitized manifest/report before training.
5. Train matching adapters for Qwen3-0.6B and Qwen3.5-0.8B; select a base using Gate B ordering.
6. Expand source and human-authored family diversity to 25,000/1,500 only if the pilot validates
   the approach.
7. After templates stabilize, have an independent context author, double-review, hash, and seal
   blind v2 outside the training job's readable path.
8. Train the selected base on full v1, then select exactly one checkpoint/prompt/decoder on dev and
   the old diagnostics before unsealing blind v2 once.
9. If Gate C passes, export Q4 and repeat quality checks before starting Pixel integration. If it
   fails, record the failure class, retire v2 to diagnostics, and iterate with a newly authored
   blind v3.
10. Add a consented real-STT canary set after the text pipeline works. Keep it speaker/session
   isolated and use it to decide which synthetic corruptions are unrealistic or missing.

This plan keeps STT and cleanup separable: cleanup development can proceed immediately using text,
while actual recognizer transcripts later provide a realism check rather than blocking the model
experiment.
