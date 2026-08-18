import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "score-stt-results.py"
SPEC = importlib.util.spec_from_file_location("score_stt_results", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ScoreSttResultsTest(unittest.TestCase):
    def test_normalization_ignores_case_and_punctuation(self):
        self.assertEqual(
            ["it's", "version", "2", "1"],
            MODULE.normalize_words("  IT’S version 2.1! "),
        )

    def test_edit_counts(self):
        substitutions, insertions, deletions = MODULE.edit_counts(
            "one two three".split(), "one too extra".split()
        )
        self.assertEqual(2, substitutions)
        self.assertEqual(0, insertions)
        self.assertEqual(0, deletions)

    def test_score_uses_one_quality_row_but_all_latency_rows(self):
        base = {
            "schema_version": 1,
            "run_id": "run",
            "engine": "engine",
            "phase": "measured",
            "case_id": "case",
            "reference": "hello world",
            "hypothesis": "hello word",
            "audio_duration_ms": 1000.0,
            "model_load_duration_ms": 50.0,
            "process_cpu_duration_ms": 75.0,
            "average_process_cpu_cores": 0.75,
        }
        rows = [
            {**base, "repeat_index": 0, "inference_duration_ms": 100.0, "real_time_factor": 0.1},
            {**base, "repeat_index": 1, "inference_duration_ms": 200.0, "real_time_factor": 0.2},
        ]
        summary = MODULE.score(rows)
        self.assertEqual(2, summary["reference_word_count"])
        self.assertEqual(1, summary["word_errors"])
        self.assertEqual(0.5, summary["wer"])
        self.assertEqual(150.0, summary["median_inference_duration_ms"])
        self.assertEqual(200.0, summary["max_inference_duration_ms"])
        self.assertEqual(0.2, summary["max_real_time_factor"])
        self.assertEqual(150.0, summary["total_process_cpu_duration_ms"])
        self.assertEqual(75.0, summary["median_process_cpu_duration_ms"])
        self.assertEqual(0.75, summary["median_average_process_cpu_cores"])


if __name__ == "__main__":
    unittest.main()
