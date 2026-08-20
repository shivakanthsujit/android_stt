from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "benchmark-s1-mini.py"
SPEC = importlib.util.spec_from_file_location("benchmark_s1_mini", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bench = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bench
SPEC.loader.exec_module(bench)


class BenchmarkS1MiniTest(unittest.TestCase):
    def test_publisher_prompt_and_control_line_are_pinned(self) -> None:
        prompt = bench.SYSTEM_PROMPT_PATH.read_text(encoding="utf-8").strip()
        self.assertEqual(
            "6ecb6800f96b00cf612631552eff606a829feb2be8449fa95f9f150713b89327",
            hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            "[Styling: semi-formal] [Structure: prose] [Context: general]",
            bench.CONTROL_LINE,
        )

    def test_output_cap_matches_publisher_formula(self) -> None:
        self.assertEqual(34, bench.max_new_tokens(1))
        self.assertEqual(45, bench.max_new_tokens(10))
        self.assertEqual(162, bench.max_new_tokens(100))

    def test_server_command_uses_exact_no_thinking_and_greedy_flags(self) -> None:
        command = bench.server_command(
            Path("/bin/llama-server"), Path("/models/s1.gguf"), "s1", 18081
        )
        self.assertIn("--jinja", command)
        self.assertIn("--chat-template-kwargs", command)
        self.assertIn('{"enable_thinking":false}', command)
        self.assertEqual("0", command[command.index("--temp") + 1])
        self.assertNotIn("--reasoning-budget", command)

    def test_case_loader_uses_raw_and_ignores_reference_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(
                json.dumps({
                    "id": "case-1",
                    "raw": "raw transcript",
                    "expected": "must not become prompt context",
                    "categories": ["test"],
                    "must_preserve": ["raw"],
                }) + "\n",
                encoding="utf-8",
            )
            self.assertEqual([bench.Case("case-1", "raw transcript")], bench.read_cases(path))

    def test_output_comparison_reports_quantization_differences_and_stability(self) -> None:
        q4 = {
            "quantization": "Q4_K_M",
            "runs": [
                {"case_id": "a", "repeat_index": 0, "model_text": "A."},
                {"case_id": "a", "repeat_index": 1, "model_text": "A."},
                {"case_id": "b", "repeat_index": 0, "model_text": "B."},
                {"case_id": "b", "repeat_index": 1, "model_text": "B changed."},
            ],
        }
        f16 = {
            "quantization": "F16",
            "runs": [
                {"case_id": "a", "repeat_index": 0, "model_text": "A."},
                {"case_id": "a", "repeat_index": 1, "model_text": "A."},
                {"case_id": "b", "repeat_index": 0, "model_text": "B."},
                {"case_id": "b", "repeat_index": 1, "model_text": "B."},
            ],
        }
        comparison = bench.compare_outputs([q4, f16])
        self.assertEqual(3, comparison["exact_agreement_requests"])
        self.assertEqual(["b"], comparison["repeat_stability"]["Q4_K_M"]["unstable_case_ids"])
        self.assertEqual([], comparison["repeat_stability"]["F16"]["unstable_case_ids"])


if __name__ == "__main__":
    unittest.main()
