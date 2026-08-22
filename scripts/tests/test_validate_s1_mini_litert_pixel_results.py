from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/validate-s1-mini-litert-pixel-results.py"
SPEC = importlib.util.spec_from_file_location("litert_validator", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class LiteRtPixelValidatorTest(unittest.TestCase):
    def test_prompt_and_hash_are_stable(self) -> None:
        prompt = MODULE.expected_prompt("um hello there")
        self.assertTrue(prompt.endswith("<think>\n\n</think>\n\n"))
        self.assertEqual(
            "0b546eb4a221629272391b80cbf55e5cf26af3f9ff9df2305923d1362b4c99fb",
            MODULE.sha256_text(prompt),
        )


if __name__ == "__main__":
    unittest.main()
