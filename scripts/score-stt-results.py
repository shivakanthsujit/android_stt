#!/usr/bin/env python3
"""Score file-fed Android STT JSONL results with normalized word error rate."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import unicodedata
from pathlib import Path
from typing import Any


def normalize_words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    characters = [
        "'"
        if character in {"'", "’", "‘"}
        else character
        if unicodedata.category(character)[0] in {"L", "N"}
        else " "
        for character in normalized
    ]
    return "".join(characters).split()


def edit_counts(reference: list[str], hypothesis: list[str]) -> tuple[int, int, int]:
    # Each cell is (total errors, substitutions, insertions, deletions).
    previous = [(index, 0, index, 0) for index in range(len(hypothesis) + 1)]
    for reference_index, reference_word in enumerate(reference, start=1):
        current = [(reference_index, 0, 0, reference_index)]
        for hypothesis_index, hypothesis_word in enumerate(hypothesis, start=1):
            if reference_word == hypothesis_word:
                diagonal = previous[hypothesis_index - 1]
            else:
                base = previous[hypothesis_index - 1]
                diagonal = (base[0] + 1, base[1] + 1, base[2], base[3])
            insertion_base = current[hypothesis_index - 1]
            insertion = (
                insertion_base[0] + 1,
                insertion_base[1],
                insertion_base[2] + 1,
                insertion_base[3],
            )
            deletion_base = previous[hypothesis_index]
            deletion = (
                deletion_base[0] + 1,
                deletion_base[1],
                deletion_base[2],
                deletion_base[3] + 1,
            )
            current.append(min(diagonal, insertion, deletion))
        previous = current
    _, substitutions, insertions, deletions = previous[-1]
    return substitutions, insertions, deletions


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                row = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number}: {error}") from error
            if row.get("schema_version") != 1:
                raise ValueError(f"Unsupported schema on line {line_number}")
            rows.append(row)
    if not rows:
        raise ValueError("Result file has no rows")
    return rows


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    measured = [row for row in rows if row.get("phase") == "measured"]
    if not measured:
        raise ValueError("Result file has no measured rows")
    engines = {str(row["engine"]) for row in measured}
    run_ids = {str(row["run_id"]) for row in measured}
    if len(engines) != 1 or len(run_ids) != 1:
        raise ValueError("Rows contain multiple engines or run IDs")
    keys = [(str(row["case_id"]), int(row["repeat_index"])) for row in measured]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate case/repeat result")

    quality_rows: dict[str, dict[str, Any]] = {}
    for row in measured:
        case_id = str(row["case_id"])
        if case_id not in quality_rows or int(row["repeat_index"]) < int(
            quality_rows[case_id]["repeat_index"]
        ):
            quality_rows[case_id] = row

    substitutions = insertions = deletions = reference_words = 0
    for row in quality_rows.values():
        reference = normalize_words(str(row["reference"]))
        hypothesis = normalize_words(str(row["hypothesis"]))
        row_substitutions, row_insertions, row_deletions = edit_counts(reference, hypothesis)
        substitutions += row_substitutions
        insertions += row_insertions
        deletions += row_deletions
        reference_words += len(reference)
    if reference_words == 0:
        raise ValueError("References contain no scorable words")

    inference_ms = [float(row["inference_duration_ms"]) for row in measured]
    rtf = [float(row["real_time_factor"]) for row in measured]
    process_pss_kb = [
        int(row["process_pss_kb_after_inference"])
        for row in measured
        if "process_pss_kb_after_inference" in row
    ]
    thermal_statuses = [
        int(row["thermal_status_after_inference"])
        for row in measured
        if "thermal_status_after_inference" in row
    ]
    process_cpu_ms = [
        float(row["process_cpu_duration_ms"])
        for row in measured
        if "process_cpu_duration_ms" in row
    ]
    average_process_cpu_cores = [
        float(row["average_process_cpu_cores"])
        for row in measured
        if "average_process_cpu_cores" in row
    ]
    audio_ms_by_case = {
        str(row["case_id"]): float(row["audio_duration_ms"]) for row in measured
    }
    median_inference_by_case = {
        case_id: statistics.median(
            float(row["inference_duration_ms"])
            for row in measured
            if str(row["case_id"]) == case_id
        )
        for case_id in quality_rows
    }
    total_audio_ms = sum(audio_ms_by_case.values())
    total_median_inference_ms = sum(median_inference_by_case.values())
    errors = substitutions + insertions + deletions
    hypotheses_by_case = {
        case_id: {str(row["hypothesis"]) for row in measured if str(row["case_id"]) == case_id}
        for case_id in quality_rows
    }
    normalized_hypotheses_by_case = {
        case_id: {
            tuple(normalize_words(str(row["hypothesis"])))
            for row in measured
            if str(row["case_id"]) == case_id
        }
        for case_id in quality_rows
    }

    summary = {
        "schema_version": 1,
        "run_id": next(iter(run_ids)),
        "engine": next(iter(engines)),
        "case_count": len(quality_rows),
        "measured_run_count": len(measured),
        "reference_word_count": reference_words,
        "substitutions": substitutions,
        "insertions": insertions,
        "deletions": deletions,
        "word_errors": errors,
        "wer": errors / reference_words,
        "unstable_case_count": sum(len(outputs) > 1 for outputs in hypotheses_by_case.values()),
        "normalized_unstable_case_count": sum(
            len(outputs) > 1 for outputs in normalized_hypotheses_by_case.values()
        ),
        "model_load_duration_ms": float(measured[0]["model_load_duration_ms"]),
        "median_inference_duration_ms": statistics.median(inference_ms),
        "p90_inference_duration_ms": percentile(inference_ms, 0.9),
        "p99_inference_duration_ms": percentile(inference_ms, 0.99),
        "max_inference_duration_ms": max(inference_ms),
        "median_real_time_factor": statistics.median(rtf),
        "p90_real_time_factor": percentile(rtf, 0.9),
        "p99_real_time_factor": percentile(rtf, 0.99),
        "max_real_time_factor": max(rtf),
        "corpus_real_time_factor": total_median_inference_ms / total_audio_ms,
        "corpus_realtime_multiple": total_audio_ms / total_median_inference_ms,
        "total_audio_duration_ms": total_audio_ms,
    }
    if process_pss_kb:
        summary["max_process_pss_kb_after_inference"] = max(process_pss_kb)
    if thermal_statuses:
        summary["max_thermal_status_after_inference"] = max(thermal_statuses)
    if process_cpu_ms:
        summary["total_process_cpu_duration_ms"] = sum(process_cpu_ms)
        summary["median_process_cpu_duration_ms"] = statistics.median(process_cpu_ms)
    if average_process_cpu_cores:
        summary["median_average_process_cpu_cores"] = statistics.median(
            average_process_cpu_cores
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    summary = score(load_rows(args.results))
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"Engine: {summary['engine']}")
    print(
        f"WER: {summary['wer'] * 100:.2f}% "
        f"({summary['word_errors']}/{summary['reference_word_count']} words; "
        f"S={summary['substitutions']} I={summary['insertions']} D={summary['deletions']})"
    )
    print(
        f"Inference: median {summary['median_inference_duration_ms']:.1f} ms, "
        f"p90 {summary['p90_inference_duration_ms']:.1f} ms, "
        f"p99 {summary['p99_inference_duration_ms']:.1f} ms, "
        f"max {summary['max_inference_duration_ms']:.1f} ms"
    )
    print(
        f"Corpus speed: {summary['corpus_realtime_multiple']:.2f}x realtime "
        f"(RTF {summary['corpus_real_time_factor']:.4f})"
    )
    print(f"Model load: {summary['model_load_duration_ms']:.1f} ms")
    if "max_process_pss_kb_after_inference" in summary:
        print(f"Max post-inference PSS: {summary['max_process_pss_kb_after_inference']} KiB")
    if "max_thermal_status_after_inference" in summary:
        print(f"Max Android thermal status: {summary['max_thermal_status_after_inference']}")
    if "total_process_cpu_duration_ms" in summary:
        print(
            f"Process CPU: {summary['total_process_cpu_duration_ms'] / 1000:.1f} s total, "
            f"median {summary['median_process_cpu_duration_ms']:.1f} ms/inference, "
            f"{summary['median_average_process_cpu_cores']:.2f} average cores"
        )
    print(
        "Output instability across repeats: "
        f"{summary['unstable_case_count']} raw / "
        f"{summary['normalized_unstable_case_count']} normalized cases"
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
