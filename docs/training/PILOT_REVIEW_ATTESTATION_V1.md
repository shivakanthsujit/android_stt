# Pilot human-review attestation v1

Gate A requires a local attestation file outside Git. It contains no transcript text. The human
reviewer or review coordinator creates JSON with this shape:

```json
{
  "attestation_version": "cleanup-pilot-review-attestation-v1",
  "policy_sha256": "64-lowercase-hex-characters",
  "review_completed_at": "2026-08-17",
  "reviewer_refs": ["reviewer-a"],
  "statements": {
    "all_selected_rows_human_reviewed": true,
    "all_dev_rows_human_reviewed": true,
    "all_correction_mixed_adversarial_protected_rows_human_reviewed": true,
    "all_formatting_rows_human_reviewed": true,
    "all_grammar_asr_lexical_addition_high_stakes_rows_human_reviewed": true,
    "no_model_or_automated_approval_substituted_for_human_review": true,
    "no_blind_references_were_accessed": true
  }
}
```

`policy_sha256` must match `docs/training/ANNOTATION_POLICY_V2.md`. Reviewer references must cover
the pseudonymous reviewer references present on all selected rows. The Gate A tool hashes this
local file but omits reviewer identities and its path from the sanitized committed report.
