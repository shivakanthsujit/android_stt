from __future__ import annotations

import importlib.util
import math
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "prepare-s1-mini-pixel-cases.py"
SPEC = importlib.util.spec_from_file_location("prepare_s1_mini_pixel_cases", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PrepareS1MiniPixelCasesTest(unittest.TestCase):
    def test_publisher_output_cap(self) -> None:
        for input_tokens in (1, 10, 47, 999):
            self.assertEqual(
                math.ceil(1.3 * input_tokens + 32),
                MODULE.max_new_tokens(input_tokens),
            )

    def test_rejects_empty_tokenization(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            MODULE.max_new_tokens(0)


if __name__ == "__main__":
    unittest.main()
