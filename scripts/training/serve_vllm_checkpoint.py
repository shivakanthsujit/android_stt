#!/usr/bin/env python3
"""Serve the pinned Qwen3 base and completed cleanup LoRA through vLLM."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from check_vllm_environment import load_config, verify_artifacts


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "training/config/vllm-serving-v1.json"


def vllm_command(config: dict[str, Any]) -> list[str]:
    vllm = config["vllm"]
    model = config["model"]
    adapter = config["adapter"]
    server = config["server"]
    executable = Path(vllm["environment_path"]) / "bin/vllm"
    lora_module = json.dumps(
        {
            "name": adapter["served_name"],
            "path": adapter["path"],
            "base_model_name": model["model_id"],
        },
        separators=(",", ":"),
    )
    command = [
        str(executable),
        "serve",
        model["snapshot_path"],
        "--served-model-name",
        model["served_base_name"],
        "--host",
        server["host"],
        "--port",
        str(server["port"]),
        "--dtype",
        server["dtype"],
        "--gpu-memory-utilization",
        str(server["gpu_memory_utilization"]),
        "--max-model-len",
        str(server["max_model_len"]),
        "--max-num-seqs",
        str(server["max_num_seqs"]),
        "--max-num-batched-tokens",
        str(server["max_num_batched_tokens"]),
        "--generation-config",
        server["generation_config"],
        "--enable-lora",
        "--max-lora-rank",
        str(adapter["rank"]),
        "--max-loras",
        "1",
        "--max-cpu-loras",
        "1",
        "--lora-modules",
        lora_module,
    ]
    if server["enable_prefix_caching"]:
        command.append("--enable-prefix-caching")
    if server["disable_request_logging"]:
        command.append("--disable-log-requests")
    if server["disable_access_logging"]:
        command.append("--disable-uvicorn-access-log")
    return command


def compute_processes() -> list[str]:
    result = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_memory",
            "--format=csv,noheader,nounits",
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(f"nvidia-smi preflight failed: {result.stderr.strip()}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--print-command", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "--allow-other-compute-processes",
        action="store_true",
        help="explicitly allow serving while another CUDA compute process is active",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    verify_artifacts(config)
    command = vllm_command(config)
    executable = Path(command[0])
    if not args.print_command and not executable.is_file():
        raise RuntimeError(
            f"vLLM environment is missing: {executable}; run setup_vllm_env.sh"
        )
    if args.print_command:
        print(shlex.join(command))
        return 0
    if args.check_only:
        print("Pinned vLLM, model, and adapter paths/hashes pass.")
        return 0
    active = compute_processes()
    if active and not args.allow_other_compute_processes:
        raise RuntimeError(
            "refusing to start while CUDA compute processes are active: "
            + "; ".join(active)
        )

    artifact_root = Path(config["vllm"]["artifact_root"])
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HOME": str(artifact_root / "cache/huggingface"),
            "HF_HUB_CACHE": str(artifact_root / "cache/huggingface/hub"),
            "UV_CACHE_DIR": str(artifact_root / "cache/uv"),
            "PYTHONUNBUFFERED": "1",
            "VLLM_ALLOW_RUNTIME_LORA_UPDATING": "False",
        }
    )
    print(shlex.join(command), file=sys.stderr, flush=True)
    os.execve(command[0], command, environment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
