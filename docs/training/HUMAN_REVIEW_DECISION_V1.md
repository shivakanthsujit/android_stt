# Human review decision format v1

Review decisions stay in the ignored training-data workspace and are never committed. One JSONL
object records one human review of one candidate:

```json
{"id":"candidate-sotto-example","decision":"approved","reviewer_ref":"reviewer-a","reviewed_at":"2026-08-17","reason":"Minimal unambiguous filler removal."}
```

Required fields are `id`, `decision`, `reviewer_ref`, and `reviewed_at`. `decision` is `approved`
or `rejected`; `reviewed_at` is `YYYY-MM-DD`; `reason` is optional but recommended. Use a stable
pseudonymous reviewer reference rather than an email address or legal name.

The application tool rejects unknown row IDs, duplicate decisions by one reviewer, malformed
dates, and all blind records. Conflicting decisions remain pending until a human adjudicates them.
It never infers or generates approval decisions.

```bash
python3 scripts/training/apply_cleanup_reviews.py \
  --records /data/rise/android_stt/work/import/candidate.jsonl \
  --records /data/rise/android_stt/work/import/quarantine.jsonl \
  --decisions /data/rise/android_stt/reviews/reviewer-a.jsonl \
  --output-root /data/rise/android_stt/work/reviewed
```

After applying decisions, build the release pilot from `approved.jsonl` without
`--allow-pending`. The pilot builder and schema validator independently reject unapproved rows.
