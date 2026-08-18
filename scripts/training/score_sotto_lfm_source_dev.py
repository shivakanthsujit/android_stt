#!/usr/bin/env python3
"""Score Sotto LFM publisher-dev generations by source without exporting example text."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_ROOT))

from infer_sotto_lfm import read_jsonl, sha256_file


def normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n")).strip()


def score(cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    indexed = {row.get("case_id"): row for row in results}
    case_ids = [row.get("id") for row in cases]
    if len(indexed) != len(results) or set(indexed) != set(case_ids):
        raise RuntimeError("case and result IDs do not form the same unique set")
    counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "exact": 0, "empty": 0, "cap_hits": 0, "guardrail_flags": 0},
    )
    for case in cases:
        source = case.get("source_id")
        if not isinstance(source, str) or not source:
            raise RuntimeError("source-dev case is missing source_id")
        result = indexed[case["id"]]
        if result.get("raw") != case.get("raw") or result.get("expected") != case.get("expected"):
            raise RuntimeError(f"{case['id']}: result text does not match its source case")
        output, expected = normalize(result.get("model_text", "")), normalize(case["expected"])
        item = counts[source]
        item["records"] += 1
        item["exact"] += int(output == expected)
        item["empty"] += int(not output)
        item["cap_hits"] += int(result.get("hit_output_token_limit") is True)
        item["guardrail_flags"] += int(result.get("guardrail_would_fallback") is True)
    sources = {
        source: {**item, "exact_rate": item["exact"] / item["records"]}
        for source, item in sorted(counts.items())
    }
    overall = {
        key: sum(item[key] for item in counts.values())
        for key in ("records", "exact", "empty", "cap_hits", "guardrail_flags")
    }
    overall["exact_rate"] = overall["exact"] / overall["records"]
    return {"overall": overall, "sources": sources, "contains_example_text": False}


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
    cases, results = read_jsonl(args.cases), read_jsonl(args.results)
    report = {
        "schema_version": "sotto-lfm-source-dev-score-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases_sha256": sha256_file(args.cases),
        "results_sha256": sha256_file(args.results),
        **score(cases, results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"overall": report["overall"], "sources": report["sources"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
