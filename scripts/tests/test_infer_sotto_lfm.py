import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "training" / "infer_sotto_lfm.py"
SPEC = importlib.util.spec_from_file_location("infer_sotto_lfm", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InferSottoLfmTest(unittest.TestCase):
    def test_publisher_output_cap_has_900_token_floor(self) -> None:
        self.assertEqual(MODULE.publisher_output_cap("a short transcript"), 900)

    def test_publisher_output_parser_strips_following_section(self) -> None:
        self.assertEqual(
            MODULE.parse_publisher_output("Clean text.\n### Input:\nextra"),
            "Clean text.",
        )

    def test_publisher_output_parser_preserves_plain_text(self) -> None:
        self.assertEqual(MODULE.parse_publisher_output("  Clean text.  "), "Clean text.")


if __name__ == "__main__":
    unittest.main()
