import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "training" / "score_sotto_lfm_source_dev.py"
SPEC = importlib.util.spec_from_file_location("score_sotto_lfm_source_dev", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ScoreSottoLfmSourceDevTest(unittest.TestCase):
    def test_scores_each_source_and_failure_counter(self) -> None:
        cases = [
            {"id": "a", "source_id": "one", "raw": "r1", "expected": "x"},
            {"id": "b", "source_id": "two", "raw": "r2", "expected": "y"},
        ]
        results = [
            {"case_id": "a", "raw": "r1", "expected": "x", "model_text": "x",
             "hit_output_token_limit": False, "guardrail_would_fallback": False},
            {"case_id": "b", "raw": "r2", "expected": "y", "model_text": "",
             "hit_output_token_limit": True, "guardrail_would_fallback": True},
        ]
        report = MODULE.score(cases, results)
        self.assertEqual(report["overall"]["exact"], 1)
        self.assertEqual(report["sources"]["one"]["exact_rate"], 1.0)
        self.assertEqual(report["sources"]["two"]["cap_hits"], 1)

    def test_rejects_mismatched_ids(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "same unique set"):
            MODULE.score(
                [{"id": "a", "source_id": "one", "raw": "r", "expected": "x"}],
                [{"case_id": "b", "raw": "r", "expected": "x", "model_text": "x"}],
            )


if __name__ == "__main__":
    unittest.main()
