#!/usr/bin/env python3
"""Run the pinned, Linux-only S1-mini LiteRT-LM export."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from s1_mini_litert_common import (
    ConversionError,
    load_config,
    sha256_file,
    validate_generated_recipe,
    verify_source_snapshot,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    if sys.platform != "linux" or platform.machine() != "x86_64" or sys.version_info[:2] != (3, 11):
        raise ConversionError("full conversion requires Linux x86_64 with Python 3.11")
    if args.output_dir.exists():
        raise ConversionError(f"refusing to overwrite conversion output: {args.output_dir}")
    config = load_config(args.config)
    source_files = verify_source_snapshot(args.source_dir, config)
    expected_packages = {
        "litert-torch": config["tools"]["litert_torch_version"],
        "ai-edge-quantizer": config["tools"]["ai_edge_quantizer_version"],
    }
    installed = {name: importlib.metadata.version(name) for name in expected_packages}
    if installed != expected_packages:
        raise ConversionError(f"conversion package drift: {installed}")

    from ai_edge_quantizer import recipe as recipe_lib
    from litert_torch.generative.export_hf import export as litert_export

    recipe = validate_generated_recipe(recipe_lib.dynamic_wi4b32_afp32(), config)
    args.output_dir.mkdir(parents=True)
    status_path = args.output_dir / "conversion-status.json"
    recipe_path = args.output_dir / "resolved-recipe.json"
    write_json(recipe_path, recipe)
    base_status: dict[str, object] = {
        "schema_version": "s1-mini-litert-export-status-v1",
        "state": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config_sha256": sha256_file(args.config),
        "recipe_sha256": sha256_file(recipe_path),
        "source_revision": config["model"]["revision"],
        "source_files": source_files,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "installed_packages": installed,
        "export": {
            "cache_length": config["contract"]["cache_length"],
            "prefill_lengths": config["contract"]["prefill_lengths"],
            "quantization_recipe": config["quantization"]["recipe_name"],
            "keep_temporary_files": True,
            "externalize_embedder": True,
            "bundle_litert_lm": True,
        },
    }
    write_json(status_path, base_status)
    try:
        litert_export.export(
            model=str(args.source_dir.resolve()),
            output_dir=str(args.output_dir.resolve()),
            keep_temporary_files=True,
            prefill_lengths=config["contract"]["prefill_lengths"],
            cache_length=config["contract"]["cache_length"],
            quantization_recipe=config["quantization"]["recipe_name"],
            externalize_embedder=True,
            bundle_litert_lm=True,
        )
        artifacts = sorted(args.output_dir.glob("*.litertlm"))
        if len(artifacts) != 1:
            raise ConversionError(f"expected one .litertlm artifact, found {len(artifacts)}")
        base_status.update({
            "state": "exported_unverified",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "artifact": {
                "path": artifacts[0].name,
                "bytes": artifacts[0].stat().st_size,
                "sha256": sha256_file(artifacts[0]),
            },
        })
        write_json(status_path, base_status)
        return 0
    except BaseException as error:
        base_status.update({
            "state": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
        })
        write_json(status_path, base_status)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
