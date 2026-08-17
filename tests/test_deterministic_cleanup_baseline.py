from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.deterministic_cleanup_baseline import cleanup_text


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deterministic_cleanup_baseline.py"
CORPUS = ROOT / "docs" / "evaluation" / "cleanup_cases.jsonl"


class CleanupTextTest(unittest.TestCase):
    def test_removes_only_standalone_fillers(self) -> None:
        self.assertEqual(
            cleanup_text("uh the album is under the umbrella um"),
            "The album is under the umbrella.",
        )

    def test_collapses_exact_word_and_phrase_repeats(self) -> None:
        self.assertEqual(
            cleanup_text("can you can you send the the link"),
            "Can you send the link?",
        )

    def test_handles_explicit_make_that_correction(self) -> None:
        self.assertEqual(
            cleanup_text("send it on Tuesday actually make that Thursday"),
            "Send it on Thursday.",
        )

    def test_handles_matching_modal_correction(self) -> None:
        self.assertEqual(
            cleanup_text(
                "can you send that to Sarah actually no send it to James tomorrow"
            ),
            "Can you send that to James tomorrow?",
        )

    def test_handles_explicit_preference_correction(self) -> None:
        self.assertEqual(
            cleanup_text("let's meet at three actually four thirty works better"),
            "Let's meet at four thirty; that works better.",
        )

    def test_does_not_treat_bare_actually_as_correction(self) -> None:
        self.assertEqual(
            cleanup_text("I actually like Thursday"),
            "I actually like Thursday.",
        )

    def test_preserves_unicode_and_technical_tokens(self) -> None:
        self.assertEqual(
            cleanup_text("send ./gradlew output to Sébastien at localhost:8080"),
            "Send ./gradlew output to Sébastien at localhost:8080.",
        )

    def test_formats_three_step_sequence(self) -> None:
        self.assertEqual(
            cleanup_text("first install it then restart it then test it"),
            "First, install it. Then restart it and test it.",
        )

    def test_empty_input_stays_empty(self) -> None:
        self.assertEqual(cleanup_text("  \r\n "), "")


class CommandLineTest(unittest.TestCase):
    def test_emits_scorer_compatible_complete_run(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--cases", str(CORPUS)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        rows = [json.loads(line) for line in completed.stdout.splitlines()]
        self.assertEqual(len(rows), 24)
        self.assertEqual(rows[0]["case_id"], "cleanup-001")
        self.assertEqual(rows[-1]["case_id"], "cleanup-024")
        for row in rows:
            self.assertIsInstance(row["model_text"], str)
            self.assertEqual(row["selected_text"], row["model_text"])
            self.assertFalse(row["used_fallback"])
            self.assertGreaterEqual(row["timings"]["cleanup_ms"], 0)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results.jsonl"
            output.write_text(completed.stdout, encoding="utf-8")
            score = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "score-cleanup-results.py"),
                    "--cases",
                    str(CORPUS),
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            # Strict scoring returns non-zero for mismatches, but schema parsing
            # and a complete-run report must still succeed.
            self.assertNotEqual(score.returncode, 2, score.stderr)
            self.assertIn("Cases: 24", score.stdout)


if __name__ == "__main__":
    unittest.main()
