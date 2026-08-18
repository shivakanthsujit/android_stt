from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/score-joined-results.py"
SPEC = importlib.util.spec_from_file_location("score_joined_results", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ScoreJoinedResultsTest(unittest.TestCase):
    def test_reads_complete_unique_results(self) -> None:
        row = {
            "case_id": "personal-tts-001",
            "reference": "Meet me at six twenty.",
            "raw_stt": "Meet me at six twenty.",
            "raw_model_output": "Meet me at 6:20.",
            "guarded_output": "Meet me at 6:20.",
            "used_fallback": False,
            "stt_inference_ms": 100,
            "cleanup_total_ms": 50,
            "pipeline_total_ms": 150,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            self.assertEqual([row], MODULE.read_results(path))

    def test_rejects_duplicate_case_ids(self) -> None:
        row = {
            "case_id": "duplicate",
            "reference": "hello",
            "raw_stt": "hello",
            "raw_model_output": "Hello.",
            "guarded_output": "Hello.",
            "used_fallback": False,
            "stt_inference_ms": 1,
            "cleanup_total_ms": 1,
            "pipeline_total_ms": 2,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                MODULE.read_results(path)

    def test_normalization_ignores_case_and_punctuation(self) -> None:
        self.assertEqual(
            MODULE.normalize("Could we meet at six-twenty?"),
            MODULE.normalize("could we meet at six twenty"),
        )

    def test_timing_uses_nearest_rank_p90(self) -> None:
        summary = MODULE.timing([1.0, 2.0, 3.0, 4.0, 100.0])
        self.assertEqual(3.0, summary["median_ms"])
        self.assertEqual(100.0, summary["p90_ms"])
        self.assertEqual(100.0, summary["max_ms"])

    def test_scores_cleaned_targets_separately_from_spoken_reference(self) -> None:
        row = {
            "case_id": "personal-tts-001",
            "reference": "Well, uh, I think I think dinner sounds better.",
            "raw_stt": "Well, uh, I think I think dinner sounds better.",
            "raw_model_output": "I think dinner sounds better.",
            "guarded_output": "I think dinner sounds better.",
            "used_fallback": False,
            "stt_inference_ms": 100,
            "cleanup_total_ms": 50,
            "pipeline_total_ms": 150,
        }
        summary = MODULE.summarize(
            [row], {"personal-tts-001": "I think dinner sounds better."}
        )
        self.assertEqual(1, summary["raw_stt_normalized_exact"])
        self.assertEqual(1, summary["raw_model_target_strict_exact"])
        self.assertEqual(1, summary["guarded_target_normalized_exact"])

    def test_expected_case_ids_must_match_results(self) -> None:
        row = {
            "case_id": "one",
            "reference": "hello",
            "raw_stt": "hello",
            "raw_model_output": "Hello.",
            "guarded_output": "Hello.",
            "used_fallback": False,
            "stt_inference_ms": 1,
            "cleanup_total_ms": 1,
            "pipeline_total_ms": 2,
        }
        with self.assertRaisesRegex(ValueError, "mismatch"):
            MODULE.summarize([row], {"two": "Hello."})


if __name__ == "__main__":
    unittest.main()
