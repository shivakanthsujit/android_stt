#!/usr/bin/env python3
"""Run pilot Gate A and emit a path-sanitized, text-free report."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_cleanup_pilot import bucket, cross_cutting
from cleanup_data_common import near_duplicate_scores, normalized_text, sha256_file
from import_cleanup_sources import path_matches


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTESTATION_STATEMENTS = frozenset({
    "all_selected_rows_human_reviewed",
    "all_dev_rows_human_reviewed",
    "all_correction_mixed_adversarial_protected_rows_human_reviewed",
    "all_formatting_rows_human_reviewed",
    "all_grammar_asr_lexical_addition_high_stakes_rows_human_reviewed",
    "no_model_or_automated_approval_substituted_for_human_review",
    "no_blind_references_were_accessed",
})
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ENTITY = re.compile(
    r"(?:\b\d+(?:[.:/-]\d+)*\b|\b[A-Z][\w'-]+\b|\b[\w.+-]+@[\w.-]+\b|(?:^|\s)(?:[/~.]\S+))",
    re.UNICODE,
)
FROZEN_CASES = (
    REPO_ROOT / "docs/evaluation/cleanup_cases.jsonl",
    REPO_ROOT / "docs/evaluation/cleanup_cases_heldout_v1.jsonl",
)
DERIVED_SOURCES = frozenset({
    "template_human_reviewed", "deterministic_generated", "llm_proposed_human_approved"
})
DETERMINISTIC_SUPPLEMENT_ARTIFACTS = frozenset({
    REPO_ROOT / "scripts/training/generate_cleanup_supplement.py",
    REPO_ROOT / "training/config/supplement-v1.json",
})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise RuntimeError(f"{path}:{line_number}: expected an object")
                rows.append(value)
    return rows


def validate_attestation(
    value: dict[str, Any], policy_sha256: str, selected_reviewer_refs: set[str]
) -> None:
    if value.get("attestation_version") != "cleanup-pilot-review-attestation-v1":
        raise RuntimeError("unsupported review attestation version")
    if value.get("policy_sha256") != policy_sha256:
        raise RuntimeError("review attestation policy hash does not match the annotation policy")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value.get("review_completed_at", ""))):
        raise RuntimeError("review attestation needs review_completed_at=YYYY-MM-DD")
    reviewer_refs = value.get("reviewer_refs")
    if not isinstance(reviewer_refs, list) or not reviewer_refs or any(
        not isinstance(item, str) or not item for item in reviewer_refs
    ):
        raise RuntimeError("review attestation needs non-empty pseudonymous reviewer_refs")
    if len(reviewer_refs) != len(set(reviewer_refs)):
        raise RuntimeError("review attestation reviewer_refs must be unique")
    missing_reviewers = selected_reviewer_refs - set(reviewer_refs)
    if missing_reviewers:
        raise RuntimeError(f"attestation does not cover {len(missing_reviewers)} selected reviewer reference(s)")
    statements = value.get("statements")
    if not isinstance(statements, dict) or set(statements) != ATTESTATION_STATEMENTS:
        raise RuntimeError("review attestation statements do not match the v1 contract")
    if not all(statements.values()) or any(item is not True for item in statements.values()):
        raise RuntimeError("every review attestation statement must be exactly true")


def validate_license_attestation(
    value: dict[str, Any], source_manifest: dict[str, Any], source_config: dict[str, Any], manifest_sha256: str
) -> None:
    if value.get("attestation_version") != "cleanup-source-license-attestation-v1":
        raise RuntimeError("unsupported source license attestation version")
    if value.get("source_manifest_sha256") != manifest_sha256:
        raise RuntimeError("license attestation source-manifest hash differs")
    configured = {row["id"]: row for row in source_config["sources"]}
    manifested = {row["id"]: row for row in source_manifest["sources"]}
    audits = value.get("sources")
    if not isinstance(audits, list) or {row.get("id") for row in audits if isinstance(row, dict)} != set(configured):
        raise RuntimeError("license attestation must cover every configured source exactly once")
    for audit in audits:
        source_id = audit["id"]
        if audit.get("license") != configured[source_id]["license"]:
            raise RuntimeError(f"{source_id}: audited license label differs from configuration")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(audit.get("audited_at", ""))):
            raise RuntimeError(f"{source_id}: audited_at must be YYYY-MM-DD")
        if not isinstance(audit.get("auditor_ref"), str) or not audit["auditor_ref"]:
            raise RuntimeError(f"{source_id}: auditor_ref is required")
        evidence = audit.get("evidence_files")
        manifested_paths = {item["path"] for item in manifested[source_id]["files"]}
        if not isinstance(evidence, list) or not evidence or not set(evidence) <= manifested_paths:
            raise RuntimeError(f"{source_id}: evidence_files must name downloaded manifest paths")
        statements = audit.get("statements")
        required = {"terms_reviewed", "attribution_recorded", "research_training_permitted"}
        if not isinstance(statements, dict) or set(statements) != required or any(value is not True for value in statements.values()):
            raise RuntimeError(f"{source_id}: every license statement must be exactly true")


def audit_rows(
    train: list[dict[str, Any]], dev: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any]:
    if len(train) != config["train_records"] or len(dev) != config["dev_records"]:
        raise RuntimeError(
            f"pilot count mismatch: train={len(train)}, dev={len(dev)}, "
            f"expected={config['train_records']}/{config['dev_records']}"
        )
    all_rows = train + dev
    if any(row.get("split") == "blind" for row in all_rows):
        raise RuntimeError("blind records are forbidden in pilot Gate A inputs")
    if any(row.get("split") != split for split, rows in (("train", train), ("dev", dev)) for row in rows):
        raise RuntimeError("dataset file and row split disagree")
    unapproved = [row.get("id") for row in all_rows if row.get("review", {}).get("status") != "approved"]
    if unapproved:
        raise RuntimeError(f"pilot contains {len(unapproved)} unapproved row(s)")
    selected_reviewer_refs: set[str] = set()
    for row in all_rows:
        review = row["review"]
        refs = review.get("reviewer_refs")
        if not isinstance(refs, list) or not refs:
            raise RuntimeError(f"approved row {row.get('id')} has no reviewer_refs")
        selected_reviewer_refs.update(refs)
    train_buckets = Counter(bucket(row) for row in train)
    dev_buckets = Counter(bucket(row) for row in dev)
    if train_buckets.get(None):
        raise RuntimeError(f"train has {train_buckets[None]} row(s) outside primary buckets")
    if dev_buckets.get(None):
        raise RuntimeError(f"dev has {dev_buckets[None]} row(s) outside primary buckets")
    expected_train = config["train_primary_buckets"]
    expected_dev = {
        name: round(target * config["dev_records"] / config["train_records"])
        for name, target in expected_train.items()
    }
    for split, actual, expected in (("train", train_buckets, expected_train), ("dev", dev_buckets, expected_dev)):
        actual_dict = {name: actual[name] for name in expected}
        if actual_dict != expected:
            raise RuntimeError(f"{split} primary bucket counts differ: actual={actual_dict}, expected={expected}")
    cross = {"train": cross_cutting(train), "dev": cross_cutting(dev)}
    failures = []
    for split, values in cross.items():
        for name, minimum in config["minimum_cross_cutting_fraction"].items():
            if values[name] < minimum:
                failures.append(f"{split}:{name}={values[name]:.6f}<{minimum:.6f}")
    if failures:
        raise RuntimeError("cross-cutting quota failure: " + "; ".join(failures))
    return {
        "selected_reviewer_refs": selected_reviewer_refs,
        "primary_bucket_counts": {
            "train": {name: train_buckets[name] for name in expected_train},
            "dev": {name: dev_buckets[name] for name in expected_dev},
        },
        "cross_cutting_fraction": cross,
    }


def verify_source_manifest(source_manifest: dict[str, Any], source_config: dict[str, Any]) -> None:
    if source_manifest.get("manifest_version") != "cleanup-source-manifest-v1":
        raise RuntimeError("invalid source manifest version")
    configured = {item["id"]: item for item in source_config["sources"]}
    manifested = {item["id"]: item for item in source_manifest.get("sources", [])}
    if set(configured) != set(manifested):
        raise RuntimeError("source manifest IDs differ from source config")
    for source_id, expected in configured.items():
        actual = manifested[source_id]
        for field in ("url", "revision", "license"):
            if actual.get(field) != expected[field]:
                raise RuntimeError(f"source {source_id} {field} differs from pinned config")
        files = actual.get("files")
        if not isinstance(files, list) or not files:
            raise RuntimeError(f"source {source_id} has no payload hashes")
        for item in files:
            if not isinstance(item.get("bytes"), int) or item["bytes"] <= 0 or not HEX64.fullmatch(str(item.get("sha256", ""))):
                raise RuntimeError(f"source {source_id} has malformed file provenance")


def verify_source_payloads(source_manifest: dict[str, Any], source_root: Path) -> None:
    for source in source_manifest["sources"]:
        source_dir = (source_root / source["id"]).resolve()
        for item in source["files"]:
            path = (source_dir / item["path"]).resolve()
            if source_dir not in path.parents:
                raise RuntimeError(f"source manifest path escapes source directory: {source['id']}")
            if (
                not path.is_file()
                or path.stat().st_size != item["bytes"]
                or sha256_file(path) != item["sha256"]
            ):
                raise RuntimeError(f"source payload differs from manifest: {source['id']}/{item['path']}")


def validate_frozen_separation(
    selected: list[dict[str, Any]], thresholds: dict[str, float]
) -> dict[str, int]:
    frozen: list[tuple[str, str, str]] = []
    for path in FROZEN_CASES:
        for row in read_jsonl(path):
            for field in ("raw", "expected"):
                value = row.get(field)
                if isinstance(value, str) and value.strip():
                    frozen.append((
                        f"{path.name}:{row.get('id')}:{field}", value,
                        normalized_text(ENTITY.sub(" ENTITY ", value)),
                    ))
    flags: list[tuple[str, str, str]] = []
    comparisons = 0
    for row in selected:
        for selected_field in ("raw", "expected"):
            value = row[selected_field]
            masked = normalized_text(ENTITY.sub(" ENTITY ", value))
            for frozen_ref, frozen_value, frozen_masked in frozen:
                comparisons += 1
                token, chars, edit = near_duplicate_scores(value, frozen_value)
                masked_equal = masked == frozen_masked and len(masked.split()) >= 4
                if (
                    token >= thresholds["token_3gram_jaccard"]
                    or chars >= thresholds["character_5gram_jaccard"]
                    or edit >= thresholds["normalized_edit_similarity"]
                    or masked_equal
                ):
                    flags.append((row["id"], selected_field, frozen_ref))
                    if len(flags) >= 20:
                        rendered = "; ".join(f"{item[0]}:{item[1]}~{item[2]}" for item in flags)
                        raise RuntimeError("selected rows overlap frozen diagnostics; first flags: " + rendered)
    if flags:
        rendered = "; ".join(f"{item[0]}:{item[1]}~{item[2]}" for item in flags)
        raise RuntimeError("selected rows overlap frozen diagnostics: " + rendered)
    return {"comparisons": comparisons, "flags": 0}


def validate_source_native_holdouts(
    selected: list[dict[str, Any]], source_config: dict[str, Any]
) -> dict[str, Any]:
    configured = {source["id"]: source for source in source_config["sources"]}
    checked = 0
    for row in selected:
        if row.get("source") != "public_corpus":
            continue
        reference = row.get("source_ref", "")
        parts = reference.split(":", 2)
        if len(parts) != 3 or parts[0] not in configured:
            raise RuntimeError(f"{row.get('id')}: malformed public source_ref")
        source_id, relative, _ = parts
        rule = configured[source_id]
        if path_matches(relative, rule["holdout_include"]):
            raise RuntimeError(f"{row.get('id')}: source-native holdout entered the pilot")
        if not path_matches(relative, rule["candidate_include"]):
            raise RuntimeError(f"{row.get('id')}: public source path is outside candidate subset")
        checked += 1
    return {"public_rows_checked": checked, "source_native_holdout_rows": 0}


def validate_authoring_artifacts(
    selected: list[dict[str, Any]], artifacts: list[Path]
) -> list[Path]:
    derived = sorted({row.get("source") for row in selected if row.get("source") in DERIVED_SOURCES})
    if derived and not artifacts:
        raise RuntimeError(
            "derived supplemental rows require committed --authoring-artifact inputs; "
            f"selected sources={derived}"
        )
    checked = []
    for path in artifacts:
        resolved = path.resolve()
        if not resolved.is_file():
            raise RuntimeError(f"authoring artifact is not a file: {path}")
        if REPO_ROOT.resolve() not in resolved.parents:
            raise RuntimeError(f"authoring artifact must live in the repository: {path}")
        relative = resolved.relative_to(REPO_ROOT.resolve())
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", str(relative)],
            cwd=REPO_ROOT, text=True, capture_output=True,
        )
        clean = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", str(relative)], cwd=REPO_ROOT
        )
        if tracked.returncode != 0 or clean.returncode != 0:
            raise RuntimeError(f"authoring artifact must be tracked and committed: {relative}")
        checked.append(resolved)
    if len(checked) != len(set(checked)):
        raise RuntimeError("authoring artifacts must not be repeated")
    if "deterministic_generated" in derived:
        missing = {path.resolve() for path in DETERMINISTIC_SUPPLEMENT_ARTIFACTS} - set(checked)
        if missing:
            raise RuntimeError(
                "deterministic supplement requires its exact generator and configuration artifacts"
            )
    return checked


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--dev", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--review-attestation", type=Path, required=True)
    parser.add_argument("--license-attestation", type=Path, required=True)
    parser.add_argument("--local-manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--pilot-config", type=Path, default=REPO_ROOT / "training/config/pilot-v1.json")
    parser.add_argument("--training-config", type=Path, default=REPO_ROOT / "training/config/pilot-training-v1.json")
    parser.add_argument("--source-config", type=Path, default=REPO_ROOT / "training/config/sources-v1.json")
    parser.add_argument("--annotation-policy", type=Path, default=REPO_ROOT / "docs/training/ANNOTATION_POLICY_V2.md")
    parser.add_argument("--blind-contract", type=Path, default=REPO_ROOT / "training/config/blind-evaluator-contract-v1.json")
    parser.add_argument(
        "--authoring-artifact", type=Path, action="append", default=[],
        help="committed supplemental generator/lexicon/config input; repeat as needed",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for output in (args.local_manifest, args.report):
        if output.exists():
            raise RuntimeError(f"refusing to overwrite Gate A artifact: {output}")
    config = json.loads(args.pilot_config.read_text(encoding="utf-8"))
    training_config = json.loads(args.training_config.read_text(encoding="utf-8"))
    instruction_path = REPO_ROOT / training_config["instruction_path"]
    if not instruction_path.is_file():
        raise RuntimeError("training config instruction path does not exist")
    source_config = json.loads(args.source_config.read_text(encoding="utf-8"))
    source_manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    verify_source_manifest(source_manifest, source_config)
    verify_source_payloads(source_manifest, args.source_root)
    if source_manifest.get("config_sha256") != sha256_file(args.source_config):
        raise RuntimeError("source manifest config hash differs from source config")
    validate_license_attestation(
        json.loads(args.license_attestation.read_text(encoding="utf-8")),
        source_manifest, source_config, sha256_file(args.source_manifest),
    )
    train, dev = read_jsonl(args.train), read_jsonl(args.dev)
    authoring_artifacts = validate_authoring_artifacts(train + dev, args.authoring_artifact)
    audit = audit_rows(train, dev, config)
    source_subset_audit = validate_source_native_holdouts(train + dev, source_config)
    frozen_near_overlap = validate_frozen_separation(train + dev, config["near_duplicate"])
    attestation = json.loads(args.review_attestation.read_text(encoding="utf-8"))
    policy_hash = sha256_file(args.annotation_policy)
    validate_attestation(attestation, policy_hash, audit.pop("selected_reviewer_refs"))
    blind_contract = json.loads(args.blind_contract.read_text(encoding="utf-8"))
    if blind_contract.get("training_context_may_read_references") is not False:
        raise RuntimeError("blind evaluator contract must forbid training-context reference access")

    artifacts = [
        args.source_manifest, args.review_attestation, args.license_attestation, args.pilot_config,
        args.training_config, args.source_config,
        args.annotation_policy, args.blind_contract,
        instruction_path,
        Path(__file__).resolve(), REPO_ROOT / "scripts/training/build_cleanup_pilot.py",
        REPO_ROOT / "scripts/training/import_cleanup_sources.py",
        REPO_ROOT / "scripts/training/fetch_cleanup_sources.py",
        REPO_ROOT / "scripts/training/apply_cleanup_reviews.py",
        *authoring_artifacts,
    ]
    command = [
        sys.executable, str(REPO_ROOT / "scripts/validate-cleanup-training-data.py"),
        "--require-approved", "--write-manifest", str(args.local_manifest),
    ]
    for artifact in artifacts:
        command.extend(["--hash-artifact", str(artifact)])
    command.extend([str(args.train), str(args.dev)])
    result = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError("schema/frozen/leakage validation failed:\n" + result.stderr)
    local_manifest = json.loads(args.local_manifest.read_text(encoding="utf-8"))
    sanitized = {
        "report_version": "cleanup-pilot-gate-a-report-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate": "pilot_gate_a",
        "status": "pass",
        "blind_v2": {
            "references_accessed": False,
            "references_present_in_training_inputs": False,
            "evaluator_contract_sha256": sha256_file(args.blind_contract),
            "full_v1_double_reviewed_hash": "deferred_until_after_pilot_template_stabilization"
        },
        "counts": {"train": len(train), "dev": len(dev)},
        "dataset_files": [
            {"role": role, "sha256": sha256_file(path), "bytes": path.stat().st_size, "records": len(rows)}
            for role, path, rows in (("train", args.train, train), ("dev", args.dev, dev))
        ],
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "source_subset_audit": source_subset_audit,
        "license_attestation_sha256": sha256_file(args.license_attestation),
        "review_attestation_sha256": sha256_file(args.review_attestation),
        "reviewer_count": len(attestation["reviewer_refs"]),
        "annotation_policy_sha256": policy_hash,
        "training_config_sha256": sha256_file(args.training_config),
        "instruction_sha256": sha256_file(instruction_path),
        "authoring_artifact_hashes": [sha256_file(path) for path in authoring_artifacts],
        "schema_sha256": local_manifest["schema"]["sha256"],
        "record_schema_version": local_manifest["record_schema_version"],
        "validator_sha256": local_manifest["validator"]["sha256"],
        "frozen_evaluation": [
            {"sha256": item["sha256"], "bytes": item["bytes"]}
            for item in local_manifest["frozen_evaluation"]
        ],
        "frozen_near_overlap": frozen_near_overlap,
        **audit,
    }
    rendered = json.dumps(sanitized, indent=2, sort_keys=True) + "\n"
    if str(args.train.resolve()) in rendered or str(args.dev.resolve()) in rendered:
        raise RuntimeError("sanitized report unexpectedly contains a local dataset path")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(rendered, encoding="utf-8")
    print(f"Pilot Gate A passed for {len(train)} train and {len(dev)} dev records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
