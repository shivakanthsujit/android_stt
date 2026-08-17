#!/usr/bin/env python3
"""Validate and merge deterministic OpenAI cleanup-evaluation shard files."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence


RUNNER_PATH = Path(__file__).resolve().with_name("run-cleanup-openai.py")
SPEC = importlib.util.spec_from_file_location("cleanup_openai_runner_for_merge", RUNNER_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import machinery failure
    raise RuntimeError(f"cannot load runner from {RUNNER_PATH}")
runner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runner
SPEC.loader.exec_module(runner)


class MergeError(Exception):
    """A fail-closed shard or output-contract error."""


def _read_rows(path: Path) -> list[tuple[int, dict[str, Any]]]:
    try:
        handle = path.open("r", encoding="utf-8")
    except OSError as exc:
        raise MergeError(f"cannot read shard {path}: {exc}") from exc
    rows: list[tuple[int, dict[str, Any]]] = []
    with handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise MergeError(f"{path}:{line_number}: blank records are forbidden")
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MergeError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(value, dict):
                raise MergeError(f"{path}:{line_number}: expected a JSON object")
            rows.append((line_number, value))
    return rows


def _require_string(row: dict[str, Any], key: str, location: str) -> str:
    value = row.get(key)
    if not isinstance(value, str):
        raise MergeError(f"{location}: {key} must be a string")
    return value


def _require_string_list(row: dict[str, Any], key: str, location: str) -> list[str]:
    value = row.get(key)
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise MergeError(f"{location}: {key} must be a list of strings")
    return value


def _validate_timing(value: Any, location: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MergeError(f"{location}: timing must be a finite number or null")
    if not math.isfinite(float(value)) or value < 0:
        raise MergeError(f"{location}: timing must be finite and non-negative")


def validate_and_order(
    *,
    cases_path: Path,
    shard_paths: Sequence[Path],
    shard_count: int,
    case_ids: Sequence[str] = (),
) -> list[dict[str, Any]]:
    if shard_count <= 0:
        raise MergeError("--shard-count must be positive")
    if len(shard_paths) != shard_count:
        raise MergeError(
            f"expected exactly {shard_count} --input paths in shard-index order; "
            f"received {len(shard_paths)}"
        )
    if len(set(shard_paths)) != len(shard_paths):
        raise MergeError("shard input paths must be unique")
    runner.reject_blind_cases_path(cases_path)
    try:
        cases = runner.load_cases(cases_path)
        cases_sha256 = runner.sha256_file(cases_path)
    except runner.RunnerError as exc:
        raise MergeError(str(exc)) from exc
    requested = set(case_ids)
    if requested:
        known = {case.case_id for case in cases}
        unknown = sorted(requested - known)
        if unknown:
            raise MergeError("unknown --case-id value(s): " + ", ".join(unknown))
        cases = tuple(case for case in cases if case.case_id in requested)

    by_id: dict[str, dict[str, Any]] = {}
    fingerprints: set[str] = set()
    source_indices = {case.case_id: index for index, case in enumerate(cases)}
    for input_shard_index, path in enumerate(shard_paths):
        for line_number, row in _read_rows(path):
            location = f"{path}:{line_number}"
            case_id = _require_string(row, "case_id", location)
            if case_id not in source_indices:
                raise MergeError(f"{location}: unknown or unselected case_id {case_id!r}")
            if case_id in by_id:
                raise MergeError(f"{location}: duplicate case_id {case_id!r}")
            case = cases[source_indices[case_id]]
            expected_shard = runner.stable_shard_index(case_id, shard_count)
            metadata = {
                "source_index": source_indices[case_id],
                "shard_count": shard_count,
                "shard_index": expected_shard,
                "cases_sha256": cases_sha256,
            }
            for key, expected in metadata.items():
                if row.get(key) != expected:
                    raise MergeError(f"{location}: {key} must equal {expected!r}")
            if expected_shard != input_shard_index:
                raise MergeError(
                    f"{location}: record belongs to shard {expected_shard}, not input "
                    f"position {input_shard_index}"
                )
            fingerprint = _require_string(row, "evaluation_fingerprint", location)
            fingerprints.add(fingerprint)
            canonical = {
                "raw": case.raw,
                "expected": case.expected,
                "categories": list(case.categories),
                "must_preserve": list(case.must_preserve),
                "must_remove": list(case.must_remove),
            }
            for key, expected in canonical.items():
                actual = (
                    _require_string(row, key, location)
                    if isinstance(expected, str)
                    else _require_string_list(row, key, location)
                )
                if actual != expected:
                    raise MergeError(f"{location}: {key} differs from source cases")
            _require_string(row, "model_text", location)
            _require_string(row, "selected_text", location)
            _require_string(row, "guardrail_selected_text", location)
            if row.get("raw_model_output_is_selected_for_scoring") is not True:
                raise MergeError(
                    f"{location}: raw model output must be selected for scoring"
                )
            timings = row.get("timings")
            if not isinstance(timings, dict):
                raise MergeError(f"{location}: timings must be an object")
            for key in ("ttft_ms", "total_ms"):
                if key not in timings:
                    raise MergeError(f"{location}: timings.{key} is required")
                _validate_timing(timings[key], f"{location}:timings.{key}")
            by_id[case_id] = row

    if len(fingerprints) > 1:
        raise MergeError("shards have different evaluation fingerprints")
    expected_ids = [case.case_id for case in cases]
    missing = [case_id for case_id in expected_ids if case_id not in by_id]
    if missing:
        preview = ", ".join(missing[:10])
        suffix = " ..." if len(missing) > 10 else ""
        raise MergeError(f"missing {len(missing)} case(s): {preview}{suffix}")
    return [by_id[case_id] for case_id in expected_ids]


def write_merged(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    if path.exists():
        raise MergeError(f"refusing to overwrite merged output {path}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    except OSError as exc:
        raise MergeError(f"cannot write merged output {path}: {exc}") from exc


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="repeat exactly once per shard, in zero-based shard-index order",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case-id", action="append", default=[])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_argument_parser()
    arguments = parser.parse_args(argv)
    try:
        rows = validate_and_order(
            cases_path=arguments.cases,
            shard_paths=arguments.input,
            shard_count=arguments.shard_count,
            case_ids=arguments.case_id,
        )
        write_merged(arguments.output, rows)
    except MergeError as exc:
        parser.exit(2, f"error: {exc}\n")
    print(f"merged {len(rows)} cases into {arguments.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
