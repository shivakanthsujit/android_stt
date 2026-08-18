#!/usr/bin/env python3
"""Summarize Pixel power-rail energy inside the STT benchmark trace marker."""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


TRACE_SECTION = "localflow_stt_benchmark"
TRACE_INFERENCE_SECTION = "localflow_stt_inference"


def query(trace_processor: Path, trace: Path, sql: str) -> list[dict[str, str]]:
    completed = subprocess.run(
        [str(trace_processor), "query", str(trace), sql],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = completed.stdout.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if line.startswith('"') and '","' in line
        ),
        None,
    )
    if header_index is None:
        raise ValueError("Trace processor did not emit a CSV result")
    return list(csv.DictReader(io.StringIO("\n".join(lines[header_index:]))))


def _safe_trace_name(value: str, option: str) -> str:
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for character in value):
        raise ValueError(f"{option} must be a non-empty trace-safe identifier")
    return value


def score(
    trace_processor: Path,
    trace: Path,
    trace_section: str = TRACE_SECTION,
    inference_section: str = TRACE_INFERENCE_SECTION,
) -> dict:
    trace_section = _safe_trace_name(trace_section, "trace section")
    inference_section = _safe_trace_name(inference_section, "inference section")
    rail_rows = query(
        trace_processor,
        trace,
        f"""
        INCLUDE PERFETTO MODULE android.power_rails;
        WITH benchmark AS (
          SELECT ts, ts + dur AS end_ts, dur
          FROM slice
          WHERE name = '{trace_section}' AND dur > 0
          ORDER BY dur DESC
          LIMIT 1
        )
        SELECT
          benchmark.dur AS benchmark_duration_ns,
          metadata.power_rail_name,
          metadata.raw_power_rail_name,
          metadata.subsystem_name,
          COUNT(*) AS sample_count,
          (MAX(counters.energy_since_boot) - MIN(counters.energy_since_boot)) / 1000000.0
            AS energy_joules
        FROM benchmark
        JOIN android_power_rails_counters AS counters
          ON counters.ts >= benchmark.ts AND counters.ts <= benchmark.end_ts
        JOIN android_power_rails_metadata AS metadata USING (track_id)
        GROUP BY metadata.track_id
        ORDER BY metadata.power_rail_name;
        """,
    )
    if not rail_rows:
        raise ValueError(f"Trace has no complete {trace_section} slice with power-rail samples")

    duration_ns = int(rail_rows[0]["benchmark_duration_ns"])
    if duration_ns <= 0:
        raise ValueError("Benchmark trace duration is not positive")
    duration_seconds = duration_ns / 1_000_000_000.0
    subsystems: dict[str, float] = defaultdict(float)
    rails = []
    for row in rail_rows:
        energy_joules = float(row["energy_joules"])
        subsystem = row["subsystem_name"]
        subsystems[subsystem] += energy_joules
        rails.append(
            {
                "power_rail_name": row["power_rail_name"],
                "raw_power_rail_name": row["raw_power_rail_name"],
                "subsystem_name": subsystem,
                "sample_count": int(row["sample_count"]),
                "energy_joules": energy_joules,
                "average_power_watts": energy_joules / duration_seconds,
            }
        )

    total_energy_joules = sum(row["energy_joules"] for row in rails)
    cpu_energy_joules = sum(
        energy for subsystem, energy in subsystems.items() if subsystem.startswith("CPU(")
    )
    gpu_energy_joules = subsystems.get("GPU", 0.0)
    memory_fabric_subsystems = {"DDR", "MIF", "INT", "SLC"}
    memory_fabric_energy_joules = sum(
        subsystems.get(subsystem, 0.0) for subsystem in memory_fabric_subsystems
    )
    compute_energy_joules = (
        cpu_energy_joules + gpu_energy_joules + memory_fabric_energy_joules
    )

    inference_rows = query(
        trace_processor,
        trace,
        f"""
        INCLUDE PERFETTO MODULE android.power_rails;
        WITH inference AS (
          SELECT ts, ts + dur AS end_ts, dur
          FROM slice
          WHERE name = '{inference_section}' AND dur > 0
        )
        SELECT
          (SELECT COUNT(*) FROM inference) AS inference_count,
          (SELECT SUM(dur) FROM inference) AS inference_duration_ns,
          metadata.power_rail_name,
          metadata.raw_power_rail_name,
          metadata.subsystem_name,
          COUNT(*) AS overlapping_sample_count,
          SUM(
            counters.energy_delta *
            (MIN(counters.ts + counters.dur, inference.end_ts) -
             MAX(counters.ts, inference.ts)) / counters.dur
          ) / 1000000.0 AS energy_joules
        FROM inference
        JOIN android_power_rails_counters AS counters
          ON counters.dur > 0
          AND counters.ts < inference.end_ts
          AND counters.ts + counters.dur > inference.ts
        JOIN android_power_rails_metadata AS metadata USING (track_id)
        GROUP BY metadata.track_id
        ORDER BY metadata.power_rail_name;
        """,
    )
    if not inference_rows:
        raise ValueError(f"Trace has no complete {inference_section} slices")
    inference_count = int(inference_rows[0]["inference_count"])
    inference_duration_seconds = int(inference_rows[0]["inference_duration_ns"]) / 1_000_000_000.0
    inference_subsystems: dict[str, float] = defaultdict(float)
    inference_rails = []
    for row in inference_rows:
        energy_joules = float(row["energy_joules"])
        subsystem = row["subsystem_name"]
        inference_subsystems[subsystem] += energy_joules
        inference_rails.append(
            {
                "power_rail_name": row["power_rail_name"],
                "raw_power_rail_name": row["raw_power_rail_name"],
                "subsystem_name": subsystem,
                "overlapping_sample_count": int(row["overlapping_sample_count"]),
                "energy_joules": energy_joules,
            }
        )
    inference_cpu_energy_joules = sum(
        energy
        for subsystem, energy in inference_subsystems.items()
        if subsystem.startswith("CPU(")
    )
    inference_gpu_energy_joules = inference_subsystems.get("GPU", 0.0)
    inference_memory_fabric_energy_joules = sum(
        inference_subsystems.get(subsystem, 0.0)
        for subsystem in memory_fabric_subsystems
    )
    inference_compute_energy_joules = (
        inference_cpu_energy_joules
        + inference_gpu_energy_joules
        + inference_memory_fabric_energy_joules
    )
    summary = {
        "schema_version": 1,
        "trace_section": trace_section,
        "inference_trace_section": inference_section,
        "benchmark_duration_seconds": duration_seconds,
        "cpu_energy_joules": cpu_energy_joules,
        "gpu_energy_joules": gpu_energy_joules,
        "memory_fabric_energy_joules": memory_fabric_energy_joules,
        "compute_energy_joules": compute_energy_joules,
        "total_measured_rail_energy_joules": total_energy_joules,
        "average_compute_power_watts": compute_energy_joules / duration_seconds,
        "average_total_measured_rail_power_watts": total_energy_joules / duration_seconds,
        "inference_count": inference_count,
        "inference_duration_seconds": inference_duration_seconds,
        "inference_cpu_energy_joules": inference_cpu_energy_joules,
        "inference_gpu_energy_joules": inference_gpu_energy_joules,
        "inference_memory_fabric_energy_joules": inference_memory_fabric_energy_joules,
        "inference_compute_energy_joules": inference_compute_energy_joules,
        "inference_average_compute_power_watts": (
            inference_compute_energy_joules / inference_duration_seconds
        ),
        "inference_subsystem_energy_joules": dict(sorted(inference_subsystems.items())),
        "inference_rails": inference_rails,
        "subsystem_energy_joules": dict(sorted(subsystems.items())),
        "rails": rails,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("--trace-processor", type=Path, required=True)
    parser.add_argument("--trace-section", default=TRACE_SECTION)
    parser.add_argument("--inference-section", default=TRACE_INFERENCE_SECTION)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    summary = score(
        args.trace_processor.resolve(),
        args.trace.resolve(),
        trace_section=args.trace_section,
        inference_section=args.inference_section,
    )
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"Power trace interval: {summary['benchmark_duration_seconds']:.3f} s")
    print(
        f"Measured inference slices: {summary['inference_count']} in "
        f"{summary['inference_duration_seconds']:.3f} s"
    )
    print(
        f"Inference compute rails: {summary['inference_compute_energy_joules']:.3f} J "
        f"({summary['inference_average_compute_power_watts']:.3f} W average)"
    )
    print(f"Inference CPU rails: {summary['inference_cpu_energy_joules']:.3f} J")
    print(f"Inference GPU rails: {summary['inference_gpu_energy_joules']:.6f} J")
    print(
        "Inference memory/fabric rails: "
        f"{summary['inference_memory_fabric_energy_joules']:.3f} J"
    )
    print(
        f"Compute rails: {summary['compute_energy_joules']:.3f} J "
        f"({summary['average_compute_power_watts']:.3f} W average)"
    )
    print(f"CPU rails: {summary['cpu_energy_joules']:.3f} J")
    print(f"GPU rails: {summary['gpu_energy_joules']:.6f} J")
    print(f"Memory/fabric rails: {summary['memory_fabric_energy_joules']:.3f} J")
    print(
        f"All measured rails: {summary['total_measured_rail_energy_joules']:.3f} J "
        f"({summary['average_total_measured_rail_power_watts']:.3f} W average)"
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
