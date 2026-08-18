#!/usr/bin/env python3
"""Summarize debug file-fed Parakeet -> Sotto JSONL results."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path


def read_results(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise ValueError("Result file is empty")
    required = {
        "case_id", "reference", "raw_stt", "raw_model_output", "guarded_output",
        "used_fallback", "stt_inference_ms", "cleanup_total_ms", "pipeline_total_ms",
    }
    for index, row in enumerate(rows, 1):
        missing = required - set(row)
        if missing:
            raise ValueError(f"Row {index} is missing: {sorted(missing)}")
    if len({row["case_id"] for row in rows}) != len(rows):
        raise ValueError("Result contains duplicate case IDs")
    return rows


def normalize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower())


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percentile * len(ordered) + 0.999999)) - 1))
    return ordered[index]


def timing(values: list[float]) -> dict[str, float]:
    return {
        "median_ms": statistics.median(values),
        "p90_ms": percentile_nearest_rank(values, 0.9),
        "max_ms": max(values),
    }


def read_expected_cases(path: Path) -> dict[str, str]:
    expected: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        case_id = row.get("id")
        target = row.get("expected")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"Expected case line {line_number} has no valid id")
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f"Expected case {case_id} has no cleaned target")
        if case_id in expected:
            raise ValueError(f"Expected cases contain duplicate id: {case_id}")
        expected[case_id] = target
    if not expected:
        raise ValueError("Expected case file is empty")
    return expected


def summarize(rows: list[dict], expected: dict[str, str] | None = None) -> dict:
    referenced = [row for row in rows if row["reference"].strip()]
    summary = {
        "schema_version": 1,
        "case_count": len(rows),
        "fallback_count": sum(bool(row["used_fallback"]) for row in rows),
        "raw_stt_strict_exact": sum(
            row["raw_stt"] == row["reference"] for row in referenced
        ),
        "raw_stt_normalized_exact": sum(
            normalize(row["raw_stt"]) == normalize(row["reference"]) for row in referenced
        ),
        "referenced_case_count": len(referenced),
        "stt_inference": timing([float(row["stt_inference_ms"]) for row in rows]),
        "cleanup_total": timing([float(row["cleanup_total_ms"]) for row in rows]),
        "pipeline_total": timing([float(row["pipeline_total_ms"]) for row in rows]),
    }
    if expected is not None:
        result_ids = {row["case_id"] for row in rows}
        missing = result_ids - set(expected)
        extra = set(expected) - result_ids
        if missing or extra:
            raise ValueError(
                f"Expected/result case mismatch: missing={sorted(missing)}, extra={sorted(extra)}"
            )
        summary.update(
            {
                "expected_case_count": len(expected),
                "raw_model_target_strict_exact": sum(
                    row["raw_model_output"] == expected[row["case_id"]] for row in rows
                ),
                "raw_model_target_normalized_exact": sum(
                    normalize(row["raw_model_output"])
                    == normalize(expected[row["case_id"]])
                    for row in rows
                ),
                "guarded_target_strict_exact": sum(
                    row["guarded_output"] == expected[row["case_id"]] for row in rows
                ),
                "guarded_target_normalized_exact": sum(
                    normalize(row["guarded_output"])
                    == normalize(expected[row["case_id"]])
                    for row in rows
                ),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--expected-cases", type=Path)
    args = parser.parse_args()
    rows = read_results(args.result)
    expected = read_expected_cases(args.expected_cases) if args.expected_cases else None
    summary = summarize(rows, expected)
    summary["result_file"] = str(args.result)
    if args.expected_cases:
        summary["expected_cases_file"] = str(args.expected_cases)
    serialized = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    print(serialized, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(serialized, encoding="utf-8")


if __name__ == "__main__":
    main()
