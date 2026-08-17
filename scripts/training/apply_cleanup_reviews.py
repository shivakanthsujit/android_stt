#!/usr/bin/env python3
"""Apply explicit human review decisions without auto-approving any dataset row."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from cleanup_data_common import require_empty_output_dir, write_jsonl


ALLOWED_DECISIONS = frozenset({"approved", "rejected"})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def validate_decision(value: dict[str, Any], location: str) -> None:
    required = {"id", "decision", "reviewer_ref", "reviewed_at"}
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - {"reason"})
    if missing or unknown:
        raise RuntimeError(f"{location}: missing={missing}, unknown={unknown}")
    for field in ("id", "reviewer_ref", "reviewed_at"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise RuntimeError(f"{location}: {field} must be a non-empty string")
    if value["decision"] not in ALLOWED_DECISIONS:
        raise RuntimeError(f"{location}: decision must be one of {sorted(ALLOWED_DECISIONS)}")
    if not __import__("re").fullmatch(r"\d{4}-\d{2}-\d{2}", value["reviewed_at"]):
        raise RuntimeError(f"{location}: reviewed_at must be YYYY-MM-DD")
    if "reason" in value and (not isinstance(value["reason"], str) or not value["reason"].strip()):
        raise RuntimeError(f"{location}: reason must be a non-empty string when present")


def apply_reviews(
    records: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise RuntimeError("input record has no valid id")
        if record_id in by_id:
            raise RuntimeError(f"duplicate input record id: {record_id}")
        if record.get("split") == "blind":
            raise RuntimeError("blind records are forbidden in the training-context review tool")
        by_id[record_id] = record

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reviewer_pairs: set[tuple[str, str]] = set()
    for index, decision in enumerate(decisions, 1):
        validate_decision(decision, f"decision {index}")
        record_id = decision["id"]
        if record_id not in by_id:
            raise RuntimeError(f"review decision references unknown id: {record_id}")
        pair = (record_id, decision["reviewer_ref"])
        if pair in reviewer_pairs:
            raise RuntimeError(f"reviewer {pair[1]!r} submitted multiple decisions for {pair[0]!r}")
        reviewer_pairs.add(pair)
        grouped[record_id].append(decision)

    outputs: dict[str, list[dict[str, Any]]] = {
        "approved": [], "pending": [], "rejected": []
    }
    for record_id, original in sorted(by_id.items()):
        row = dict(original)
        record_decisions = grouped.get(record_id, [])
        if not record_decisions:
            row["review"] = {"status": "pending", "reviewers": 0}
            outputs["pending"].append(row)
            continue
        distinct = {decision["decision"] for decision in record_decisions}
        reviewer_refs = sorted(decision["reviewer_ref"] for decision in record_decisions)
        dates = sorted(decision["reviewed_at"] for decision in record_decisions)
        if len(distinct) > 1:
            row["review"] = {
                "status": "pending", "reviewers": len(reviewer_refs),
                "reviewer_refs": reviewer_refs, "reviewed_at": dates[-1],
            }
            row["notes"] = (row.get("notes", "") + "; review_conflict_requires_adjudication").strip("; ")
            outputs["pending"].append(row)
            continue
        status = distinct.pop()
        row["review"] = {
            "status": status, "reviewers": len(reviewer_refs),
            "reviewer_refs": reviewer_refs, "reviewed_at": dates[-1],
        }
        reasons = sorted({decision.get("reason", "") for decision in record_decisions if decision.get("reason")})
        if reasons:
            row["notes"] = (row.get("notes", "") + "; human_review=" + " | ".join(reasons)).strip("; ")
        outputs[status].append(row)
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, action="append", required=True)
    parser.add_argument("--decisions", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    require_empty_output_dir(args.output_root)
    records = [row for path in args.records for row in read_jsonl(path)]
    decisions = [row for path in args.decisions for row in read_jsonl(path)]
    outputs = apply_reviews(records, decisions)
    for status, rows in outputs.items():
        write_jsonl(args.output_root / f"{status}.jsonl", rows)
    summary = {status: len(rows) for status, rows in outputs.items()}
    (args.output_root / "review-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
