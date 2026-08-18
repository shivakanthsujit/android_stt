import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/training/prepare_sotto_lfm_mixture.py"
SPEC = importlib.util.spec_from_file_location("prepare_sotto_lfm_mixture", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class PrepareSottoLfmMixtureTests(unittest.TestCase):
    def test_stream_uses_every_row_once_without_rebalancing(self) -> None:
        pools = {
            "large": {"train": [
                {"source_id": "large", "source_ref": f"large:{index}"} for index in range(11)
            ]},
            "small": {"train": [
                {"source_id": "small", "source_ref": f"small:{index}"} for index in range(2)
            ]},
        }
        stream, counts, schedule = MODULE.build_stream(pools, "train", 934857)
        self.assertEqual(counts, {"large": 11, "small": 2})
        self.assertEqual(len(stream), 13)
        self.assertEqual(len({row["source_ref"] for row in stream}), 13)
        self.assertEqual(schedule.count("small"), 2)

    def test_disco_split_keeps_normalized_target_families_together(self) -> None:
        rows = []
        for index in range(100):
            expected = f"target {index // 2}"
            rows.append({"expected": expected, "raw": expected + " uh", "source_ref": str(index)})
        train, dev, test = MODULE.split_disco(
            rows, 934857, {"train": 0.8, "dev": 0.1, "test": 0.1},
        )
        families = [
            {MODULE.normalized_text(row["expected"]) for row in split}
            for split in (train, dev, test)
        ]
        self.assertFalse(families[0] & families[1])
        self.assertFalse(families[0] & families[2])
        self.assertFalse(families[1] & families[2])
        self.assertEqual(len(train) + len(dev) + len(test), len(rows))

if __name__ == "__main__":
    unittest.main()
