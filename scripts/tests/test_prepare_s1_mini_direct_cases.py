import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "prepare-s1-mini-direct-cases.py"
SPEC = importlib.util.spec_from_file_location("prepare_s1_mini_direct_cases", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PrepareS1MiniDirectCasesTest(unittest.TestCase):
    def test_keeps_only_transcript_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cases.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "id": "smoke-001",
                        "raw": "um hello",
                        "categories": ["short"],
                        "expected": "must never be staged",
                        "captured_model_output": "must never be staged either",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [{"id": "smoke-001", "raw": "um hello", "categories": ["short"]}],
                MODULE.prepare(source),
            )

    def test_rejects_blind_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "blind evaluation inputs are prohibited"):
            MODULE.prepare(Path("cleanup_cases_blind_v2.jsonl"))
        with self.assertRaisesRegex(ValueError, "blind evaluation inputs are prohibited"):
            MODULE.prepare(Path("blind-v2/cases.jsonl"))

    def test_rejects_non_object_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cases.jsonl"
            source.write_text('["not", "an", "object"]\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "row must be an object"):
                MODULE.prepare(source)

    def test_rejects_case_ids_the_apk_cannot_parse(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cases.jsonl"
            source.write_text(
                '{"id":"bad id","raw":"hello","categories":[]}\n', encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "invalid or duplicate id"):
                MODULE.prepare(source)

    def test_cli_refuses_to_overwrite_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cases.jsonl"
            output = root / "prepared.jsonl"
            source.write_text(
                '{"id":"one","raw":"hello","categories":[]}\n', encoding="utf-8"
            )
            output.write_text("keep", encoding="utf-8")
            result = subprocess.run(
                [str(SCRIPT), str(source), "--output", str(output)],
                cwd=REPO,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("output already exists", result.stderr)
            self.assertEqual("keep", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
