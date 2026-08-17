#!/usr/bin/env python3
"""Export one run's publisher validation pairs outside Git for raw adapter evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from train_cleanup_adapter import sha256_file  # noqa: E402
from train_direct_source_adapter import (  # noqa: E402
    frozen_surfaces,
    load_source_split,
    manifest_files,
    verify_source_identity,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--experiment", choices=("sotto", "disfl_qa", "nyra", "combined"),
        help="publisher validation split to export; defaults to the run's training experiment",
    )
    return parser.parse_args()


def select_experiment(
    resolved: dict, training_config: dict, requested_experiment: str | None,
) -> tuple[str, dict]:
    experiment_key = requested_experiment or resolved["experiment_key"]
    experiments = training_config.get("experiments", {})
    if experiment_key not in experiments:
        raise RuntimeError(f"unknown direct-source experiment: {experiment_key}")
    return experiment_key, experiments[experiment_key]


def main() -> int:
    args = parse_args()
    output = args.output.resolve()
    if output.exists():
        raise RuntimeError(f"refusing to overwrite {output}")
    if output == REPO_ROOT or REPO_ROOT in output.parents:
        raise RuntimeError("publisher validation text must remain outside the Git repository")
    provenance_path = output.with_suffix(output.suffix + ".provenance.json")
    if provenance_path.exists():
        raise RuntimeError(f"refusing to overwrite {provenance_path}")

    resolved_path = args.run_dir / "resolved-config.json"
    if not resolved_path.is_file():
        raise RuntimeError("run directory is missing resolved-config.json")
    resolved = json.loads(resolved_path.read_text(encoding="utf-8"))
    if resolved.get("run_controls", {}).get("purpose") != "full":
        raise RuntimeError("publisher validation export requires a full direct-source run")

    source_manifest_path = Path(resolved["artifact_inputs"]["source_manifest"])
    source_root = Path(resolved["artifact_inputs"]["source_root"])
    if sha256_file(source_manifest_path) != resolved["input_hashes"]["source_manifest_sha256"]:
        raise RuntimeError("source manifest bytes differ from the training run")
    source_config_path = REPO_ROOT / resolved["source_config_path"]
    if sha256_file(source_config_path) != resolved["input_hashes"]["source_config_sha256"]:
        raise RuntimeError("source config bytes differ from the training run")
    training_config_path = REPO_ROOT / "training/config/direct-source-training-v1.json"
    if sha256_file(training_config_path) != resolved["input_hashes"]["training_config_sha256"]:
        raise RuntimeError("direct-source training config bytes differ from the training run")
    manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    source_config = json.loads(source_config_path.read_text(encoding="utf-8"))
    training_config = json.loads(training_config_path.read_text(encoding="utf-8"))
    verify_source_identity(manifest, source_config, source_config_path)
    indexed = manifest_files(manifest)
    forbidden = frozen_surfaces(REPO_ROOT / path for path in resolved["frozen_evaluation_paths"])
    experiment_key, experiment = select_experiment(resolved, training_config, args.experiment)

    validation_rows: list[dict[str, str]] = []
    source_reports = []
    for spec in experiment["sources"]:
        rows, report = load_source_split(source_root, spec, "validation", indexed, forbidden)
        validation_rows.extend(rows)
        source_reports.append(report)
    expected_count = experiment["validation_records"]
    if len(validation_rows) != expected_count:
        raise RuntimeError(f"validation row count {len(validation_rows)} != {expected_count}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as handle:
        for row in validation_rows:
            handle.write(json.dumps({
                "id": row["id"],
                "raw": row["raw"],
                "expected": row["expected"],
                "categories": ["publisher_validation"],
                "must_preserve": [],
                "must_remove": [],
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
    provenance = {
        "schema_version": "direct-source-publisher-validation-v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contains_example_text": False,
        "run_dir": str(args.run_dir.resolve()),
        "trained_experiment": resolved["experiment_key"],
        "evaluated_experiment": experiment_key,
        "resolved_config_sha256": sha256_file(resolved_path),
        "source_manifest_sha256": sha256_file(source_manifest_path),
        "records": len(validation_rows),
        "sources": source_reports,
        "output_sha256": sha256_file(output),
    }
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "evaluated_experiment": experiment_key,
        "records": len(validation_rows),
        "output": str(output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
