#!/usr/bin/env python3
"""Interactive human review ledger writer for selected non-blind cleanup rows."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from train_cleanup_adapter import REPO_ROOT, read_jsonl


def existing_keys(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    keys: set[tuple[str, str]] = set()
    for row in read_jsonl(path):
        case_id, reviewer = row.get("id"), row.get("reviewer_ref")
        if not isinstance(case_id, str) or not isinstance(reviewer, str):
            raise RuntimeError("existing decision ledger has a malformed id or reviewer_ref")
        key = (case_id, reviewer)
        if key in keys:
            raise RuntimeError(f"existing decision ledger repeats {case_id!r} for {reviewer!r}")
        keys.add(key)
    return keys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, action="append", required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--reviewer-ref", required=True)
    return parser.parse_args()


def render(row: dict[str, Any], ordinal: int, total: int) -> None:
    print("\n" + "=" * 78)
    print(f"[{ordinal}/{total}] {row['id']} | split={row['split']} | source={row['source']}")
    print("source ref:", row.get("source_ref", "(human-authored; no source_ref)"))
    print("license:", row.get("license", "(missing)"))
    print("family/template:", row.get("family_id", "(missing)"), "/", row.get("template_id", "(missing)"))
    print("categories:", ", ".join(row.get("categories", [])))
    print("risks:", ", ".join(row.get("risk_tags", [])) or "(none)")
    print("must preserve:", json.dumps(row.get("must_preserve", []), ensure_ascii=False))
    print("must remove:", json.dumps(row.get("must_remove", []), ensure_ascii=False))
    print("allowed additions:", json.dumps(row.get("allowed_additions", []), ensure_ascii=False))
    print("RAW:\n" + row["raw"])
    print("EXPECTED:\n" + row["expected"])


def main() -> int:
    args = parse_args()
    if not args.reviewer_ref.strip():
        raise RuntimeError("--reviewer-ref must be non-empty")
    decision_path = args.decisions.resolve()
    if decision_path == REPO_ROOT.resolve() or REPO_ROOT.resolve() in decision_path.parents:
        raise RuntimeError("human decision ledgers must stay outside the repository")
    if any("blind" in str(path).casefold() for path in args.records):
        raise RuntimeError("authoring-side review tool refuses blind inputs")
    rows = [row for path in args.records for row in read_jsonl(path)]
    ids = [row.get("id") for row in rows]
    if any(not isinstance(value, str) or not value for value in ids) or len(ids) != len(set(ids)):
        raise RuntimeError("review inputs contain a missing or duplicate ID")
    if any(str(row.get("split", "")).casefold().startswith("blind") for row in rows):
        raise RuntimeError("authoring-side review tool refuses blind rows")
    completed = existing_keys(args.decisions)
    pending = [row for row in rows if (row["id"], args.reviewer_ref) not in completed]
    args.decisions.parent.mkdir(parents=True, exist_ok=True)
    approved = rejected = skipped = 0
    print(f"Reviewer {args.reviewer_ref}: {len(pending)} pending of {len(rows)} selected rows.")
    with args.decisions.open("a", encoding="utf-8", newline="\n") as handle:
        for ordinal, row in enumerate(pending, 1):
            render(row, ordinal, len(pending))
            while True:
                action = input("Decision [approve/reject/skip/quit]: ").strip().casefold()
                if action in {"approve", "a"}:
                    decision = "approved"
                    reason = input("Optional reason: ").strip()
                    approved += 1
                    break
                if action in {"reject", "r"}:
                    reason = input("Required rejection reason: ").strip()
                    if not reason:
                        print("A rejection reason is required.")
                        continue
                    decision = "rejected"
                    rejected += 1
                    break
                if action in {"skip", "s"}:
                    skipped += 1
                    decision = ""
                    break
                if action in {"quit", "q"}:
                    print(json.dumps({"approved": approved, "rejected": rejected, "skipped": skipped, "remaining": len(pending) - ordinal + 1}, sort_keys=True))
                    return 0
                print("Enter approve, reject, skip, or quit.")
            if not decision:
                continue
            record = {
                "id": row["id"], "decision": decision,
                "reviewer_ref": args.reviewer_ref,
                "reviewed_at": datetime.now(timezone.utc).date().isoformat(),
            }
            if reason:
                record["reason"] = reason
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    print(json.dumps({"approved": approved, "rejected": rejected, "skipped": skipped, "remaining": skipped}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
