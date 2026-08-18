import importlib.util
import sys
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

    def test_checkpoint_cli_accepts_spoken_input_with_hash_identity(self) -> None:
        original = sys.argv
        try:
            sys.argv = [
                "infer_sotto_lfm.py",
                "--model-dir", "/tmp/model",
                "--cases", "/tmp/cases.jsonl",
                "--output", "/tmp/results.jsonl",
                "--model-id", "local/sotto-repair",
                "--model-revision", "checkpoint-100",
                "--expected-model-sha256", "a" * 64,
                "--input-field", "spoken",
            ]
            args = MODULE.parse_args()
        finally:
            sys.argv = original
        self.assertEqual("spoken", args.input_field)
        self.assertEqual("local/sotto-repair", args.model_id)
        self.assertEqual("checkpoint-100", args.model_revision)
        self.assertEqual("a" * 64, args.expected_model_sha256)


if __name__ == "__main__":
    unittest.main()
