# RTX A6000 cleanup pilot runbook v1

This runbook operates only on the reviewed 5,000-train/500-dev pilot. All datasets, caches, model
weights, adapters, checkpoints, run logs, and review queues stay under
`/data/rise/android_stt/`. Never point these commands at blind-v2.

## 1. Locked environment and immutable source fetch

```bash
cd /home/shiva/android_stt
bash scripts/training/setup_training_env.sh

bash scripts/training/run_with_training_env.sh scripts/training/fetch_cleanup_sources.py \
  --root /data/rise/android_stt/raw/sources-v1 \
  --manifest /data/rise/android_stt/manifests/source-manifest-v1.json

bash scripts/training/run_with_training_env.sh scripts/training/fetch_cleanup_sources.py \
  --root /data/rise/android_stt/raw/sources-v1 \
  --manifest /data/rise/android_stt/manifests/source-manifest-v1.json \
  --check
```

The fetch includes source-native train/dev/test payloads for immutable provenance. Import is
restricted to each source's configured training subset; Gate A independently rejects any selected
row whose source reference points to an upstream holdout. Sotto's canonical Parquet is the only
candidate representation; its overlapping legacy JSONL is provenance-only. Nyra import projects
only transcript/provenance columns and does not materialize embedded audio.

## 2. Import and measure candidate coverage

```bash
bash scripts/training/run_with_training_env.sh scripts/training/import_cleanup_sources.py \
  --source-manifest /data/rise/android_stt/manifests/source-manifest-v1.json \
  --source-root /data/rise/android_stt/raw/sources-v1 \
  --output-root /data/rise/android_stt/work/import-v1

bash scripts/training/run_with_training_env.sh scripts/training/audit_cleanup_candidate_coverage.py \
  --input /data/rise/android_stt/work/import-v1/candidate.jsonl \
  --input /data/rise/android_stt/work/import-v1/quarantine.jsonl \
  --output /data/rise/android_stt/manifests/candidate-coverage-v1.json
```

Inspect the text-free import and coverage reports before authoring supplemental records. Do not
weaken a quota or approve unsafe public targets to fill a shortage. Any supplemental generator,
lexicon, and configuration must be committed and hashed before its rows can enter Gate A.

The pinned source profile requires supplemental paragraph, adversarial, and Unicode/multilingual
coverage. Generate the deterministic pending-review pool outside Git, then validate it:

```bash
bash scripts/training/run_with_training_env.sh scripts/training/generate_cleanup_supplement.py \
  --output-root /data/rise/android_stt/work/supplement-v1

bash scripts/training/run_with_training_env.sh scripts/validate-cleanup-training-data.py \
  /data/rise/android_stt/work/supplement-v1/supplement-candidates.jsonl
```

The generated rows are candidates, not labels: every selected row remains pending until an
explicit human decision is recorded. Commit the generator and `supplement-v1.json` configuration,
but never commit the generated JSONL.

## 3. Select pending rows and apply human review

Build a pending review selection from the complete non-rejected pool:

```bash
bash scripts/training/run_with_training_env.sh scripts/training/build_cleanup_pilot.py \
  --input /data/rise/android_stt/work/import-v1/candidate.jsonl \
  --input /data/rise/android_stt/work/import-v1/quarantine.jsonl \
  --input /data/rise/android_stt/work/supplement-v1/supplement-candidates.jsonl \
  --allow-pending \
  --output-root /data/rise/android_stt/work/pilot-review-round-1
```

Record actual human decisions using `HUMAN_REVIEW_DECISION_V1.md`. Apply the complete cumulative
decision ledger to the complete pool, then rebuild from approved plus still-pending records to
select replacements for rejected rows. Repeat until every selected row is approved. Automated or
model-generated approval is forbidden.

The optional terminal reviewer displays one selected raw/expected pair at a time and appends only
the human's explicit decision to an external ledger:

```bash
bash scripts/training/run_with_training_env.sh scripts/training/review_cleanup_candidates.py \
  --records /data/rise/android_stt/work/pilot-review-round-1/train.jsonl \
  --records /data/rise/android_stt/work/pilot-review-round-1/dev.jsonl \
  --decisions /data/rise/android_stt/reviews/pilot-decisions-v1.jsonl \
  --reviewer-ref reviewer-a
```

```bash
bash scripts/training/run_with_training_env.sh scripts/training/apply_cleanup_reviews.py \
  --records /data/rise/android_stt/work/import-v1/candidate.jsonl \
  --records /data/rise/android_stt/work/import-v1/quarantine.jsonl \
  --records /data/rise/android_stt/work/supplement-v1/supplement-candidates.jsonl \
  --decisions /data/rise/android_stt/reviews/pilot-decisions-v1.jsonl \
  --output-root /data/rise/android_stt/work/reviewed-v1

bash scripts/training/run_with_training_env.sh scripts/training/build_cleanup_pilot.py \
  --input /data/rise/android_stt/work/reviewed-v1/approved.jsonl \
  --input /data/rise/android_stt/work/reviewed-v1/pending.jsonl \
  --allow-pending \
  --output-root /data/rise/android_stt/work/pilot-review-round-2
```

