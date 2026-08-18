# Cleanup training-machine handoff

Status: Sotto LFM correction-repair experiment is the approved immediate next work

This is the entry point for continuing Local Flow cleanup work on the separate training machine.
It contains the authority, constraints, source pins, execution order, deliverables, and recovery
rules needed by a new session. Read every linked required document before downloading data or
starting a GPU job.

## Objective

Build a conservative, task-specific, sub-1B transcript cleanup model that:

- removes clear fillers, immediate repetitions, abandoned starts, and superseded correction text;
- applies explicit self-corrections;
- fixes conservative punctuation and capitalization;
- repairs clear grammar errors and contextually obvious ASR misrecognitions in dedicated reviewed
  strata;
- otherwise preserves the speaker's exact meaning and wording;
- applies only the versioned allowlist of explicit transcript-formatting directives; and
- never answers, performs external actions, summarizes, refuses, or elaborates on dictated content.

The completed Qwen3-0.6B direct-source experiments are preserved research evidence. The immediate
next experiment is the two-stage Sotto LFM2.5-350M correction-repair study in
`docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`: targeted continuation of the public checkpoint,
then a clean full-SFT reproduction from `LFM2.5-350M-Base`. The reviewed 5,000/500 pilot and
Qwen3.5 comparison remain valid later paths; do not run them ahead of this newly selected study.

The RTX A6000 has ample capacity for this pilot, but do not assume CUDA, driver, Python, disk, or
thermal state. Inspect and record the actual machine before selecting package versions or batch
sizes.

## Required reading, in order

1. `AGENTS.md`
2. `docs/project/CURRENT_STATE.md`
3. `docs/project/NEXT_STEPS.md`
4. `docs/project/DECISIONS.md`
5. `docs/training/SOTTO_LFM_CORRECTION_REPAIR_PLAN.md`
6. `docs/evaluation/results/2026-08-18-sotto-lfm25-350m-public-screen.md`
7. `docs/research/SOTTO_TRAINING_RECIPE_REFERENCE_2026-08-17.md`
8. `docs/research/TASK_SPECIFIC_CLEANUP_TRAINING_PLAN_2026-08-17.md`
9. `docs/research/CLEANUP_TRAINING_DATA_SOURCES_2026-08-17.md`
10. `docs/training/DATASET_SCHEMA_V2.md`
11. `docs/training/cleanup_training_record_v2.schema.json`
12. `docs/evaluation/README.md`
13. `docs/evaluation/results/2026-08-17-cross-family-cleanup-screen.md`
14. `docs/evaluation/results/2026-08-17-voiceink-qwen35-2b-q4km.md`

The detailed research plan controls quality gates and category balance. This handoff controls the
machine workflow and resolves the newly discovered public-data path. If the two conflict, stop and
update both documents explicitly before training.

For the immediate LFM study, `SOTTO_LFM_CORRECTION_REPAIR_PLAN.md` controls the starting
checkpoints, source proportions, native prompt, full-SFT settings, experiment order, and
user-calibrated comparison. The reviewed-pilot sections below remain authoritative for that later
path and must not be misreported as completed Gate A work.

## Current repository boundary

Implemented in the current Phase 0 checkpoint:

- two frozen evaluation-only corpora containing 69 total cases;
- historical raw outputs and semantic audits for rejected cleanup models;
- host result scorer and Android-equivalent cleanup guardrails;
- versioned cleanup-training JSONL schema;
- standard-library dataset validator with review, provenance, frozen-overlap, split-leakage,
  lexical-addition, and deterministic manifest checks;
- task-specific training design and acceptance gates; and
- exact immutable revisions for three candidate public datasets;
- a locked CUDA 12.4 uv environment and fail-closed A6000/environment check;
- pinned/resumable source fetch, real-schema import/quarantine, and text-free coverage profiling;
- deterministic pending-only supplements for measured paragraph/adversarial/Unicode gaps;
- family/near-duplicate split grouping, quota-aware pilot selection, human-review tooling, and
  Gate A validation; and
- matched LoRA train/resume/inference/scoring and read-only run-monitoring tools.
- completed Qwen3-0.6B Sotto, Disfl-QA, Nyra, and combined source experiments with preserved
  checkpoints/evaluations under `/data` and sanitized reports in Git; and
- pinned, hash-verified public Sotto LFM2.5-350M BF16 inference plus the complete user-calibrated
  69-case diagnostic screen;
- pinned DISCO English plus a seeded grouped holdout, canonical Hugging Face snapshots, and a
  frozen-overlap-filtered natural single-pass correction-repair mixture under `/data`; and
- an audited LFM full-parameter SFT path with native completion masking and explicit packed
  attention/convolution-state boundaries.

