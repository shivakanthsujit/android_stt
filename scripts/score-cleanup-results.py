#!/usr/bin/env python3
"""Score deterministic dictation-cleanup JSONL runs.

The scorer intentionally uses only Python's standard library so it can run on
the macOS host before any Android tooling is configured.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


DEFAULT_CASES = Path("docs/evaluation/cleanup_cases.jsonl")


class InputError(Exception):
    """Raised when an input file violates the scorer's schema."""


@dataclass(frozen=True)
class CleanupCase:
    case_id: str
    raw: str
    expected: str
    categories: tuple[str, ...]
    must_preserve: tuple[str, ...]


@dataclass(frozen=True)
class ResultRecord:
    case_id: str
    model_text: str
    selected_text: str
    used_fallback: bool
    timings: dict[str, Any]
    prompt_variant: str | None
    finish_reason: str | None
    max_output_tokens: int | None
    hit_output_token_limit: bool | None
    completion_tokens: int | None


@dataclass(frozen=True)
class Run:
    label: str
    source: Path
    prompt_variant: str | None
    records: tuple[ResultRecord, ...]


def normalize_text(value: str) -> str:
    """Apply the deliberately narrow normalization defined by the corpus."""

    return unicodedata.normalize("NFC", value.replace("\r\n", "\n")).strip()


def read_jsonl(path: Path) -> list[tuple[int, dict[str, Any]]]:
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc

    rows: list[tuple[int, dict[str, Any]]] = []
    with handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise InputError(
                    f"{path}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            if not isinstance(value, dict):
                raise InputError(f"{path}:{line_number}: expected a JSON object")
            rows.append((line_number, value))
    if not rows:
        raise InputError(f"{path}: contains no JSON records")
    return rows


def require_string(
    row: dict[str, Any], field: str, path: Path, line_number: int
) -> str:
    value = row.get(field)
    if not isinstance(value, str):
        raise InputError(f"{path}:{line_number}: {field!r} must be a string")
    return value


def require_string_list(
    row: dict[str, Any], field: str, path: Path, line_number: int
) -> tuple[str, ...]:
    value = row.get(field)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
    ):
        raise InputError(
            f"{path}:{line_number}: {field!r} must be a non-empty list of "
            "non-empty strings"
        )
    return tuple(value)


def load_cases(path: Path) -> tuple[CleanupCase, ...]:
    cases: list[CleanupCase] = []
    seen: set[str] = set()
    for line_number, row in read_jsonl(path):
        case_id = require_string(row, "id", path, line_number)
        spoken = require_string(row, "spoken", path, line_number)
        raw = require_string(row, "raw", path, line_number)
        expected = require_string(row, "expected", path, line_number)
        categories = require_string_list(row, "categories", path, line_number)
        must_preserve = require_string_list(row, "must_preserve", path, line_number)
        if not case_id:
            raise InputError(f"{path}:{line_number}: 'id' must not be empty")
        if case_id in seen:
            raise InputError(f"{path}:{line_number}: duplicate case id {case_id!r}")
        if not spoken:
            raise InputError(f"{path}:{line_number}: 'spoken' must not be empty")
        if not raw:
            raise InputError(f"{path}:{line_number}: 'raw' must not be empty")
        if not expected:
            raise InputError(f"{path}:{line_number}: 'expected' must not be empty")
        if len(categories) != len(set(categories)):
            raise InputError(f"{path}:{line_number}: duplicate category")
        if len(must_preserve) != len(set(must_preserve)):
            raise InputError(f"{path}:{line_number}: duplicate must_preserve anchor")
        normalized_expected = normalize_text(expected)
        missing_anchors = [
            anchor
            for anchor in must_preserve
            if normalize_text(anchor) not in normalized_expected
        ]
        if missing_anchors:
            raise InputError(
                f"{path}:{line_number}: must_preserve anchor(s) absent from expected: "
                + ", ".join(repr(anchor) for anchor in missing_anchors)
            )
        seen.add(case_id)
        cases.append(
            CleanupCase(case_id, raw, expected, categories, must_preserve)
        )
    return tuple(cases)


