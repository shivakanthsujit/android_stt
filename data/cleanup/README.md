# Cleanup data workspace

This directory documents the local training-data layout. Bulk data and private references are
ignored by git and must not be published through this repository.

Expected local layout on the training machine:

```text
data/cleanup/
  raw/          # immutable pinned source payloads
  work/         # converted, filtered, quarantined, and review-stage data
  private/      # personal or unsealed blind references; never commit
  manifests/    # local manifests; commit only reviewed, path-sanitized versions
```

Before creating any files, read `TRAINING_MACHINE_HANDOFF.md`,
`docs/research/CLEANUP_TRAINING_DATA_SOURCES_2026-08-17.md`, and
`docs/training/DATASET_SCHEMA_V1.md`.

Downloaded data, processed bulk rows, personal transcripts, and blind references stay local.
Reviewed schemas, importer code, source pins, sanitized manifests, and aggregate reports belong in
git. Never commit credentials or machine-specific absolute paths.
