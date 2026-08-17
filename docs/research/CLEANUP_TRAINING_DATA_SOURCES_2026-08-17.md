# Cleanup training data sources

Status: sources selected for audit, not yet imported or approved

Verified: 2026-08-17

## Decision

Use public data to reduce custom generation, but treat every row as an untrusted candidate. The
primary source is the Sotto transcript-cleanup dataset because it directly matches raw ASR text to
cleaned text. Disfl-QA supplies human-authored correction/restart questions, and Nyra
Disfluency Speech supplies a smaller audio-backed verbatim/intended supplement.

None of these sources replaces project-specific validation, family-level splitting, manual review,
the safety-heavy blind set, or later Moonshine transcript canaries. Do not train directly from a
publisher's split or unfiltered targets.

## Immutable source pins

| Role | Source | Immutable revision | Declared license |
|---|---|---|---|
| Primary | [Sotto transcript cleanup](https://huggingface.co/datasets/juanquivilla/sotto-transcript-cleanup) | `183cc8fd58532f13fa192980185214de1bcd5acc` | MIT |
| Question corrections | [Disfl-QA](https://github.com/google-research-datasets/Disfl-QA) | `1f0c16171c77b3d3408be92c485f11b8998a9189` | CC BY 4.0 |
| Audio-backed supplement | [Nyra Disfluency Speech English](https://huggingface.co/datasets/nyralabs/disfluency_speech_english) | `723e9e69bfbdc8214a9b8ce8815985e90afcbaa3` | Apache-2.0 |

These are source repository revisions, not downloaded-file checksums. The training-machine fetcher
must additionally record every retrieved payload's SHA-256 and byte count in the project manifest.
Never resolve `main` implicitly during a released dataset build.

License labels come from the respective publisher cards/repository. They are inputs to the
provenance review, not a legal guarantee about every upstream sentence. Preserve attribution and
investigate any upstream provenance conflict before distributing a trained derivative.

## Sotto transcript cleanup

The publisher describes over 100,000 synthetic raw/clean transcript pairs spanning explicit
self-corrections, no-op preservation, fillers, mixed disfluencies, false starts, dictation
punctuation commands, grammar, guessed ASR errors, formatting, and adversarial filler-like text.
Generation combines deterministic corruption, LLM generation, and hand-written examples.

Why it is useful:

- The task format directly matches this project's cleanup interface.
- It includes explicit correction and preserve-wording categories that target our measured
  bottlenecks.
- It contains technical and protected-literal examples at much greater scale than we can author
  manually for the pilot.

Why it cannot be used wholesale:

- It is mostly synthetic rather than transcripts from our Moonshine path.
- Its public card reports inconsistent totals: an older 118,069/6,215 split summary coexists with
  a newer viewer total around 142,424. Derive counts from the pinned files.
- `grammar` targets intentionally rewrite wording.
- `misheard_words` targets guess ASR corrections without an explicit spoken repair.
- Some crutch-word targets delete stance or discourse that this project preserves when ambiguous.
- Some list, paragraph, medical, legal, financial, mixed, and novel-token targets make edits beyond
  the project's conservative policy.
- A publisher-reported automated validation rate does not establish semantic safety for our app.

Default policy:

- Prefer `self_correction`, conservative `false_start`, `filler_removal`, immediate repetition,
  and `preserve_wording` candidates.
- Reject `misheard_words` by default.
- Reject grammar-only rewrites by default.
- Quarantine crutch-word, dictation-command, list/paragraph, mixed, high-stakes-domain, and
  lexical-addition rows for explicit policy review.
- Require correction targets to retain the final replacement and remove every superseded value or
  action.
- Require exact preservation checks for uncertainty, negation, names, numbers, dates, money,
  versions, paths, identifiers, acronyms, and Unicode spans.
- Rebuild train/dev splits by semantic family/template after deduplication.

The related Sotto 350M model is evidence that task-specific training may work, not an evaluator or
trusted labeler. It was trained on this dataset and cannot provide an independent quality judgment
of its targets.

## Disfl-QA

Disfl-QA contains 11,825 pairs derived from SQuAD-v2 questions: 7,182 train, 1,000 dev, and 3,643
test. Each record provides an original fluent question and a human-authored disfluent question.
The authors report that more than 90% of its disfluencies are corrections or restarts.

Why it is useful:

- Map `disfluent` to raw and `original` to expected for correction candidates.
- Questions force the cleanup model to edit question text rather than answer it.
- Human-introduced contextual distractors are more realistic than simple word swaps.

Limitations and policy:

- It is an information-seeking question domain, not dictation or ASR output.
- It inherits content structure from SQuAD/Wikipedia and requires attribution tracking.
- Publisher train/dev/test partitions are not project splits.
- Group by the source question/article and detected template before project splitting.
- Audit punctuation/case normalization and reject unnatural or meaning-ambiguous insertions.
- Use it as a correction/must-not-answer supplement, not the majority of the pilot.

## Nyra Disfluency Speech English

The publisher provides 4,957 English utterances and about 9.4 hours of audio with
`verbatim_transcript` and `intended_transcript` fields. The dataset is derived from the AMAAI Lab
DisfluencySpeech release and contains fillers, cutoffs, repetitions, and sound events.

Why it is useful:

- It supplies paired verbatim/intended text backed by audio.
- It can test whether synthetic text patterns resemble actual spoken disfluencies.
- The audio can later support a separate STT realism check.

Limitations and policy:

- It is single-speaker, reenacted conversational speech rather than personal dictation.
- Its annotation tags and cleanup conventions differ from Moonshine output.
- Remove or map sound/cutoff tags through an explicit documented policy.
- Split by speaker/source/session where metadata permits; never randomly split sibling utterances.
- Keep a portion as a realism canary instead of consuming all rows for training.

## Explicit exclusions

- Do not use either committed 69-case evaluation corpus or any model result derived from it.
- Do not use the VoiceInk system prompt, captured responses, private author data, or undeclared
  fine-tune artifact as training examples.
- Do not use Switchboard/LDC material unless the exact obtained distribution license permits the
  planned model training and artifact use.
- Do not use a dataset merely because its repository metadata states a permissive license when its
  upstream provenance contradicts that label.
- Do not ingest personal transcripts without explicit consent, pseudonymization, and
  speaker/session isolation.

## Pilot source strategy

Start with a 5,000/500 filtered pilot rather than the full public corpus. Approximate source/task
targets are defined in `TRAINING_MACHINE_HANDOFF.md`; the authoritative category and safety quotas
remain in the task-specific training plan.

For every accepted record, preserve:

- source repository and immutable revision;
- upstream row identifier or deterministic source reference;
- declared license and attribution;
- project family/template IDs;
- transformation and risk labels;
- required-preserve and required-remove anchors;
- review status and reviewers; and
- generator/importer version.

Run `scripts/validate-cleanup-training-data.py` across all splits in one invocation. The future
importer must add near-duplicate detection and generate a deterministic manifest that includes
source payload, schema, validator, importer, configuration, frozen corpora, and output hashes.

## Go/no-go for source use

A source is usable only when:

- its exact revision and payload hashes are recorded;
- license/provenance review is documented;
- rows can be mapped without weakening the v1 schema;
- frozen and family/template overlap checks pass;
- unsafe target classes are rejected or quarantined;
- the required review sample finds no systematic meaning-changing pattern; and
- accepted data meets project quotas without padding from ambiguous rows.

If Sotto fails this audit, retain its generation taxonomy as research evidence and fall back to a
smaller human-reviewed dataset. Do not lower the cleanup policy to accommodate a public corpus.
