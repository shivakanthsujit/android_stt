import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "training" / "infer_sotto_lfm_batched.py"
SPEC = importlib.util.spec_from_file_location("infer_sotto_lfm_batched", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InferSottoLfmBatchedTest(unittest.TestCase):
    def test_batches_honor_size_token_budget_and_output_cap(self) -> None:
        rows = [
            {"input_ids": [1] * 4, "output_cap": 900},
            {"input_ids": [1] * 5, "output_cap": 900},
            {"input_ids": [1] * 5, "output_cap": 901},
            {"input_ids": [1] * 8, "output_cap": 901},
        ]
        result = list(MODULE.batches(rows, max_batch_size=3, max_batch_tokens=12))
        self.assertEqual([len(batch) for batch in result], [2, 1, 1])

    def test_batches_never_drop_rows(self) -> None:
        rows = [{"input_ids": [1] * length, "output_cap": 900} for length in range(1, 10)]
        result = list(MODULE.batches(rows, max_batch_size=4, max_batch_tokens=12))
        self.assertEqual([row for batch in result for row in batch], rows)


if __name__ == "__main__":
    unittest.main()
