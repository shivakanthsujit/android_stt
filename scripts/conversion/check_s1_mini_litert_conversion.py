#!/usr/bin/env python3
"""Verify the exact S1 source and optionally materialize the installed recipe."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
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
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--recipe-output", type=Path)
    parser.add_argument("--check-installed-tools", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.report.exists() or (args.recipe_output and args.recipe_output.exists()):
        raise ConversionError("refusing to overwrite an existing report or recipe")
    config = load_config(args.config)
    source_files = verify_source_snapshot(args.source_dir, config)
    report: dict[str, object] = {
        "schema_version": "s1-mini-litert-preflight-v1",
        "config_sha256": sha256_file(args.config),
        "source_revision": config["model"]["revision"],
        "source_files": source_files,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "installed_tools_checked": args.check_installed_tools,
    }
    if args.check_installed_tools:
        if sys.platform != "linux" or platform.machine() != "x86_64":
            raise ConversionError("the evidence-bearing conversion host must be Linux x86_64")
        if sys.version_info[:2] != (3, 11):
            raise ConversionError("the conversion environment must use Python 3.11")
        expected_versions = {
            "litert-torch": config["tools"]["litert_torch_version"],
            "ai-edge-quantizer": config["tools"]["ai_edge_quantizer_version"],
        }
        installed = {name: importlib.metadata.version(name) for name in expected_versions}
        if installed != expected_versions:
            raise ConversionError(f"conversion package drift: {installed}")
        from ai_edge_quantizer import recipe as recipe_lib

        generated = validate_generated_recipe(recipe_lib.dynamic_wi4b32_afp32(), config)
        report["installed_packages"] = installed
        report["recipe"] = generated
        if args.recipe_output is None:
            raise ConversionError("--recipe-output is required with --check-installed-tools")
        args.recipe_output.parent.mkdir(parents=True, exist_ok=True)
        args.recipe_output.write_text(json.dumps(generated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report["recipe_sha256"] = sha256_file(args.recipe_output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
