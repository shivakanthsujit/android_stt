#!/usr/bin/env python3
"""Score raw adapter outputs on authoring dev data without emitting example text."""

from __future__ import annotations

import argparse
import json
import statistics
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from train_cleanup_adapter import read_jsonl, sha256_file


def normalize(value: str) -> str:
    return unicodedata.normalize("NFC", value.replace("\r\n", "\n")).strip()


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    return sorted(values)[max(0, min(len(values) - 1, int(len(values) * fraction) - 1))]


def reject_blind(path: Path, rows: list[dict[str, Any]]) -> None:
    if "blind" in str(path).casefold() or any(str(row.get("split", "")).casefold().startswith("blind") for row in rows):
        raise RuntimeError("authoring dev scorer refuses blind inputs")


def score(cases: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in results:
        case_id = row.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in by_id:
            raise RuntimeError("results contain a missing or duplicate case_id")
        by_id[case_id] = row
    case_ids = [row.get("id") for row in cases]
    if any(not isinstance(case_id, str) or not case_id for case_id in case_ids) or len(set(case_ids)) != len(case_ids):
        raise RuntimeError("cases contain a missing or duplicate id")
    if set(case_ids) != set(by_id):
        raise RuntimeError("result IDs do not exactly match case IDs")

    category_totals: dict[str, int] = defaultdict(int)
    category_exact: dict[str, int] = defaultdict(int)
    exact = preserve_ok = preserve_total = removal_ok = removal_total = 0
    noop_total = noop_exact = must_not_answer_total = must_not_answer_exact = 0
    empty = cap_hits = guardrail_flags = 0
    failure_ids: list[str] = []
    total_times: list[float] = []
    ttfts: list[float] = []
    for case in cases:
        result = by_id[case["id"]]
        if result.get("raw") != case.get("raw") or result.get("expected") != case.get("expected"):
            raise RuntimeError(f"{case['id']}: result raw/expected do not match cases")
        output = normalize(result.get("model_text", ""))
        expected = normalize(case["expected"])
        is_exact = output == expected
        exact += int(is_exact)
        if not is_exact:
            failure_ids.append(case["id"])
        categories = case.get("categories", [])
        for category in categories:
            category_totals[category] += 1
            category_exact[category] += int(is_exact)
        anchors = case.get("must_preserve", [])
        preserve_total += len(anchors)
        preserve_ok += sum(normalize(anchor) in output for anchor in anchors)
        removals = case.get("must_remove", [])
        if removals:
            removal_total += 1
            removal_ok += int(all(normalize(anchor) not in output for anchor in removals))
        if normalize(case["raw"]) == expected:
            noop_total += 1
            noop_exact += int(is_exact)
        if "must_not_answer" in categories:
            must_not_answer_total += 1
            must_not_answer_exact += int(is_exact)
        empty += int(not output)
        cap_hits += int(result.get("hit_output_token_limit") is True)
        guardrail_flags += int(result.get("guardrail_would_fallback") is True)
        timings = result.get("timings", {})
        if isinstance(timings.get("total_ms"), (int, float)):
            total_times.append(float(timings["total_ms"]))
        if isinstance(timings.get("ttft_ms"), (int, float)):
            ttfts.append(float(timings["ttft_ms"]))
    total = len(cases)
    return {
        "records": total,
        "raw_exact_match": {"count": exact, "rate": ratio(exact, total)},
        "must_preserve_anchors": {"preserved": preserve_ok, "total": preserve_total, "rate": ratio(preserve_ok, preserve_total)},
        "correction_rows": {"all_must_remove_removed": removal_ok, "total": removal_total, "rate": ratio(removal_ok, removal_total)},
        "no_op_rows": {"exact": noop_exact, "total": noop_total, "rate": ratio(noop_exact, noop_total)},
        "must_not_answer_rows": {"exact": must_not_answer_exact, "total": must_not_answer_total, "rate": ratio(must_not_answer_exact, must_not_answer_total)},
        "failure_counts": {"empty_output": empty, "output_cap_hit": cap_hits, "guardrail_flag": guardrail_flags},
        "category_exact_match": {
            category: {"exact": category_exact[category], "total": count, "rate": ratio(category_exact[category], count)}
            for category, count in sorted(category_totals.items())
        },
        "latency_ms": {
            "ttft_median": statistics.median(ttfts) if ttfts else None,
            "ttft_p95": percentile(ttfts, 0.95),
            "total_median": statistics.median(total_times) if total_times else None,
            "total_p95": percentile(total_times, 0.95),
        },
        "raw_semantic_safety": {
            "status": "not_assessed",
            "note": "Automated metrics and guardrail flags cannot qualify raw semantic safety; complete manual review separately.",
        },
        "non_exact_case_ids": failure_ids,
        "contains_example_text": False,
    }


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
    reject_blind(args.cases, cases)
    report = {
        "schema_version": "cleanup-training-dev-score-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "cases_sha256": sha256_file(args.cases),
        "results_sha256": sha256_file(args.results),
        **score(cases, results),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"records": report["records"], "raw_exact_match": report["raw_exact_match"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