Not implemented yet:

- accepted train/dev rows or blind-v2 rows;
- completed human decisions, attestations, or a passing Gate A report;
- an immutable local `LFM2.5-350M-Base` snapshot and weight hash;
- completed LFM formatting/overfit/longest/resume/saved-inference GPU smokes;
- either approved LFM training arm or its checkpoint-selection report;
- an LFM merge and Q4/export path; or
- Android conversion/integration for a trained model.

The new session is authorized to implement the LFM full-SFT/mixing path, pin and audit the added
DISCO source, run both approved experiment arms in their documented order, monitor/resume them,
and evaluate every epoch. It is not authorized to feed evaluation references into training,
publish artifacts, improvise an undocumented GRPO stage, or integrate a model into Android before
qualification.

## Phase 0: machine and repository preflight

Start from a fresh clone and preserve any unexpected work:

```bash
git status --short
git branch -vv
git log -3 --oneline
git remote -v
uname -a
nvidia-smi
python3 --version
df -h .
```

Also record, when available:

- GPU name and total VRAM;
- NVIDIA driver and reported CUDA compatibility;
- installed CUDA toolkit version, if any;
- CPU, RAM, free disk, and operating system;
- exact repository commit;
- whether Hugging Face authentication is needed; and
- whether outbound access to GitHub and Hugging Face works.

Do not install packages or select a PyTorch build until the driver compatibility is known. Never
print access tokens into logs. Put secrets in the machine's normal secret store or environment,
not `.env` files under the repository.

