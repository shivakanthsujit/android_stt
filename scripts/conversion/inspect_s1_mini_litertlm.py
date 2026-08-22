#!/usr/bin/env python3
"""Prove block-32 INT4 metadata in every TFLite section of a LiteRT-LM bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from s1_mini_litert_common import ConversionError, load_config, sha256_file


def inspect_model(model: Any, schema: Any, section_id: int) -> dict[str, Any]:
    int4_tensors = 0
    block32_tensors = 0
    scale_types: dict[str, int] = {}
    signature_tensors: list[dict[str, Any]] = []
    for subgraph_index, subgraph in enumerate(model.subgraphs or []):
        tensors = subgraph.tensors or []
        for tensor_index, tensor in enumerate(tensors):
            if tensor.type != schema.TensorType.INT4:
                continue
            int4_tensors += 1
            quantization = tensor.quantization
            details = quantization.details if quantization is not None else None
            if not isinstance(details, schema.BlockwiseQuantizationT):
                raise ConversionError(
                    f"section {section_id} subgraph {subgraph_index} tensor {tensor_index}: "
                    "INT4 tensor lacks blockwise metadata"
                )
            if details.blockSize != 32:
                raise ConversionError(
                    f"section {section_id} subgraph {subgraph_index} tensor {tensor_index}: "
                    f"block size is {details.blockSize}, expected 32"
                )
            if details.scales < 0 or details.scales >= len(tensors):
                raise ConversionError("blockwise scale tensor index is invalid")
            scale_tensor = tensors[details.scales]
            if scale_tensor.type not in (schema.TensorType.FLOAT16, schema.TensorType.FLOAT32):
                raise ConversionError("blockwise scale tensor is not floating point")
            scale_name = "FLOAT16" if scale_tensor.type == schema.TensorType.FLOAT16 else "FLOAT32"
            scale_types[scale_name] = scale_types.get(scale_name, 0) + 1
            block32_tensors += 1
    for signature in model.signatureDefs or []:
        if signature.subgraphIndex >= len(model.subgraphs or []):
            raise ConversionError("signature references an invalid subgraph")
        tensors = model.subgraphs[signature.subgraphIndex].tensors or []
        for direction, mappings in (("input", signature.inputs), ("output", signature.outputs)):
            for mapping in mappings or []:
                if mapping.tensorIndex >= len(tensors):
                    raise ConversionError("signature references an invalid tensor")
                tensor = tensors[mapping.tensorIndex]
                name = mapping.name.decode() if isinstance(mapping.name, bytes) else str(mapping.name)
                if any(fragment in name.lower() for fragment in ("kv", "cache")):
                    if tensor.type != schema.TensorType.FLOAT32:
                        raise ConversionError(f"KV signature tensor is not FLOAT32: {name}")
                signature_tensors.append({
                    "signature": signature.signatureKey.decode() if isinstance(signature.signatureKey, bytes) else str(signature.signatureKey),
                    "direction": direction,
                    "name": name,
                    "tensor_type": int(tensor.type),
                })
    if int4_tensors == 0 or block32_tensors != int4_tensors:
        raise ConversionError(f"section {section_id} has no proven block-32 INT4 tensors")
    return {
        "section_id": section_id,
        "int4_tensors": int4_tensors,
        "block32_tensors": block32_tensors,
        "scale_tensor_types": scale_types,
        "signature_tensors": signature_tensors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise ConversionError(f"refusing to overwrite inspection report: {args.report}")
    config = load_config(args.config)
    if not args.artifact.is_file() or args.artifact.suffix != ".litertlm":
        raise ConversionError("artifact must be an existing .litertlm file")

    from ai_edge_litert import schema_py_generated as schema
    from ai_edge_quantizer.utils.litertlm_utils import LiteRTLMFile

    bundle = LiteRTLMFile(args.artifact)
    sections: list[dict[str, Any]] = []
    tflite_sections = 0
    for section_id in range(len(bundle.sections)):
        model = bundle.read_model(section_id)
        if model is None:
            continue
        tflite_sections += 1
        sections.append(inspect_model(model, schema, section_id))
    if tflite_sections == 0:
        raise ConversionError("LiteRT-LM bundle contains no TFLite sections")
    report = {
        "schema_version": "s1-mini-litert-artifact-inspection-v1",
        "config_sha256": sha256_file(args.config),
        "artifact": {
            "bytes": args.artifact.stat().st_size,
            "sha256": sha256_file(args.artifact),
        },
        "required_quantization": config["quantization"],
        "tflite_sections": tflite_sections,
        "sections": sections,
        "verdict": "pass",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ConversionError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error