def validate_timing_value(
    value: Any, location: str, *, allow_mapping: bool = True
) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        raise InputError(f"{location}: timing values must be numbers, objects, or null")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise InputError(f"{location}: timing values must be finite")
        return
    if allow_mapping and isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str) or not key:
                raise InputError(f"{location}: timing keys must be non-empty strings")
            validate_timing_value(child, f"{location}.{key}")
        return
    raise InputError(f"{location}: timing values must be numbers, objects, or null")


def load_result_records(path: Path) -> list[ResultRecord]:
    records: list[ResultRecord] = []
    for line_number, row in read_jsonl(path):
        case_id = require_string(row, "case_id", path, line_number)
        model_text = require_string(row, "model_text", path, line_number)
        selected_text = require_string(row, "selected_text", path, line_number)
        used_fallback = row.get("used_fallback")
        if not isinstance(used_fallback, bool):
            raise InputError(
                f"{path}:{line_number}: 'used_fallback' must be a boolean"
            )
        timings = row.get("timings")
        if not isinstance(timings, dict):
            raise InputError(f"{path}:{line_number}: 'timings' must be an object")
        validate_timing_value(timings, f"{path}:{line_number}:timings")
        prompt_variant = row.get("prompt_variant")
        if prompt_variant is not None and (
            not isinstance(prompt_variant, str) or not prompt_variant
        ):
            raise InputError(
                f"{path}:{line_number}: 'prompt_variant' must be a non-empty string"
            )

        finish_reason = row.get("finish_reason")
        if "finish_reason" in row and (
            not isinstance(finish_reason, str) or not finish_reason
        ):
            raise InputError(
                f"{path}:{line_number}: 'finish_reason' must be a non-empty string"
            )

        max_output_tokens = row.get("max_output_tokens")
        if "max_output_tokens" in row and (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or max_output_tokens <= 0
        ):
            raise InputError(
                f"{path}:{line_number}: 'max_output_tokens' must be a positive integer"
            )

        hit_output_token_limit = row.get("hit_output_token_limit")
        if "hit_output_token_limit" in row and not isinstance(
            hit_output_token_limit, bool
        ):
            raise InputError(
                f"{path}:{line_number}: 'hit_output_token_limit' must be a boolean"
            )

        completion_tokens = row.get("completion_tokens")
        if "completion_tokens" in row and (
            isinstance(completion_tokens, bool)
            or not isinstance(completion_tokens, int)
            or completion_tokens < 0
        ):
            raise InputError(
                f"{path}:{line_number}: 'completion_tokens' must be a non-negative integer"
            )
        if (
            isinstance(max_output_tokens, int)
            and isinstance(completion_tokens, int)
            and completion_tokens > max_output_tokens
        ):
            raise InputError(
                f"{path}:{line_number}: 'completion_tokens' must not exceed "
                "'max_output_tokens'"
            )
        records.append(
            ResultRecord(
                case_id,
                model_text,
                selected_text,
                used_fallback,
                timings,
                prompt_variant,
                finish_reason,
                max_output_tokens,
                hit_output_token_limit,
                completion_tokens,
            )
        )
    return records


def parse_result_spec(spec: str) -> tuple[str, Path]:
    whole_path = Path(spec)
    if whole_path.exists() or "=" not in spec:
        return whole_path.stem, whole_path
    label, raw_path = spec.split("=", 1)
    if not label or not raw_path:
        raise InputError(
            f"invalid result specification {spec!r}; expected [LABEL=]PATH"
        )
    return label, Path(raw_path)


def make_runs(specs: Sequence[str]) -> tuple[Run, ...]:
    runs: list[Run] = []
    used_labels: set[str] = set()
    for spec in specs:
        base_label, path = parse_result_spec(spec)
        groups: dict[str | None, list[ResultRecord]] = defaultdict(list)
        for record in load_result_records(path):
            groups[record.prompt_variant].append(record)
        for prompt_variant in sorted(groups, key=lambda item: item or ""):
            label = base_label
            if prompt_variant is not None:
                label = f"{base_label}[{prompt_variant}]"
            if label in used_labels:
                raise InputError(
                    f"duplicate run label {label!r}; use distinct LABEL=PATH inputs"
                )
            used_labels.add(label)
            runs.append(
                Run(label, path, prompt_variant, tuple(groups[prompt_variant]))
            )
    return tuple(runs)


