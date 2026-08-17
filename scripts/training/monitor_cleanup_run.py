#!/usr/bin/env python3
"""Read-only monitor for one managed cleanup training run."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL = frozenset({"complete", "failed", "paused_for_resume_smoke"})


def command(args: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(args, text=True, capture_output=True)
    except OSError as exc:
        return {"returncode": 127, "stdout": [], "stderr": str(exc)}
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip().splitlines(),
        "stderr": result.stderr.strip(),
    }


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def file_state(path: Path, previous_size: int | None) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "bytes": 0, "new_bytes": 0, "modified_at": None}
    stat = path.stat()
    return {
        "present": True,
        "bytes": stat.st_size,
        "new_bytes": max(0, stat.st_size - previous_size) if previous_size is not None else stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def last_jsonl(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    last = ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.strip():
                last = line
    try:
        value = json.loads(last)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return {"malformed_last_line": True}


def checkpoint_state(run_dir: Path) -> list[dict[str, Any]]:
    checkpoints: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("checkpoint-*"), key=lambda item: int(item.name.split("-")[-1]) if item.name.split("-")[-1].isdigit() else -1):
        if not path.is_dir():
            continue
        state_path = path / "trainer_state.json"
        stat = path.stat()
        checkpoints.append({
            "name": path.name,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "trainer_state_present": state_path.is_file(),
            "trainer_global_step": (read_json(state_path) or {}).get("global_step"),
        })
    return checkpoints


def process_state(run_dir: Path) -> list[str]:
    result = command(["ps", "-eo", "pid=,ppid=,lstart=,etime=,stat=,%cpu=,%mem=,args="])
    if result["returncode"] != 0:
        return []
    needle = str(run_dir.resolve())
    return [line for line in result["stdout"] if needle in line and "monitor_cleanup_run.py" not in line]


def snapshot(run_dir: Path, session: str | None, previous: dict[str, int]) -> tuple[dict[str, Any], dict[str, int]]:
    metrics_path = run_dir / "metrics.jsonl"
    console_path = run_dir / "console.log"
    telemetry_path = run_dir / "gpu-telemetry.jsonl"
    files = {
        "metrics": file_state(metrics_path, previous.get("metrics")),
        "console": file_state(console_path, previous.get("console")),
        "gpu_telemetry": file_state(telemetry_path, previous.get("gpu_telemetry")),
    }
    next_previous = {name: value["bytes"] for name, value in files.items()}
    disk = shutil.disk_usage(run_dir if run_dir.exists() else run_dir.parent)
    tmux = command(["tmux", "has-session", "-t", session]) if session else None
    event = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "run_dir": str(run_dir.resolve()),
        "status": read_json(run_dir / "status.json"),
        "resolved_config_present": (run_dir / "resolved-config.json").is_file(),
        "repository": read_json(run_dir / "repository.json"),
        "session": {"name": session, "alive": tmux["returncode"] == 0} if tmux else None,
        "matching_processes": process_state(run_dir),
        "files": files,
        "latest_metric": last_jsonl(metrics_path),
        "latest_gpu_telemetry": last_jsonl(telemetry_path),
        "checkpoints": checkpoint_state(run_dir),
        "live_gpu": command([
            "nvidia-smi",
            "--query-gpu=timestamp,index,uuid,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit",
            "--format=csv,noheader,nounits",
        ]),
        "disk": {"total_bytes": disk.total, "used_bytes": disk.used, "free_bytes": disk.free},
        "recovery_action_taken": False,
    }
    return event, next_previous


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--session", help="tmux session name to verify")
    parser.add_argument("--output", type=Path, help="JSONL monitor log; defaults to RUN_DIR/monitor.jsonl")
    parser.add_argument("--interval-seconds", type=int, default=180)
    parser.add_argument("--follow", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval_seconds < 60:
        raise RuntimeError("monitor interval must be at least 60 seconds")
    output = args.output or args.run_dir / "monitor.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    previous: dict[str, int] = {}
    while True:
        event, previous = snapshot(args.run_dir, args.session, previous)
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
            handle.flush()
        print(json.dumps(event, sort_keys=True), flush=True)
        status = (event.get("status") or {}).get("status")
        if not args.follow or status in TERMINAL:
            return 0 if status != "failed" else 1
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
