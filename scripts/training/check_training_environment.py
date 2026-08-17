#!/usr/bin/env python3
"""Fail-closed CUDA/package check and sanitized environment report."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


EXPECTED = {
    "accelerate": "1.14.0",
    "datasets": "5.0.0",
    "huggingface-hub": "1.24.0",
    "peft": "0.19.1",
    "pyarrow": "25.0.0",
    "safetensors": "0.8.0",
    "torch": "2.6.0+cu124",
    "torchvision": "0.21.0+cu124",
    "transformers": "5.14.1",
}


def installed_distribution_inventory() -> list[str]:
    """Return a pip-free, path-free inventory for uv environments without pip."""

    rows = set()
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if name:
            rows.add(f"{name}=={distribution.version}")
    return sorted(rows, key=str.casefold)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.report.exists():
        raise RuntimeError(f"refusing to overwrite environment report: {args.report}")
    actual = {name: importlib.metadata.version(name) for name in EXPECTED}
    if actual != EXPECTED:
        raise RuntimeError(f"package versions differ from pin set: {actual}")
    import torch
    if torch.__version__ != EXPECTED["torch"]:
        raise RuntimeError(f"unexpected torch build: {torch.__version__}")
    if torch.version.cuda != "12.4":
        raise RuntimeError(f"expected PyTorch CUDA 12.4 build, found {torch.version.cuda}")
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("expected exactly one visible CUDA GPU")
    properties = torch.cuda.get_device_properties(0)
    if "RTX A6000" not in properties.name:
        raise RuntimeError(f"unexpected GPU: {properties.name}")
    if properties.total_memory < 47 * 1024**3:
        raise RuntimeError(f"unexpectedly low GPU memory: {properties.total_memory}")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("RTX environment does not report bfloat16 support")
    allocation = torch.ones((1024, 1024), device="cuda", dtype=torch.bfloat16)
    result = (allocation @ allocation).float().mean().item()
    del allocation
    torch.cuda.synchronize()
    if result != result:
        raise RuntimeError("CUDA smoke computation produced NaN")
    nvidia = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,uuid,driver_version,memory.total", "--format=csv,noheader,nounits"],
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    freeze = installed_distribution_inventory()
    report = {
        "report_version": "cleanup-training-environment-report-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": actual,
        "torch_build": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cudnn": torch.backends.cudnn.version(),
        "nvidia_smi": nvidia,
        "gpu_compute_capability": list(torch.cuda.get_device_capability(0)),
        "bf16_supported": torch.cuda.is_bf16_supported(),
        "package_inventory": freeze,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("python", "torch_build", "torch_cuda", "nvidia_smi")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
