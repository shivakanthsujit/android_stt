#!/usr/bin/env python3
"""Emit a text-free coverage audit for candidate cleanup records before selection."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_cleanup_pilot import bucket, cross_cutting, read_jsonl
from cleanup_data_common import sha256_file


def source_id(row: dict[str, Any]) -> str:
    reference = row.get("source_ref")
    if isinstance(reference, str) and ":" in reference:
        return reference.split(":", 1)[0]
    return str(row.get("source", "unknown"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("training/config/pilot-v1.json"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")
    rows = [row for path in args.input for row in read_jsonl(path)]
    if any("blind" in str(path).casefold() for path in args.input) or any(
        str(row.get("split", "")).casefold().startswith("blind") for row in rows
    ):
        raise RuntimeError("candidate coverage audit refuses blind inputs")
    ids = [row.get("id") for row in rows]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise RuntimeError("candidate inputs contain a missing or duplicate ID")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    total_target = config["train_records"] + config["dev_records"]
    primary_required = {
        name: count + round(count * config["dev_records"] / config["train_records"])
        for name, count in config["train_primary_buckets"].items()
    }
    primary_available = Counter(bucket(row) for row in rows)
    cross_fraction = cross_cutting(rows) if rows else {name: 0.0 for name in config["minimum_cross_cutting_fraction"]}
    cross_available = {
        name: round(cross_fraction[name] * len(rows)) for name in config["minimum_cross_cutting_fraction"]
    }
    cross_required = {
        name: math.ceil(fraction * total_target)
        for name, fraction in config["minimum_cross_cutting_fraction"].items()
    }
    categories = Counter(category for row in rows for category in row.get("categories", []))
    risks = Counter(risk for row in rows for risk in row.get("risk_tags", []))
    review = Counter(str(row.get("review", {}).get("status", "missing")) for row in rows)
    sources = Counter(source_id(row) for row in rows)
    primary_shortfalls = {
        name: required - primary_available[name]
        for name, required in primary_required.items() if primary_available[name] < required
    }
    cross_global_shortfalls = {
        name: required - cross_available[name]
        for name, required in cross_required.items() if cross_available[name] < required
    }
    report = {
        "report_version": "cleanup-candidate-coverage-audit-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "candidate_pool_sufficient" if not primary_shortfalls and not cross_global_shortfalls else "supplement_required",
        "records": len(rows), "pilot_target_records": total_target,
        "input_files": [{"sha256": sha256_file(path), "bytes": path.stat().st_size} for path in args.input],
        "source_counts": dict(sorted(sources.items())),
        "review_status_counts": dict(sorted(review.items())),
        "primary_bucket": {
            name: {"available": primary_available[name], "required_train_plus_dev": required}
            for name, required in primary_required.items()
        },
        "primary_shortfalls": primary_shortfalls,
        "cross_cutting_global_pool": {
            name: {
                "available": cross_available[name], "available_fraction": cross_fraction[name],
                "minimum_selected_count": cross_required[name],
                "minimum_selected_fraction": config["minimum_cross_cutting_fraction"][name],
            }
            for name in config["minimum_cross_cutting_fraction"]
        },
        "cross_global_shortfalls": cross_global_shortfalls,
        "category_counts": dict(sorted(categories.items())),
        "risk_tag_counts": dict(sorted(risks.items())),
        "contains_example_text": False,
        "note": "Global pool sufficiency is necessary but not sufficient; the family split and selected-pilot quota audit remain authoritative.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "records": len(rows), "primary_shortfalls": primary_shortfalls, "cross_global_shortfalls": cross_global_shortfalls}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