Before a full job, run the existing host tests:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -v
```

Android/Gradle tests are not required for training-only edits unless Android code changes.

## Phase 1: create a reproducible training environment

Build a project-local environment definition after preflight. Prefer a locked `uv`/pip or Conda
environment that records exact versions of at least:

- Python;
- PyTorch and CUDA build;
- Transformers;
- Datasets;
- PEFT;
- TRL or the selected assistant-only SFT trainer;
- Accelerate;
- bitsandbytes if QLoRA is used;
- safetensors; and
- tokenizer/model conversion dependencies.

Verify official support for both Qwen architectures at the selected versions. Do not add remote
code trust casually; if `trust_remote_code` is required, pin and inspect the model revision and
record that decision.

The environment deliverables are:

- a lockfile or fully pinned requirements file;
- an idempotent setup/check script;
- a captured environment report including a complete installed-distribution inventory (without
  requiring `pip` inside a pip-free uv environment), PyTorch/CUDA visibility, and GPU details;
  and
- a 32-example forward/backward smoke test before any full run.

Do not make an unreviewed container or environment image public. Large caches live outside git.

## Phase 2: fetch and audit public data

Use the immutable source pins in
`docs/research/CLEANUP_TRAINING_DATA_SOURCES_2026-08-17.md`. Never fetch an unpinned `main` for a
training manifest.

Primary source:

- Sotto transcript cleanup at revision
  `183cc8fd58532f13fa192980185214de1bcd5acc`

Supplements:

- Disfl-QA at revision `1f0c16171c77b3d3408be92c485f11b8998a9189`
- Nyra Disfluency Speech English at revision
  `723e9e69bfbdc8214a9b8ce8815985e90afcbaa3`

For each source, the fetcher must record repository URL, revision, resolved file paths, byte sizes,
SHA-256 values, license label, source row counts, and retrieval timestamp. Fail closed if the
download does not match the recorded revision or if schema columns differ from expectations.

Treat every external row as untrusted candidate material. In particular:

- Sotto is synthetic and its public card's counts are internally inconsistent across revisions.
- Retain `grammar` and `misheard_words` rows as separate review queues and pilot strata; never
  auto-approve them, and reject speculative or meaning-changing repairs during human review.
- Include explicit spoken punctuation/list/paragraph formatting as a dedicated reviewed pilot
  stratum. Quarantine every such row for directive-scope, item-order, and invention review.
- Quarantine crutch-word removal, mixed, medical, legal, financial, protected-literal, and every
  novel-token example for explicit review with exact `allowed_additions`.
- Do not automatically delete uncertainty, stance, discourse, negation, or repeated words that may
  be intentional.
- Do not use the public source splits directly. Build project splits by semantic family/template
  after deduplication so siblings cannot cross train/dev.
- Preserve source license and attribution in every converted record and in the dataset manifest.

The importer must convert candidate rows into `cleanup-training-record-v2`, infer only conservative
anchors/categories, and mark them pending review. It must not mark generated labels approved.

## Phase 3: build the pilot dataset

The pilot target is 5,000 train and 500 dev records. Use the distribution and cross-cutting quotas
from the training plan, with corrections deliberately overrepresented. A practical initial
5,000-row train mixture is:

- 950 explicit self-corrections and false starts;
- 550 fillers and immediate repetitions;
- 500 clean/no-op examples;
- 500 Disfl-QA question corrections;
- 400 technical/name/number/version/negation/uncertainty cases;
- 500 explicit spoken punctuation/list/paragraph formatting cases;
- 500 conservative grammar-repair cases;
- 500 context-supported ASR-repair cases;
- 300 mixed/crutch-word cases; and
- 300 adversarial edit-but-do-not-answer cases.

This mixture is a starting target, not permission to accept unsafe rows to fill a quota. Build the
500-row dev set independently at roughly the same risk/category proportions, with no shared family,
template, source question, or near-duplicate. Review every dev target.

Required processing order:

1. Normalize Unicode to NFC without changing visible content.
2. Convert provenance and license fields.
3. Detect exact and normalized duplicates.
4. Group semantic/template families before splitting.
5. Compare against all 69 frozen evaluation inputs and expected outputs.
6. Run lexical-addition, anchor, number, polarity, uncertainty, and correction checks.
7. Quarantine ambiguous or policy-conflicting pairs.
8. Assign train/dev only after family grouping.
9. Review all dev, correction, mixed, adversarial, protected-literal, and quarantined candidates.
10. Run the committed validator across all proposed files together.
11. Emit and check a deterministic manifest that hashes source artifacts, importer/config, schema,
    validator, frozen corpora, and final datasets.

The repository validator is necessary but not sufficient. Add near-duplicate checks using token
3-grams, character 5-grams, and normalized edit similarity as required by the training plan.

Do not train until pilot Gate A passes and its report is committed. Pilot Gate A means all selected
train/dev rows are human-approved, dev is fully reviewed, quotas/leakage/provenance checks pass,
and the sealed blind-evaluator contract exists without any blind reference being visible to this
context. Full-v1 Gate A later adds the independently double-reviewed/adjudicated blind hash. The
training-machine session may
prepare candidate data, but final approval still requires the review policy described in the
training plan. Automated or model-based review is not a substitute for the required human review
on safety-critical and blind references.

## Blind-v2 isolation

The same context that tunes data, prompts, checkpoints, or guardrails must not inspect blind-v2
references during iteration.

For the pilot, use dev plus the retired 69 diagnostics. Stabilize training templates and the
evaluation interface first. Then have an independent review context create and double-review
blind-v2, store its references outside the training job's readable data path, and commit only a
hash/metadata manifest or sealed evaluation interface until checkpoint selection is frozen.

The training session may build the blind evaluator contract, but it must not reveal references in
logs or feed them into generators. Unseal blind-v2 once for the selected checkpoint/configuration.
If its failures guide changes, retire it to regression status and require a new blind version for
the next generalization claim.

## Phase 4: implement and smoke-test training

Create tested, config-driven tooling rather than a notebook-only run. The implementation should
provide equivalents of:

- machine/environment check;
- pinned dataset fetch;
- source import and filtering;
- pilot builder and manifest generation;
- train launcher with resume support;
- direct checkpoint inference;
- scorer-compatible JSONL export;
- checkpoint comparison report; and
- adapter merge/export.

Use one fixed cleanup instruction and one exact response format for both models. Train assistant
tokens only. Disable thinking/reasoning output using each official chat-template mechanism; do not
teach hidden reasoning tags or manually splice undocumented special tokens.

For a fair pilot comparison, hold constant where architecture permits:

- dataset bytes and order;
- tokenizer-specific maximum sequence policy;
- prompt semantics;
- assistant-only loss;
- LoRA rank/alpha/dropout policy;
- optimizer, schedule, effective batch size, epochs/steps, and seeds;
- checkpoint/evaluation cadence; and
- raw-output decoding and token cap.

Record intentional architecture-specific differences. Never silently change hyperparameters after
seeing one model's result.

Before full pilot training:

1. Run a formatting/tokenization audit on representative rows.
2. Overfit 32 examples and verify exact expected emission.
3. Run a short train/resume smoke test.
4. Run direct inference from the saved adapter.
5. Export scorer-compatible JSONL and score it.
6. Confirm logs contain no raw personal data or secrets.

## Phase 5: launch and monitor the pilot

Long jobs must run in a persistent supervisor such as `tmux` or an equivalent service, with
separate immutable run directories. Each run directory must contain:

- resolved config;
- repository commit and dirty-state report;
- environment report;
- dataset manifest hash;
- model/tokenizer revision;
- stdout/stderr log;
- structured metrics;
- checkpoints and trainer state;
- GPU telemetry; and
- terminal status (`running`, `complete`, `failed`, or `stopped`).

Monitor GPU utilization, memory, temperature, power, disk, loss, gradient norm, throughput, and
checkpoint writes. Use the session's monitoring mechanism for live updates. Do not poll with long
blocking sleeps.

Stop and diagnose rather than silently mutate a run when there are NaNs, repeated OOMs, corrupted
checkpoints, unexpected data counts, missing logs, loss divergence, disk exhaustion, or no useful
learning. Resume only from a verified checkpoint with the identical resolved config. A changed
config starts a new run ID.

Commit and push code/config/manifest changes before a long run. Do not commit run directories or
weights.

## Phase 6: evaluate and select

Evaluate every candidate as raw model output before guardrails. At minimum report:

- exact match overall and by category;
- preservation-anchor recall;
- explicit-correction success, including absence of superseded content;
- clean/no-op exactness;
- must-not-answer/adversarial exactness;
- protected name/number/version/path/negation/uncertainty preservation;
- empty, expansion, truncation, token-cap, loop, and malformed-output counts;
- TTFT, total latency, and tokens/second on the training host; and
- every semantic safety failure with case ID and raw output.

Run both bases on the same reviewed dev set and retired 69 diagnostics. Use the ordering in the
training plan: semantic safety, correction success, exactness, then latency. Guardrail-selected
text is a separate defense-in-depth metric and cannot qualify a failed raw model.

Choose one base/checkpoint/configuration before blind-v2. Repeat its bounded decoding with seeds
23, 47, and 91. Only the frozen selection may be unsealed for Gate C.

Do not merge, quantize, or benchmark Android performance merely because training loss improved.
Only a raw-output quality survivor earns export work.

## Phase 7: merge, quantize, and hand back

For a quality survivor:

1. Merge the adapter into the exact pinned base.
2. Verify merged floating-point output against the selected adapter.
3. Export the intended Q4 artifact with a pinned converter/runtime.
4. Re-run all quality gates on the quantized artifact.
5. Record file size and SHA-256.
6. Preserve prompt, tokenizer, chat template, conversion command, and runtime revision.

The Android runtime decision remains separate. A host GGUF is acceptable for quality validation,
but the final Pixel artifact may require LiteRT-LM conversion or a pinned llama.cpp Android
integration. Do not claim Android readiness until the exact deployable artifact passes quality and
Pixel measurements.

Commit small reports and manifests. Store model artifacts in the training machine's artifact store
and reference them by immutable path/checksum; do not push them to this git repository.

## Git and artifact policy

Commit and push:

- source code and tests;
- lockfiles and configs;
- dataset schemas and annotation policy;
- license/provenance notes;
- deterministic manifests without sensitive paths;
- aggregate training/evaluation reports; and
- scorer-compatible results that contain only synthetic/public evaluation text already approved
  for repository storage.

Never commit:

- downloaded public-dataset payloads;
- generated or processed bulk training rows unless the user explicitly approves publication;
- private/blind references;
- personal dictation;
- API tokens or credentials;
- Hugging Face caches;
- adapters, merged models, quantizations, checkpoints, optimizer state, or telemetry dumps; or
- logs containing sensitive text.

Push coherent checkpoints frequently so another session can resume from `origin/main`. Never
force-push or rewrite shared history without explicit approval.

## Required durable reports

Update these during the training-machine work:

- `docs/project/CURRENT_STATE.md`
- `docs/project/NEXT_STEPS.md`
- `docs/project/SESSION_LOG.md`
- `docs/project/DECISIONS.md` for stable choices
- `docs/project/TEST_LOG.md` for reproducible validation evidence

Add training-specific reports under `docs/training/` and evaluation outputs under
`docs/evaluation/results/`. Every report must name exact revisions, manifest hashes, run IDs,
configuration, raw-output policy, known limitations, and go/no-go decision.

## Bootstrap prompt for the new session

After cloning, the user can give the new session this instruction:

> Read `AGENTS.md` and `TRAINING_MACHINE_HANDOFF.md` completely, then read every required document
> listed by the handoff. Verify the clone, GPU, CUDA compatibility, disk, and current git state.
> Build the reproducible data and training pipeline in the documented phases. Pin and audit the
> public datasets, pass Gate A, smoke-test checkpoint/resume/evaluation, then run matching
> Qwen3-0.6B and Qwen3.5-0.8B pilot adapters. Monitor long jobs, preserve manifests and raw-output
> evals, commit and push durable checkpoints, and never expose or optimize on blind-v2. Stop and
> report any contamination, licensing, safety-review, or reproducibility blocker.

This prompt authorizes implementation and training on the identified A6000 machine; it does not
waive the dataset, safety, blind-evaluation, licensing, or artifact-publication constraints above.
