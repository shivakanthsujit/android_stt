from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts/conversion"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("s1_mini_litert_common", SCRIPT_DIR / "s1_mini_litert_common.py")
assert SPEC is not None and SPEC.loader is not None
common = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = common
SPEC.loader.exec_module(common)
CONFIG_PATH = REPO_ROOT / "conversion/config/s1-mini-litertlm-block32-v1.json"
PYPROJECT_PATH = REPO_ROOT / "conversion/pyproject.toml"

INSPECT_SPEC = importlib.util.spec_from_file_location(
    "inspect_s1_mini_litertlm", SCRIPT_DIR / "inspect_s1_mini_litertlm.py"
)
assert INSPECT_SPEC is not None and INSPECT_SPEC.loader is not None
inspector = importlib.util.module_from_spec(INSPECT_SPEC)
sys.modules[INSPECT_SPEC.name] = inspector
INSPECT_SPEC.loader.exec_module(inspector)


class S1MiniLiteRtConversionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = common.load_config(CONFIG_PATH)

    def test_exact_conversion_contract_is_pinned(self) -> None:
        self.assertEqual(self.config["model"]["revision"], "65f84bcda1d13df582c4a8443c1c5aa53c0c66db")
        self.assertEqual(self.config["contract"]["cache_length"], 4096)
        self.assertEqual(self.config["quantization"]["recipe_name"], "dynamic_wi4b32_afp32")
        self.assertEqual(self.config["quantization"]["block_size"], 32)
        self.assertEqual(self.config["quantization"]["weight_bits"], 4)
        self.assertEqual(self.config["quantization"]["activation_dtype"], "FLOAT32")
        self.assertEqual(self.config["quantization"]["kv_dtype"], "FLOAT32")

        project = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(project["project"]["requires-python"], "==3.11.*")
        self.assertIn("backports-strenum==1.2.8", project["project"]["dependencies"])

    def test_channelwise_or_lower_bit_config_fails(self) -> None:
        for key, value in (("recipe_name", "dynamic_wi4_afp32"), ("granularity", "CHANNELWISE"), ("weight_bits", 3)):
            changed = json.loads(json.dumps(self.config))
            changed["quantization"][key] = value
            with self.subTest(key=key), self.assertRaises(common.ConversionError):
                common.validate_config(changed)

    def test_generated_recipe_requires_block32_int4_without_activation_config(self) -> None:
        valid = [{
            "regex": ".*",
            "operation": "*",
            "algorithm_key": "min_max_uniform_quantize",
            "op_config": {
                "weight_tensor_config": {
                    "num_bits": 4,
                    "symmetric": True,
                    "granularity": "BLOCKWISE_32",
                    "dtype": "INT",
                },
                "compute_precision": "INTEGER",
                "explicit_dequantize": False,
                "skip_checks": False,
                "min_weight_elements": 0,
            },
        }]
        self.assertEqual(common.validate_generated_recipe(valid, self.config), valid)
        for mutator in (
            lambda value: value[0]["op_config"]["weight_tensor_config"].update(granularity="CHANNELWISE"),
            lambda value: value[0]["op_config"]["weight_tensor_config"].update(num_bits=2),
            lambda value: value[0]["op_config"].update(activation_tensor_config={}),
        ):
            changed = json.loads(json.dumps(valid))
            mutator(changed)
            with self.assertRaises(common.ConversionError):
                common.validate_generated_recipe(changed, self.config)

    def test_source_membership_and_hashes_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            small_config = json.loads(json.dumps(self.config))
            payload = b"exact"
            small_config["model"]["source_files"] = {
                "model.safetensors": {"bytes": len(payload), "sha256": __import__("hashlib").sha256(payload).hexdigest()},
                "config.json": {"bytes": 62, "sha256": "0" * 64},
            }
            (source / "model.safetensors").write_bytes(payload)
            (source / "extra.txt").write_text("unexpected", encoding="utf-8")
            with self.assertRaisesRegex(common.ConversionError, "membership mismatch"):
                common.verify_source_snapshot(source, small_config)

    def test_eval_and_gguf_sources_are_rejected_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for path in (base / "docs/evaluation/source", base / "model.gguf"):
                path.mkdir(parents=True)
                with self.subTest(path=path), self.assertRaises(common.ConversionError):
                    common.verify_source_snapshot(path, self.config)

    def test_artifact_metadata_rejects_channelwise_and_wrong_block_size(self) -> None:
        class TensorType:
            FLOAT32 = 0
            FLOAT16 = 1
            INT4 = 17

        class BlockwiseQuantizationT:
            def __init__(self, block_size: int = 32, scales: int = 1) -> None:
                self.blockSize = block_size
                self.scales = scales

        class Schema:
            pass

        Schema.TensorType = TensorType
        Schema.BlockwiseQuantizationT = BlockwiseQuantizationT

        class Value:
            def __init__(self, tensor_type: int, details: object | None = None) -> None:
                self.type = tensor_type
                self.quantization = type("Quantization", (), {"details": details})() if details else None

        def model(details: object) -> object:
            tensors = [Value(TensorType.INT4, details), Value(TensorType.FLOAT16)]
            subgraph = type("Subgraph", (), {"tensors": tensors})()
            return type("Model", (), {"subgraphs": [subgraph], "signatureDefs": []})()

        report = inspector.inspect_model(model(BlockwiseQuantizationT()), Schema, 0)
        self.assertEqual(report["block32_tensors"], 1)
        for details in (object(), BlockwiseQuantizationT(block_size=128)):
            with self.assertRaises(common.ConversionError):
                inspector.inspect_model(model(details), Schema, 0)


if __name__ == "__main__":
    unittest.main()
