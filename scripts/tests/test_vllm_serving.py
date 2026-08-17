from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts/training"
sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location(
    "serve_vllm_checkpoint", SCRIPT_DIR / "serve_vllm_checkpoint.py"
)
assert SPEC is not None and SPEC.loader is not None
serve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(serve)


class VllmServingConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.config = json.loads(
            (REPO_ROOT / "training/config/vllm-serving-v1.json").read_text(
                encoding="utf-8"
            )
        )

    def test_command_pins_throughput_and_lora_options(self) -> None:
        command = serve.vllm_command(self.config)
        rendered = " ".join(command)
        self.assertIn("--max-num-batched-tokens 16384", rendered)
        self.assertIn("--max-num-seqs 256", rendered)
        self.assertIn("--enable-prefix-caching", command)
        self.assertIn("--disable-log-requests", command)
        self.assertIn("--disable-uvicorn-access-log", command)
        self.assertIn("--enable-lora", command)
        self.assertIn("--max-lora-rank 16", rendered)
        self.assertNotIn("--reasoning-parser", command)
        self.assertNotIn("--default-chat-template-kwargs", command)
        self.assertNotIn("--language-model-only", command)

    def test_current_qwen3_model_is_pinned_and_text_only(self) -> None:
        self.assertEqual("0.8.5", self.config["vllm"]["package_version"])
        self.assertEqual("4.51.3", self.config["vllm"]["transformers_version"])
        self.assertEqual("cu124", self.config["vllm"]["torch_backend"])
        self.assertEqual("3.10", self.config["vllm"]["python"])
        self.assertEqual("Qwen/Qwen3-0.6B", self.config["model"]["model_id"])
        self.assertEqual(
            "61641f84fa567ab7b58e216b4930d2fe28bfd045",
            self.config["model"]["revision"],
        )
        self.assertFalse(self.config["server"]["enable_thinking"])
        self.assertEqual("vllm", self.config["server"]["generation_config"])


if __name__ == "__main__":
    unittest.main()
