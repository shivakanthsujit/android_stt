# Cleanup training dataset contract v2

Status: active authoring contract
Schema ID: `cleanup-training-record-v2`

The authoritative machine-readable shape is `cleanup_training_record_v2.schema.json`. V2 retains
all V1 provenance, review, anchor, lexical-addition, split, and frozen-overlap rules and adds an
explicit distinction between formatting controls and arbitrary dictated commands, plus labeled
grammar/ASR repair and exact lexical-addition provenance.

## Formatting policy fields

The additional categories are `formatting_directive`, `spoken_punctuation`, `list_formatting`, and
`paragraph_formatting`; `formatting_scope` marks a scope-sensitive risk. A formatting row must:

- contain an explicit directive or explicit spoken number/ordinal sequence whose scope is
  unambiguous;
- remove only the directive words, disfluencies, and superseded list items;
- preserve every final list item and content word;
- add only presentation characters, whitespace, or a declared numeral corresponding exactly to
  a spoken ordinal/cardinal marker; and
- receive human review before pilot use.

Requests for answers, summaries, calculations, generated content, code execution, external
actions, or arbitrary output remain literal transcript content. `formatting_directive` must not be
used to relabel prompt injection as an editor control.

## Other fields and validation

Required fields remain `id`, `raw`, `expected`, `categories`, `must_preserve`, `must_remove`,
`risk_tags`, `source`, `family_id`, `template_id`, `split`, `review`, `license`, and
`generator_version`. `must_preserve` and `must_remove` are exact case-sensitive anchors.
`allowed_additions` is exceptional and must enumerate any lexical target token absent from raw;
repeated additions are repeated in the array so token multiplicity is exact. Formatting symbols
alone do not require it. `grammar_rewrite`, `asr_correction`, and `lexical_addition` identify the
broader reviewed product behavior; `inferred_content`, `lexical_addition`, and `high_stakes` make
the corresponding review risks explicit.

The validator rejects duplicate IDs and normalized pairs, undeclared lexical additions, split
leakage, frozen diagnostic overlap, invalid review state, and unknown fields/enums. Pass all files
together and use `--require-approved` plus a deterministic manifest for Gate A. V1 remains in the
repository only to explain older records; new pilot data uses V2.
