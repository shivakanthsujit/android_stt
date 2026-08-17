# Cleanup training dataset contract v1

Status: active authoring contract
Schema ID: `cleanup-training-record-v1`

The authoritative machine-readable shape is
`cleanup_training_record_v1.schema.json`. The project validator implements the schema plus
cross-record rules that JSON Schema cannot express. JSONL must be UTF-8, with one object per
nonblank line, and every string must already be Unicode NFC.

## Fields and policies

The required fields are `id`, `raw`, `expected`, `categories`, `must_preserve`, `must_remove`,
`risk_tags`, `source`, `family_id`, `template_id`, `split`, `review`, `license`, and
`generator_version`. The schema enumerates the accepted category, risk, source, split, and review
values. Change an enum only by versioning this contract rather than silently changing v1.

- `must_preserve` anchors are exact, case-sensitive substrings of `expected`.
- `must_remove` anchors are exact substrings of `raw` and must not occur in `expected`.
- `allowed_additions` is exceptional: each entry must occur in `expected`, and its lexical tokens
  are the only target tokens permitted beyond those in `raw`. Punctuation/case changes are not
  lexical additions.
- `family_id` groups semantic siblings. `template_id` groups structurally equivalent renderings.
  Neither identifier may appear in more than one split across all files passed to one validation
  command.
- `source_ref` is required for every source except a directly human-authored scenario. Consented
  real STT additionally requires pseudonymous `speaker_id` and `session_id` and must use the
  `real_canary` split. Do not place names or raw private identifiers in these metadata fields.
- `review.status=approved` requires at least one reviewer. Approved blind records require two or
  more reviewers and `adjudicated=true`. Use `--require-approved` for release/Gate A validation;
  ordinary validation permits draft and pending authoring rows.

The validator rejects duplicate IDs, duplicate normalized raw/expected pairs, undeclared lexical
additions, split leakage, and any raw or expected text equal to a frozen evaluation string after
NFC, case folding, and punctuation/whitespace removal. This is a strict first barrier, not the
planned n-gram near-duplicate review stage.

## Commands

Validate authoring files together so cross-file leakage is visible:

```bash
python3 scripts/validate-cleanup-training-data.py \
  data/cleanup/train-v1.jsonl data/cleanup/dev-v1.jsonl
```

Write a deterministic manifest containing SHA-256, byte sizes, record/split counts, schema and
validator hashes, the frozen-corpus hashes, and supplied generator/config hashes:

```bash
python3 scripts/validate-cleanup-training-data.py \
  --require-approved \
  --hash-artifact scripts/generate-cleanup-training-data.py \
  --hash-artifact data/cleanup/generator-v1.json \
  --write-manifest data/cleanup/manifest-v1.json \
  data/cleanup/train-v1.jsonl data/cleanup/dev-v1.jsonl
```

Repeat the command with `--check-manifest data/cleanup/manifest-v1.json` to detect any byte-level
change. The project frozen corpora are checked by default. `--frozen-case` replaces the defaults
for controlled tests; `--no-frozen-check` exists only for validator development and must never be
used to release data.