After the selected round contains no pending/rejected row, apply the cumulative ledger once more
to a new reviewed output directory and build `pilot-release-v1` from its `approved.jsonl` without
`--allow-pending`.

```bash
bash scripts/training/run_with_training_env.sh scripts/training/apply_cleanup_reviews.py \
  --records /data/rise/android_stt/work/import-v1/candidate.jsonl \
  --records /data/rise/android_stt/work/import-v1/quarantine.jsonl \
  --records /data/rise/android_stt/work/supplement-v1/supplement-candidates.jsonl \
  --decisions /data/rise/android_stt/reviews/pilot-decisions-v1.jsonl \
  --output-root /data/rise/android_stt/work/reviewed-final-v1

bash scripts/training/run_with_training_env.sh scripts/training/build_cleanup_pilot.py \
  --input /data/rise/android_stt/work/reviewed-final-v1/approved.jsonl \
  --output-root /data/rise/android_stt/work/pilot-release-v1
```

## 4. Gate A

Complete the local human-review and source-license attestations using
`PILOT_REVIEW_ATTESTATION_V1.md` and `SOURCE_LICENSE_ATTESTATION_V1.md`, then run:

```bash
bash scripts/training/run_with_training_env.sh scripts/training/gate_a_cleanup.py \
  --train /data/rise/android_stt/work/pilot-release-v1/train.jsonl \
  --dev /data/rise/android_stt/work/pilot-release-v1/dev.jsonl \
  --source-manifest /data/rise/android_stt/manifests/source-manifest-v1.json \
  --source-root /data/rise/android_stt/raw/sources-v1 \
  --review-attestation /data/rise/android_stt/reviews/pilot-review-attestation-v1.json \
  --license-attestation /data/rise/android_stt/reviews/source-license-attestation-v1.json \
  --authoring-artifact scripts/training/generate_cleanup_supplement.py \
  --authoring-artifact training/config/supplement-v1.json \
  --local-manifest /data/rise/android_stt/manifests/pilot-training-manifest-v1.json \
  --report docs/evaluation/results/2026-08-17-pilot-gate-a.json
```

Inspect the sanitized report, rerun all tests, and commit/push it before loading either model.
Never commit either dataset, local manifest, attestation, source payload, or review ledger.

## 5. Formatting and GPU smoke sequence

Run the formatting audit once per tokenizer. Then run the same smoke controls for both model keys:

```bash
bash scripts/training/run_with_training_env.sh scripts/training/audit_cleanup_formatting.py \
  --model-key qwen3_0_6b \
  --train /data/rise/android_stt/work/pilot-release-v1/train.jsonl \
  --dev /data/rise/android_stt/work/pilot-release-v1/dev.jsonl \
  --gate-a-report docs/evaluation/results/2026-08-17-pilot-gate-a.json \
  --output /data/rise/android_stt/manifests/qwen3-0.6b-format-audit.json
```

For the 32-row overfit test, use `--run-purpose overfit32 --max-steps 100`. For the resume test,
use `--run-purpose resume_smoke --max-steps 4 --stop-after-step 2`, then invoke the identical run
again with `--resume-from RUN_DIR/checkpoint-2` and without `--stop-after-step`. The resolved
configuration prevents either smoke from being confused with a pilot. Repeat both procedures for
`qwen3_0_6b` and `qwen35_0_8b`, then run direct adapter inference and the raw dev scorer.

## 6. Managed pilot and monitoring

Create a unique empty run directory and launch one pilot per tmux session. A pilot command uses
`--run-purpose pilot` and does not set `--max-steps`. Redirect stdout/stderr to `RUN_DIR/console.log`.
Launch a separate read-only monitor session at a three-minute interval:

```bash
bash scripts/training/run_with_training_env.sh scripts/training/monitor_cleanup_run.py \
  --run-dir RUN_DIR \
  --session TMUX_TRAINING_SESSION \
  --interval-seconds 180 \
  --follow
```

Every snapshot records tmux/process identity, new log bytes, latest metrics, checkpoint state,
GPU utilization/memory/temperature/power, and disk space. It never restarts, resubmits, kills, or
changes a job. If a run fails or stalls, preserve the evidence and request explicit authorization
before any recovery action.

## 7. Raw-output evaluation

Run `infer_cleanup_adapter.py` on authoring dev and both retired diagnostic corpora. It refuses
blind-named paths, uses the Android 16–96 input-derived output bound, and puts raw model output in
the scorer's selected field. Guardrail behavior is recorded separately and cannot turn a failed
raw model into a candidate. Use `score_cleanup_training_dev.py`, the committed retired-diagnostic
scorer, and the human semantic-review queue/summary tools. Keep raw result JSONL outside Git;
commit only sanitized aggregate reports after inspection.
