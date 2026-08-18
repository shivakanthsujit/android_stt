import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/training/train_sotto_lfm.py"
SPEC = importlib.util.spec_from_file_location("train_sotto_lfm", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeTokenizer:
    eos_token_id = 7

    def __call__(self, text, **kwargs):
        return {"input_ids": [1] + [ord(character) for character in text]}


class TrainSottoLfmTests(unittest.TestCase):
    def test_campaign_config_is_full_sft_and_has_no_hardcoded_seed(self) -> None:
        config = json.loads((ROOT / "training/config/sotto-lfm-training-v1.json").read_text())
        self.assertNotIn("seed", config["common"])
        self.assertNotIn("data_seed", config["common"])
        self.assertTrue(config["dataset"]["packing"])
        self.assertTrue(config["dataset"]["pass_seq_idx_for_hybrid_state_reset"])
        self.assertNotIn("lora", json.dumps(config).casefold())

    def test_data_config_uses_expected_fields_and_isolates_holdouts(self) -> None:
        config = json.loads((ROOT / "training/config/sotto-lfm-data-v1.json").read_text())
        self.assertNotIn("seed", config)
        self.assertEqual(config["mixture_strategy"], "shuffled-single-pass-all-eligible-rows")
        self.assertEqual(
            (config["sources"]["disfl_qa"]["raw_field"], config["sources"]["disfl_qa"]["expected_field"]),
            ("disfluent", "original"),
        )
        self.assertIn("val.jsonl", config["sources"]["sotto"]["excluded_files"])
        self.assertIn("test.json", config["sources"]["disfl_qa"]["excluded_files"])
        self.assertIn("data/test-00000-of-00001.parquet", config["sources"]["nyra"]["excluded_files"])

    def test_native_completion_masks_only_prompt(self) -> None:
        tokenizer = FakeTokenizer()
        row = {"id": "one", "source_id": "sotto", "raw": "raw", "expected": "clean"}
        encoded = MODULE.encode_record(
            tokenizer, "### Input:\n{raw}\n\n### Output:\n", row, 4096,
        )
        self.assertTrue(all(value == -100 for value in encoded["labels"][:encoded["prompt_tokens"]]))
        self.assertEqual(encoded["labels"][-1], tokenizer.eos_token_id)
        self.assertEqual(len(encoded["input_ids"]), len(encoded["labels"]))

    def test_packing_resets_position_and_lfm_sequence_state(self) -> None:
        rows = [
            {"id": "a", "input_ids": [1, 2, 7], "labels": [-100, 2, 7]},
            {"id": "b", "input_ids": [1, 3, 4, 7], "labels": [-100, 3, 4, 7]},
        ]
        packed = MODULE.pack_examples(rows, 16)
        self.assertEqual(len(packed), 1)
        self.assertEqual(packed[0]["position_ids"], [0, 1, 2, 0, 1, 2, 3])
        self.assertEqual(packed[0]["seq_idx"], [0, 0, 0, 1, 1, 1, 1])
        self.assertNotIn("attention_mask", packed[0])

    def test_packing_never_splits_an_example(self) -> None:
        rows = [
            {"id": "a", "input_ids": [1] * 6, "labels": [1] * 6},
            {"id": "b", "input_ids": [2] * 5, "labels": [2] * 5},
        ]
        packed = MODULE.pack_examples(rows, 10)
        self.assertEqual([len(row["input_ids"]) for row in packed], [6, 5])
        self.assertEqual([row["example_count"] for row in packed], [1, 1])

    def test_fixed_run_controls(self) -> None:
        self.assertEqual(MODULE.validate_controls("longest_smoke", -1, None, None), 2)
        with self.assertRaises(RuntimeError):
            MODULE.validate_controls("full", 2, None, None)


if __name__ == "__main__":
    unittest.main()
