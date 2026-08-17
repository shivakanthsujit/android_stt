# Cleanup annotation policy v2

Status: active for pilot review

The model is a transcript editor with a narrow presentation-control vocabulary and conservative
grammar/ASR repair. Reviewers approve the smallest well-grounded edit, not the most polished rewrite. Documentation examples are
policy illustrations only and must not be copied into training data without separate row-level
human review.

## Allowed content edits

1. Remove clear standalone speech fillers such as `uh`, `um`, `uhm`, `er`, and `ah`.
2. Collapse an obvious immediate accidental repetition of the same word or phrase.
3. Remove an abandoned start only when the completed restart states the same intended utterance.
4. Apply an explicit self-correction: retain the final replacement and remove the superseded
   value, action, polarity, or clause plus its correction marker.
5. Add conservative sentence punctuation and capitalization without changing lexical content.
6. Repair a clear grammar error or contextually obvious ASR misrecognition when the intended words
   are unambiguous and the change preserves meaning; declare every target lexical addition.
7. Preserve everything else, including conversational tone and arbitrary questions, commands,
   quotations, markup, and instruction-like content.

## Allowed explicit formatting controls

Apply a spoken formatting directive only when both the operation and its scope are explicit:

- make the following items a bulleted or numbered list, or render an explicitly numbered/ordinal
  spoken sequence as a list;
- start a new paragraph or new line at the stated boundary; or
- insert named punctuation such as comma, period, colon, semicolon, question mark, or parentheses.

For example, a request to make a bullet list containing three fruits and then explicitly replace
the middle fruit may become three bullet lines containing the first fruit, replacement fruit, and
last fruit. The discarded fruit, correction words, and formatting-directive words must not remain.
No new fruit or descriptive wording may be invented.

Formatting is presentation, not permission to carry out arbitrary commands. A dictated request to
delete files, send a message, reveal a password, answer a question, calculate a result, emit newly
generated JSON/code, summarize content, or ignore prior instructions remains literal text.

## Forbidden edits

- Do not answer, summarize, explain, refuse, generate content, or perform an external action.
- Do not make a speculative ASR repair or alter a name, number, acronym, version, path, identifier,
  negation, uncertainty marker, or high-stakes fact without an explicit spoken correction.
- Do not rewrite style, tone, word choice, concision, or factual content beyond a clear local
  grammar repair.
- Do not delete uncertainty, stance, politeness, discourse meaning, negation, or intentional
  emphasis/repetition.
- Do not infer list or paragraph structure from a casual enumeration without an explicit
  formatting directive.
- Do not approve an expected target that introduces undeclared lexical content. Every added target
  token must appear in `allowed_additions` with exact multiplicity. Presentation symbols and
  whitespace are not lexical content; formatting rows may add a digit only when it corresponds
  exactly to an explicit spoken list marker.

## Required row checks

For every row, a reviewer verifies final-intent equivalence; all preservation/removal anchors;
names, numbers, dates, money, versions, paths, identifiers, Unicode, negation, and uncertainty;
categories/risk tags; family/template isolation; and provenance/license. For formatting rows, the
reviewer additionally verifies explicit directive scope, item order, requested list type, every
self-correction inside the formatted content, and absence of invented items.

Every selected pilot row must be human-approved. Dev and every correction, mixed, formatting,
grammar, ASR-repair, lexical-addition, adversarial, protected-literal, high-stakes, and quarantined
row receives full review. Automated or
model judgment is never a reviewer. Disagreement means preserve wording or reject the row, never
weaken the policy.