def validate_run(
    run: Run, cases: Sequence[CleanupCase], allow_partial: bool
) -> dict[str, ResultRecord]:
    known = {case.case_id for case in cases}
    records: dict[str, ResultRecord] = {}
    for record in run.records:
        if not record.case_id:
            raise InputError(f"{run.source}: empty case_id in run {run.label!r}")
        if record.case_id not in known:
            raise InputError(
                f"{run.source}: unknown case_id {record.case_id!r} in run {run.label!r}"
            )
        if record.case_id in records:
            raise InputError(
                f"{run.source}: duplicate case_id {record.case_id!r} "
                f"in run {run.label!r}"
            )
        records[record.case_id] = record
    missing = [case.case_id for case in cases if case.case_id not in records]
    if missing and not allow_partial:
        raise InputError(
            f"{run.source}: run {run.label!r} is missing {len(missing)} case(s): "
            + ", ".join(missing)
        )
    return records


def ratio(count: int, total: int) -> float | None:
    return count / total if total else None


def summarize_stream(
    pairs: Sequence[tuple[CleanupCase, ResultRecord]],
    field: str,
    *,
    include_failures: bool,
) -> dict[str, Any]:
    exact_count = 0
    empty_count = 0
    expansion_count = 0
    anchor_count = 0
    anchor_total = 0
    case_preservation_count = 0
    failures: list[dict[str, Any]] = []

    for case, record in pairs:
        candidate = normalize_text(getattr(record, field))
        expected = normalize_text(case.expected)
        raw = normalize_text(case.raw)
        exact = candidate == expected
        empty = not candidate
        expansion = len(candidate) * 10 > len(raw) * 18
        missing_anchors = [
            anchor for anchor in case.must_preserve if anchor not in candidate
        ]
        preserved = len(case.must_preserve) - len(missing_anchors)

        exact_count += int(exact)
        empty_count += int(empty)
        expansion_count += int(expansion)
        anchor_count += preserved
        anchor_total += len(case.must_preserve)
        case_preservation_count += int(not missing_anchors)

        if include_failures and (not exact or missing_anchors or empty or expansion):
            reasons: list[str] = []
            if not exact:
                reasons.append("exact_mismatch")
            if missing_anchors:
                reasons.append("missing_preservation_anchor")
            if empty:
                reasons.append("empty")
            if expansion:
                reasons.append("expansion_guard")
            failures.append(
                {
                    "case_id": case.case_id,
                    "reasons": reasons,
                    "missing_anchors": missing_anchors,
                    "expected": expected,
                    "actual": candidate,
                }
            )

    total = len(pairs)
    result: dict[str, Any] = {
        "case_count": total,
        "exact_match_count": exact_count,
        "exact_match_rate": ratio(exact_count, total),
        "preserved_anchor_count": anchor_count,
        "preservation_anchor_count": anchor_total,
        "preservation_rate": ratio(anchor_count, anchor_total),
        "case_preservation_pass_count": case_preservation_count,
        "case_preservation_pass_rate": ratio(case_preservation_count, total),
        "empty_output_count": empty_count,
        "empty_output_rate": ratio(empty_count, total),
        "expansion_guard_count": expansion_count,
        "expansion_guard_rate": ratio(expansion_count, total),
    }
    if include_failures:
        result["failures"] = failures
    return result


def per_category(
    pairs: Sequence[tuple[CleanupCase, ResultRecord]], field: str
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[tuple[CleanupCase, ResultRecord]]] = defaultdict(list)
    for pair in pairs:
        for category in pair[0].categories:
            grouped[category].append(pair)
    return {
        category: summarize_stream(items, field, include_failures=False)
        for category, items in sorted(grouped.items())
    }


def flatten_timings(
    value: dict[str, Any], prefix: str = ""
) -> Iterable[tuple[str, float]]:
    for key in sorted(value):
        child = value[key]
        name = f"{prefix}.{key}" if prefix else key
        if child is None:
            continue
        if isinstance(child, dict):
            yield from flatten_timings(child, name)
        else:
            yield name, float(child)


