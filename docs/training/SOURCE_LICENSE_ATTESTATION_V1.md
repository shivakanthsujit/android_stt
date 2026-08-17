# Source license attestation v1

Gate A requires a human to inspect the downloaded license/card evidence for every pinned public
source. The local attestation stays under `/data/rise/android_stt/reviews/` and is not committed;
the sanitized Gate A report records only its SHA-256.

Use this JSON shape, replacing the manifest hash and evidence paths with values from the actual
source manifest:

```json
{
  "attestation_version": "cleanup-source-license-attestation-v1",
  "source_manifest_sha256": "64-lowercase-hex-characters",
  "sources": [
    {
      "id": "sotto",
      "license": "MIT",
      "auditor_ref": "reviewer-a",
      "audited_at": "2026-08-17",
      "evidence_files": ["README.md"],
      "statements": {
        "terms_reviewed": true,
        "attribution_recorded": true,
        "research_training_permitted": true
      }
    }
  ]
}
```

The `sources` array must contain exactly `sotto`, `disfl_qa`, and `nyra`, with the configured
license label for each. Every `evidence_files` entry must be a path present under that source in
the immutable fetch manifest. Add no `true` conclusion unless a human actually reviewed the
downloaded evidence and confirmed the proposed research-training use and attribution obligations.
