from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "benchmark-s1-mini-bf16.py"
SPEC = importlib.util.spec_from_file_location("benchmark_s1_mini_bf16", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
bench = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bench
SPEC.loader.exec_module(bench)


class BenchmarkS1MiniBf16Test(unittest.TestCase):
    def test_publisher_configuration_is_pinned(self) -> None:
        self.assertEqual(
            bench.CONTROL_LINE,
            "[Styling: semi-formal] [Structure: prose] [Context: general]",
        )
        self.assertEqual(
            bench.MODEL_REVISION,
            "65f84bcda1d13df582c4a8443c1c5aa53c0c66db",
        )
        self.assertEqual(
            bench.MODEL_SHA256,
            "69d2057077ab4dc738aaaab75d2a8ffa141e3a09fb9d956198cfce46f381131a",
        )

    def test_output_cap_matches_publisher_formula(self) -> None:
        self.assertEqual(bench.max_new_tokens(1), 34)
        self.assertEqual(bench.max_new_tokens(10), 45)

    def test_case_reader_ignores_reference_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text(
                json.dumps({"id": "one", "raw": "hello", "expected": "secret"}) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(bench.read_cases(path), [bench.Case("one", "hello")])


if __name__ == "__main__":
    unittest.main()