def nearest_rank(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def summarize_timings(records: Iterable[ResultRecord]) -> dict[str, dict[str, Any]]:
    samples: dict[str, list[float]] = defaultdict(list)
    for record in records:
        for name, value in flatten_timings(record.timings):
            samples[name].append(value)
    return {
        name: {
            "count": len(values),
            "min": min(values),
            "median": statistics.median(values),
            "p95": nearest_rank(values, 0.95),
            "max": max(values),
            "mean": statistics.fmean(values),
        }
        for name, values in sorted(samples.items())
    }


def score_run(
    run: Run,
    cases: Sequence[CleanupCase],
    records: dict[str, ResultRecord],
) -> dict[str, Any]:
    pairs = [(case, records[case.case_id]) for case in cases if case.case_id in records]
    fallback_count = sum(record.used_fallback for _, record in pairs)
    fallback_selected_raw_count = sum(
        record.used_fallback
        and normalize_text(record.selected_text) == normalize_text(case.raw)
        for case, record in pairs
    )
    finish_reason_counts = Counter(
        record.finish_reason
        for _, record in pairs
        if record.finish_reason is not None
    )
    cap_reported_records = [
        (case, record)
        for case, record in pairs
        if record.hit_output_token_limit is not None
    ]
    cap_hit_case_ids = [
        case.case_id
        for case, record in cap_reported_records
        if record.hit_output_token_limit
    ]
    return {
        "label": run.label,
        "source": str(run.source),
        "prompt_variant": run.prompt_variant,
        "record_count": len(pairs),
        "fallback_count": fallback_count,
        "fallback_rate": ratio(fallback_count, len(pairs)),
        "fallback_selected_raw_count": fallback_selected_raw_count,
        "finish_reason_reported_count": sum(finish_reason_counts.values()),
        "finish_reason_counts": dict(sorted(finish_reason_counts.items())),
        "cap_hit_reported_count": len(cap_reported_records),
        "cap_hit_count": len(cap_hit_case_ids),
        "cap_hit_rate": ratio(len(cap_hit_case_ids), len(cap_reported_records)),
        "cap_hit_case_ids": cap_hit_case_ids,
        "streams": {
            field: summarize_stream(pairs, field, include_failures=True)
            for field in ("model_text", "selected_text")
        },
        "per_category": {
            field: per_category(pairs, field)
            for field in ("model_text", "selected_text")
        },
        "timings": summarize_timings(record for _, record in pairs),
    }


def percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def print_stream_summary(name: str, summary: dict[str, Any]) -> None:
    print(f"  {name}:")
    print(
        "    exact "
        f"{summary['exact_match_count']}/{summary['case_count']} "
        f"({percent(summary['exact_match_rate'])}); "
        "preservation "
        f"{summary['preserved_anchor_count']}/"
        f"{summary['preservation_anchor_count']} "
        f"({percent(summary['preservation_rate'])}); "
        "case preservation "
        f"{summary['case_preservation_pass_count']}/{summary['case_count']} "
        f"({percent(summary['case_preservation_pass_rate'])})"
    )
    print(
        f"    empty {summary['empty_output_count']} "
        f"({percent(summary['empty_output_rate'])}); "
        f"expansion guard {summary['expansion_guard_count']} "
        f"({percent(summary['expansion_guard_rate'])})"
    )


def print_text_report(report: dict[str, Any]) -> None:
    runs = report["runs"]
    print(
        f"Cases: {report['case_count']} from {report['cases_file']} | "
        f"Runs: {len(runs)}"
    )
    print()
    print("Comparison (post-guard selected_text)")
    print("run\tcases\texact\tpreserve\tempty\texpand\tfallback\tcap-hit")
    for run in runs:
        selected = run["streams"]["selected_text"]
        print(
            f"{run['label']}\t{run['record_count']}\t"
            f"{percent(selected['exact_match_rate'])}\t"
            f"{percent(selected['preservation_rate'])}\t"
            f"{percent(selected['empty_output_rate'])}\t"
            f"{percent(selected['expansion_guard_rate'])}\t"
            f"{percent(run['fallback_rate'])}\t"
            f"{percent(run['cap_hit_rate'])}"
        )

    for run in runs:
        print()
        print(f"Run: {run['label']} ({run['source']})")
        if run["prompt_variant"] is not None:
            print(f"  prompt variant: {run['prompt_variant']}")
        print(
            f"  fallback: {run['fallback_count']}/{run['record_count']} "
            f"({percent(run['fallback_rate'])}); selected raw on fallback: "
            f"{run['fallback_selected_raw_count']}/{run['fallback_count']}"
        )
        if run["finish_reason_reported_count"]:
            finish_reasons = ", ".join(
                f"{reason}={count}"
                for reason, count in run["finish_reason_counts"].items()
            )
            print(
                "  finish reasons: "
                f"{finish_reasons} "
                f"(reported {run['finish_reason_reported_count']}/"
                f"{run['record_count']})"
            )
        else:
            print("  finish reasons: not reported")
        print(
            f"  output-token cap hits: {run['cap_hit_count']}/"
            f"{run['cap_hit_reported_count']} "
            f"({percent(run['cap_hit_rate'])})"
        )
        if run["cap_hit_case_ids"]:
            print("    cases: " + ", ".join(run["cap_hit_case_ids"]))
        else:
            print("    cases: none")
        for field in ("model_text", "selected_text"):
            print_stream_summary(field, run["streams"][field])

        print("  per-category (model exact/preserve | selected exact/preserve):")
        model_categories = run["per_category"]["model_text"]
        selected_categories = run["per_category"]["selected_text"]
        for category in selected_categories:
            model = model_categories[category]
            selected = selected_categories[category]
            print(
                f"    {category}: "
                f"{percent(model['exact_match_rate'])}/"
                f"{percent(model['preservation_rate'])} | "
                f"{percent(selected['exact_match_rate'])}/"
                f"{percent(selected['preservation_rate'])} "
                f"({selected['case_count']} cases)"
            )

        if run["timings"]:
            print("  timings:")
            for name, timing in run["timings"].items():
                print(
                    f"    {name}: n={timing['count']} "
                    f"median={timing['median']:.3f} p95={timing['p95']:.3f} "
                    f"mean={timing['mean']:.3f} min={timing['min']:.3f} "
                    f"max={timing['max']:.3f}"
                )

        for field in ("model_text", "selected_text"):
            failures = run["streams"][field]["failures"]
            print(f"  {field} failures ({len(failures)}):")
            if not failures:
                print("    none")
                continue
            for failure in failures:
                detail = ", ".join(failure["reasons"])
                if failure["missing_anchors"]:
                    detail += "; missing=" + repr(failure["missing_anchors"])
                print(f"    {failure['case_id']}: {detail}")
                print(f"      expected: {failure['expected']!r}")
                print(f"      actual:   {failure['actual']!r}")


def selected_run_failed(run: dict[str, Any]) -> bool:
    summary = run["streams"]["selected_text"]
    return any(
        (
            summary["exact_match_count"] != summary["case_count"],
            summary["case_preservation_pass_count"] != summary["case_count"],
            summary["empty_output_count"] != 0,
            summary["expansion_guard_count"] != 0,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Score one or more cleanup result JSONL files. Result arguments "
            "may be PATH or LABEL=PATH. Files containing a prompt_variant "
            "field are split into separate runs automatically."
        )
    )
    parser.add_argument(
        "results",
        nargs="*",
        metavar="[LABEL=]RESULT.jsonl",
        help="result JSONL file; pass multiple files to compare runs",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES,
        help=f"cleanup case JSONL (default: {DEFAULT_CASES})",
    )
    parser.add_argument(
        "--validate-cases-only",
        action="store_true",
        help="validate the case JSONL schema and preservation anchors, then exit",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="report format (default: text)",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="score partial runs instead of rejecting missing case IDs",
    )
    parser.add_argument(
        "--fail-on-mismatch",
        action="store_true",
        help="exit 1 unless every selected_text passes all strict checks",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.validate_cases_only and not args.results:
        parser.error(
            "at least one result JSONL is required unless "
            "--validate-cases-only is used"
        )
    try:
        cases = load_cases(args.cases)
        if args.validate_cases_only:
            print(f"Valid cases: {len(cases)} from {args.cases}")
            return 0
        runs = make_runs(args.results)
        scored_runs = []
        for run in runs:
            records = validate_run(run, cases, args.allow_partial)
            scored_runs.append(score_run(run, cases, records))
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = {
        "cases_file": str(args.cases),
        "case_count": len(cases),
        "runs": scored_runs,
    }
    if args.format == "json":
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
        print()
    else:
        print_text_report(report)

    if args.fail_on_mismatch and any(selected_run_failed(run) for run in scored_runs):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
