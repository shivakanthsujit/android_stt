#!/usr/bin/env python3
"""Stream verified source candidates and print text-free transformation coverage."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path

from build_cleanup_pilot import bucket, cross_cutting_flags
from cleanup_data_common import atomic_json, sha256_file
from import_cleanup_sources import data_rows, make_record, path_matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--source-config", type=Path, default=Path("training/config/sources-v1.json"))
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--pilot-config", type=Path, default=Path("training/config/pilot-v1.json"))
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    config = json.loads(args.source_config.read_text(encoding="utf-8"))
    pilot = json.loads(args.pilot_config.read_text(encoding="utf-8"))
    if manifest.get("config_sha256") != sha256_file(args.source_config):
        raise RuntimeError("source manifest configuration hash differs from source configuration")
    configured = {source["id"]: source for source in config["sources"]}
    if {source["id"] for source in manifest["sources"]} != set(configured):
        raise RuntimeError("source manifest IDs differ from source configuration")

    source_rows: Counter[str] = Counter()
    mapped_rows: Counter[str] = Counter()
    outcome_counts: Counter[str] = Counter()
    reasons: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    risks: Counter[str] = Counter()
    primary_buckets: Counter[str] = Counter()
    cross_cutting_counts: Counter[str] = Counter()
    candidate_files: Counter[str] = Counter()
    held_out_files: Counter[str] = Counter()

    for source in manifest["sources"]:
        rule = configured[source["id"]]
        for item in source["files"]:
            relative = item["path"]
            path = args.source_root / source["id"] / relative
            if path.suffix.lower() not in {".parquet", ".json", ".jsonl"}:
                continue
            if path_matches(relative, rule["holdout_include"]):
                held_out_files[source["id"]] += 1
                continue
            if not path_matches(relative, rule["candidate_include"]):
                continue
            candidate_files[source["id"]] += 1
            for locator, row in data_rows(path, source["id"]):
                source_rows[source["id"]] += 1
                converted = make_record(source, relative, locator, row)
                if converted is None:
                    continue
                outcome, record, reason = converted
                mapped_rows[source["id"]] += 1
                outcome_counts[outcome] += 1
                reasons[f"{outcome}:{reason}"] += 1
                categories.update(record["categories"])
                risks.update(record["risk_tags"])
                primary_buckets[bucket(record) or "unbucketed"] += 1
                cross_cutting_counts.update(cross_cutting_flags(record))

    missing = [source_id for source_id in configured if not candidate_files[source_id] or not mapped_rows[source_id]]
    if missing:
        raise RuntimeError(f"candidate schema/path mismatch for: {', '.join(sorted(missing))}")
    primary_required = {
        name: target + round(target * pilot["dev_records"] / pilot["train_records"])
        for name, target in pilot["train_primary_buckets"].items()
    }
    primary_shortfalls = {
        name: required - primary_buckets[name]
        for name, required in primary_required.items()
        if primary_buckets[name] < required
    }
    total_required = pilot["train_records"] + pilot["dev_records"]
    cross_required = {
        name: math.ceil(total_required * fraction)
        for name, fraction in pilot["minimum_cross_cutting_fraction"].items()
    }
    cross_shortfalls = {
        name: required - cross_cutting_counts[name]
        for name, required in cross_required.items()
        if cross_cutting_counts[name] < required
    }
    report = {
        "report_version": "cleanup-source-profile-v1",
        "contains_example_text": False,
        "source_manifest_sha256": sha256_file(args.source_manifest),
        "source_config_sha256": sha256_file(args.source_config),
        "pilot_config_sha256": sha256_file(args.pilot_config),
        "importer_sha256": sha256_file(Path(__file__).with_name("import_cleanup_sources.py")),
        "profiler_sha256": sha256_file(Path(__file__)),
        "source_native_holdouts_consumed": False,
        "source_rows_visited": dict(sorted(source_rows.items())),
        "mapped_rows": dict(sorted(mapped_rows.items())),
        "unmapped_rows": {
            source_id: source_rows[source_id] - mapped_rows[source_id]
            for source_id in sorted(source_rows)
        },
        "candidate_data_files": dict(sorted(candidate_files.items())),
        "held_out_data_files": dict(sorted(held_out_files.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
        "reasons": dict(sorted(reasons.items())),
        "category_counts": dict(sorted(categories.items())),
        "risk_tag_counts": dict(sorted(risks.items())),
        "primary_bucket_counts": dict(sorted(primary_buckets.items())),
        "primary_required_train_plus_dev": primary_required,
        "primary_shortfalls": primary_shortfalls,
        "cross_cutting_counts": dict(sorted(cross_cutting_counts.items())),
        "cross_cutting_required_train_plus_dev": cross_required,
        "cross_cutting_shortfalls": cross_shortfalls,
    }
    if args.output:
        if args.output.exists():
            raise RuntimeError(f"refusing to overwrite source profile: {args.output}")
        atomic_json(args.output, report)
        print(json.dumps({
            "mapped_rows": sum(mapped_rows.values()),
            "outcome_counts": dict(sorted(outcome_counts.items())),
            "primary_shortfalls": primary_shortfalls,
            "cross_cutting_shortfalls": cross_shortfalls,
        }, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
