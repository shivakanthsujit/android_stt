#!/usr/bin/env python3
"""Fail-closed helpers for the S1-mini LiteRT-LM conversion."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


HEX64 = re.compile(r"[0-9a-f]{64}")
SCHEMA_VERSION = "s1-mini-litert-conversion-v1"


class ConversionError(RuntimeError):
    """The conversion inputs do not match the pinned contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConversionError(f"cannot read conversion config: {path}") from exc
    validate_config(config)
    return config


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != SCHEMA_VERSION:
        raise ConversionError("unsupported conversion config schema")
    model = config.get("model")
    contract = config.get("contract")
    quantization = config.get("quantization")
    tools = config.get("tools")
    if not all(isinstance(value, dict) for value in (model, contract, quantization, tools)):
        raise ConversionError("conversion config sections must be objects")
    if model["revision"] != "65f84bcda1d13df582c4a8443c1c5aa53c0c66db":
        raise ConversionError("S1-mini source revision drift")
    if model["architecture"] != "Qwen3ForCausalLM" or model["model_type"] != "qwen3":
        raise ConversionError("S1-mini architecture drift")
    files = model.get("source_files")
    if not isinstance(files, dict) or "model.safetensors" not in files:
        raise ConversionError("source file manifest is incomplete")
    for name, identity in files.items():
        if Path(name).name != name or not isinstance(identity, dict):
            raise ConversionError(f"unsafe source manifest path: {name!r}")
        if not isinstance(identity.get("bytes"), int) or identity["bytes"] <= 0:
            raise ConversionError(f"invalid byte count for {name}")
        if not HEX64.fullmatch(str(identity.get("sha256", ""))):
            raise ConversionError(f"invalid SHA-256 for {name}")
    if contract.get("cache_length") != 4096:
        raise ConversionError("the first LiteRT artifact must use context 4096")
    if contract.get("prefill_lengths") != [128, 256, 512, 1024, 1152]:
        raise ConversionError("prefill signatures drifted")
    if contract.get("stop_token_ids") != [151645, 151643]:
        raise ConversionError("stop-token contract drifted")
    expected_quantization = {
        "recipe_name": "dynamic_wi4b32_afp32",
        "weight_bits": 4,
        "weight_dtype": "INT",
        "granularity": "BLOCKWISE_32",
        "block_size": 32,
        "activation_dtype": "FLOAT32",
        "kv_dtype": "FLOAT32",
        "compute_precision": "INTEGER",
        "explicit_dequantize": False,
        "calibration": "none",
    }
    for key, expected in expected_quantization.items():
        if quantization.get(key) != expected:
            raise ConversionError(f"unsafe quantization setting: {key}")
    forbidden = quantization.get("forbidden_recipe_names")
    if not isinstance(forbidden, list) or "dynamic_wi4_afp32" not in forbidden:
        raise ConversionError("channelwise recipe must be explicitly forbidden")
    if tools.get("python") != "3.11" or tools.get("litert_torch_version") != "0.9.3":
        raise ConversionError("conversion tool pin drift")
    if tools.get("ai_edge_quantizer_version") != "0.8.0":
        raise ConversionError("quantizer pin must match litert-torch 0.9.3 dependency metadata")


def verify_source_snapshot(source_dir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    source_dir = source_dir.resolve()
    if not source_dir.is_dir() or source_dir.is_symlink():
        raise ConversionError(f"source directory is invalid: {source_dir}")
    lowered = str(source_dir).lower()
    if lowered.endswith(".gguf") or "/docs/evaluation" in lowered:
        raise ConversionError("GGUF and evaluation paths are forbidden conversion sources")
    expected = config["model"]["source_files"]
    actual_files = {path.name for path in source_dir.iterdir() if path.is_file()}
    if actual_files != set(expected):
        missing = sorted(set(expected) - actual_files)
        extra = sorted(actual_files - set(expected))
        raise ConversionError(f"source file membership mismatch: missing={missing}, extra={extra}")
    identities: list[dict[str, Any]] = []
    for name in sorted(expected):
        path = source_dir / name
        if path.is_symlink() or not path.is_file():
            raise ConversionError(f"source is not a regular file: {name}")
        identity = expected[name]
        actual_size = path.stat().st_size
        actual_hash = sha256_file(path)
        if actual_size != identity["bytes"] or actual_hash != identity["sha256"]:
            raise ConversionError(f"source identity mismatch: {name}")
        identities.append({"path": name, "bytes": actual_size, "sha256": actual_hash})
    model_config = json.loads((source_dir / "config.json").read_text(encoding="utf-8"))
    if model_config.get("architectures") != [config["model"]["architecture"]]:
        raise ConversionError("source architecture metadata mismatch")
    if model_config.get("model_type") != config["model"]["model_type"]:
        raise ConversionError("source model_type metadata mismatch")
    generation = json.loads((source_dir / "generation_config.json").read_text(encoding="utf-8"))
    if generation.get("eos_token_id") != config["contract"]["stop_token_ids"]:
        raise ConversionError("source stop-token metadata mismatch")
    tokenizer = json.loads((source_dir / "tokenizer_config.json").read_text(encoding="utf-8"))
    if tokenizer.get("chat_template") != (source_dir / "chat_template.jinja").read_text(encoding="utf-8"):
        raise ConversionError("tokenizer and standalone chat templates differ")
    return identities


def normalize_recipe_value(value: Any) -> Any:
    if hasattr(value, "value"):
        return normalize_recipe_value(value.value)
    if isinstance(value, dict):
        return {str(key): normalize_recipe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_recipe_value(item) for item in value]
    return value


def validate_generated_recipe(recipe: Any, config: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = normalize_recipe_value(recipe)
    if not isinstance(normalized, list) or len(normalized) != 1 or not isinstance(normalized[0], dict):
        raise ConversionError("block-32 recipe must contain exactly one rule")
    rule = normalized[0]
    op_config = rule.get("op_config")
    weight = op_config.get("weight_tensor_config") if isinstance(op_config, dict) else None
    if rule.get("regex") != ".*" or rule.get("operation") != "*":
        raise ConversionError("block-32 recipe scope drifted")
    if rule.get("algorithm_key") != "min_max_uniform_quantize":
        raise ConversionError("block-32 quantization algorithm drifted")
    if not isinstance(weight, dict):
        raise ConversionError("block-32 recipe lacks a weight configuration")
    checks = {
        "num_bits": config["quantization"]["weight_bits"],
        "symmetric": True,
        "granularity": config["quantization"]["granularity"],
        "dtype": config["quantization"]["weight_dtype"],
    }
    for key, expected in checks.items():
        if weight.get(key) != expected:
            raise ConversionError(f"generated recipe is not approved block-32 INT4: {key}")
    if op_config.get("compute_precision") != "INTEGER" or op_config.get("explicit_dequantize") is not False:
        raise ConversionError("generated recipe compute contract drifted")
    if "activation_tensor_config" in op_config:
        raise ConversionError("generated recipe unexpectedly quantizes activations")
    return normalized
