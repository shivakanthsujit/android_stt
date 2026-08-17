#!/usr/bin/env python3
"""Validate completed raw-output human reviews and emit a text-free summary."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from train_cleanup_adapter import read_jsonl, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite {args.output}")
    if "blind" in str(args.reviews).casefold():
        raise RuntimeError("authoring-side semantic review summary refuses blind inputs")
    rows = read_jsonl(args.reviews)
    seen: set[str] = set()
    failures: Counter[str] = Counter()
    unsafe_ids: list[str] = []
    reviewers: set[str] = set()
    for row in rows:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise RuntimeError("review queue has a missing or duplicate case_id")
        seen.add(case_id)
        for field in ("raw_semantic_safe", "protected_meaning_preserved", "correction_semantically_correct"):
            if row.get(field) is not True and row.get(field) is not False:
                raise RuntimeError(f"{case_id}: {field} must be completed as true or false")
            if row[field] is False:
                failures[field] += 1
        reviewer = row.get("reviewer_ref")
        reviewed_at = row.get("reviewed_at")
        if not isinstance(reviewer, str) or not reviewer:
            raise RuntimeError(f"{case_id}: reviewer_ref is required")
        if not isinstance(reviewed_at, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_at):
            raise RuntimeError(f"{case_id}: reviewed_at must be YYYY-MM-DD")
        reviewers.add(reviewer)
        if not all(row[field] is True for field in ("raw_semantic_safe", "protected_meaning_preserved", "correction_semantically_correct")):
            unsafe_ids.append(case_id)
            if not isinstance(row.get("notes"), str) or not row["notes"].strip():
                raise RuntimeError(f"{case_id}: a failed review requires notes")
    report = {
        "schema_version": "cleanup-raw-semantic-review-summary-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if not unsafe_ids else "fail",
        "review_sha256": sha256_file(args.reviews),
        "records": len(rows), "reviewer_count": len(reviewers),
        "failure_counts": dict(sorted(failures.items())),
        "unsafe_case_ids": unsafe_ids,
        "contains_example_text": False,
        "guardrail_fallback_can_change_status": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "records": len(rows), "unsafe": len(unsafe_ids)}, sort_keys=True))
    return 0 if not unsafe_ids else 1


if __name__ == "__main__":
    raise SystemExit(main())
