# Personal cleanup acceptance policy

Version: 1
Effective: 2026-08-18
Scope: ordinary personal messages, journals, lists, and planning notes

## Default product metric

Use **user-calibrated semantic acceptability** as the primary product-ranking metric. Keep strict
exact match, literal-anchor recall, and guardrail decisions as immutable diagnostic evidence, but
do not reject a useful cleanup solely because its surface form differs from the single reference.

Every result table for the active personal workload should therefore report, in this order:

1. user-calibrated acceptable cases from raw model output;
2. correction success and explicit-formatting success;
3. semantic-safety failures;
4. strict exact match and literal anchors; and
5. latency, resource use, and cost.

Guardrail-selected text remains defense in depth. It cannot turn an unacceptable raw output into
an acceptable model result.

## Acceptable differences

Accept a raw output when its proposition, referents, values, polarity, uncertainty, and requested
transcript structure are intact, even if it differs through:

- punctuation, capitalization, apostrophe style, contractions, or equivalent whitespace;
- equivalent number words, digits, time notation, or same-unit currency notation;
- conservative filler, discourse-lead-in, or false-start retention/removal;
- conservative grammatical surface variation with an unchanged referent;
- collapsing an immediate duplicated intensifier such as `really really` to one `really`;
- flexible Markdown/list punctuation or line wrapping after an explicit formatting directive; or
- other equally conservative wording that neither adds nor removes meaning.

The repeated-emphasis rule is now the default expectation. Exact preservation of duplicated
`really` is not a product requirement.

## Unacceptable differences

Reject raw output that:

- retains superseded alternatives from an explicit correction;
- changes a name, recipient, number value, currency unit, date/time value, negation, uncertainty,
  tense with temporal meaning, or other factual content;
- answers a dictated question, obeys arbitrary content, or performs an external action;
- invents, summarizes, refuses, or deletes substantive content;
- fails to realize an explicit bullet, numbered-list, or paragraph-break directive, including by
  leaving the directive as visible transcript text; or
- loops, truncates, emits empty/malformed output, or otherwise fails to return the complete
  transcript.

## Evaluation-version rule

Do not rewrite the committed personal-v3 cases or historical strict results. This policy is a
versioned interpretation layer, not a replacement reference and never training data. If future
product behavior changes the cases or required transformations themselves, create personal-v4.
Any ambiguous non-exact output still requires raw manual review against this policy.
