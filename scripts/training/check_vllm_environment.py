#!/usr/bin/env python3
"""Fail-closed vLLM source, package, CUDA, model, and adapter preflight."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("config_version") != "cleanup-vllm-serving-v1":
        raise RuntimeError("unsupported vLLM serving config version")
    return value


def git_output(source: Path, *arguments: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(source), *arguments], text=True
    ).strip()


def verify_artifacts(config: dict[str, Any]) -> dict[str, Any]:
    model = config["model"]
    adapter = config["adapter"]
    snapshot = Path(model["snapshot_path"])
    adapter_path = Path(adapter["path"])
    run_path = Path(adapter["run_path"])
    for required in (
        snapshot / "config.json",
        snapshot / "model.safetensors",
        snapshot / "tokenizer_config.json",
        adapter_path / "adapter_model.safetensors",
        adapter_path / "adapter_config.json",
        run_path / "resolved-config.json",
        run_path / "status.json",
    ):
        if not required.is_file():
            raise RuntimeError(f"required artifact is missing: {required}")
    status = json.loads((run_path / "status.json").read_text(encoding="utf-8"))
    if status.get("status") != "complete":
        raise RuntimeError("configured adapter run is not complete")
    resolved = json.loads(
        (run_path / "resolved-config.json").read_text(encoding="utf-8")
    )
    resolved_model = resolved["model"]
    if (
        resolved_model.get("model_id") != model["model_id"]
        or resolved_model.get("revision") != model["revision"]
    ):
        raise RuntimeError("adapter run base model does not match serving config")
    if resolved["common"].get("lora_rank") != adapter["rank"]:
        raise RuntimeError("adapter run rank does not match serving config")
    model_hash = sha256_file(adapter_path / "adapter_model.safetensors")
    config_hash = sha256_file(adapter_path / "adapter_config.json")
    if model_hash != adapter["adapter_model_sha256"]:
        raise RuntimeError("adapter model SHA-256 mismatch")
    if config_hash != adapter["adapter_config_sha256"]:
        raise RuntimeError("adapter config SHA-256 mismatch")
    return {
        "model_snapshot": str(snapshot.resolve()),
        "model_revision": model["revision"],
        "adapter_path": str(adapter_path.resolve()),
        "adapter_model_sha256": model_hash,
        "adapter_config_sha256": config_hash,
        "training_status": status["status"],
        "training_global_step": status.get("global_step"),
    }


def distribution_inventory() -> list[dict[str, str]]:
    inventory = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name") or "unknown"
        inventory.append({"name": name, "version": distribution.version})
    return sorted(inventory, key=lambda item: item["name"].casefold())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--artifacts-only",
        action="store_true",
        help="verify config/source/model/adapter without importing vLLM or CUDA",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    source = Path(config["vllm"]["source_path"])
    if not (source / ".git").is_dir():
        raise RuntimeError(f"vLLM source checkout is missing: {source}")
    revision = git_output(source, "rev-parse", "HEAD")
    if revision != config["vllm"]["revision"]:
        raise RuntimeError(f"vLLM source revision {revision} does not match config")
    if git_output(source, "status", "--short"):
        raise RuntimeError("vLLM source checkout is dirty")

    report: dict[str, Any] = {
        "schema_version": "cleanup-vllm-environment-report-v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": sha256_file(args.config),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "vllm_source_path": str(source.resolve()),
        "vllm_source_revision": revision,
        "artifacts": verify_artifacts(config),
    }
    if not args.artifacts_only:
        import torch
        import transformers
        import vllm

        module_path = Path(vllm.__file__).resolve()
        if vllm.__version__ != config["vllm"]["package_version"]:
            raise RuntimeError(
                f"vLLM package {vllm.__version__} does not match configured version"
            )
        if transformers.__version__ != config["vllm"]["transformers_version"]:
            raise RuntimeError(
                f"Transformers {transformers.__version__} does not match configured version"
            )
        if not torch.cuda.is_available():
            raise RuntimeError("PyTorch cannot access CUDA")
        if not torch.cuda.is_bf16_supported():
            raise RuntimeError("configured BF16 serving requires BF16 CUDA support")
        properties = torch.cuda.get_device_properties(0)
        report.update(
            {
                "vllm_version": vllm.__version__,
                "vllm_module_path": str(module_path),
                "torch_version": torch.__version__,
                "torch_cuda_version": torch.version.cuda,
                "transformers_version": transformers.__version__,
                "cuda_devices": torch.cuda.device_count(),
                "device_0": {
                    "name": properties.name,
                    "total_memory_bytes": properties.total_memory,
                    "compute_capability": [properties.major, properties.minor],
                },
                "distributions": distribution_inventory(),
            }
        )
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
