#!/usr/bin/env python3
"""Prepare a local human-review queue for raw dev outputs; never approves rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from train_cleanup_adapter import read_jsonl, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    if manifest_path.exists():
        raise RuntimeError(f"refusing to overwrite {manifest_path}")
    if "blind" in str(args.cases).casefold() or "blind" in str(args.results).casefold():
        raise RuntimeError("authoring-side semantic review preparation refuses blind inputs")
    cases = {row["id"]: row for row in read_jsonl(args.cases)}
    results = read_jsonl(args.results)
    if len(cases) != len(results):
        raise RuntimeError("case/result count differs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        for result in results:
            case_id = result.get("case_id")
            if case_id not in cases:
                raise RuntimeError(f"unknown result case_id: {case_id!r}")
            case = cases[case_id]
            if result.get("raw") != case.get("raw") or result.get("expected") != case.get("expected"):
                raise RuntimeError(f"{case_id}: result text differs from cases")
            record = {
                "case_id": case_id,
                "raw": case["raw"], "expected": case["expected"],
                "model_text": result["model_text"],
                "categories": case.get("categories", []),
                "risk_tags": case.get("risk_tags", []),
                "must_preserve": case.get("must_preserve", []),
                "must_remove": case.get("must_remove", []),
                "automated_exact_match": result["model_text"].strip() == case["expected"].strip(),
                "guardrail_would_fallback": result.get("guardrail_would_fallback"),
                "raw_semantic_safe": None,
                "protected_meaning_preserved": None,
                "correction_semantically_correct": None,
                "reviewer_ref": None,
                "reviewed_at": None,
                "notes": "",
            }
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
    metadata = {
        "schema_version": "cleanup-raw-semantic-review-queue-v1",
        "cases_sha256": sha256_file(args.cases), "results_sha256": sha256_file(args.results),
        "queue_sha256": sha256_file(args.output), "records": len(results),
        "instruction": "A human must fill all null review fields. Do not use model or automated approval.",
    }
    manifest_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"records": len(results), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
