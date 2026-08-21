import json
import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "scripts" / "fixtures" / "s1-mini-direct-performance-v1.jsonl"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
REQUIRED_CATEGORIES = {
    "shape-short",
    "shape-medium",
    "shape-long",
    "punctuation",
    "unicode",
    "filler",
    "paragraphs",
}


class S1MiniDirectPerformanceFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = [
            json.loads(line)
            for line in FIXTURE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_schema_ids_and_text_are_safe(self) -> None:
        self.assertEqual(12, len(self.rows))
        ids: set[str] = set()
        for row in self.rows:
            self.assertEqual({"id", "raw", "categories"}, set(row))
            self.assertIsInstance(row["id"], str)
            self.assertRegex(row["id"], SAFE_ID)
            self.assertNotIn(row["id"], ids)
            ids.add(row["id"])
            self.assertIsInstance(row["raw"], str)
            self.assertTrue(row["raw"].strip())
            self.assertIsInstance(row["categories"], list)
            self.assertTrue(row["categories"])
            self.assertTrue(all(isinstance(value, str) and value for value in row["categories"]))
            self.assertEqual(len(row["categories"]), len(set(row["categories"])))

    def test_required_shape_and_stress_categories_are_covered(self) -> None:
        categories = {value for row in self.rows for value in row["categories"]}
        self.assertTrue(REQUIRED_CATEGORIES.issubset(categories))
        for shape in ("shape-short", "shape-medium", "shape-long"):
            self.assertGreaterEqual(
                sum(shape in row["categories"] for row in self.rows),
                3,
            )

    def test_fixture_is_non_evaluation_and_within_raw_token_safety_ceiling(self) -> None:
        fixture_parts = {part.casefold() for part in FIXTURE.resolve().parts}
        evaluation_parts = {part.casefold() for part in (REPO / "docs" / "evaluation").resolve().parts}
        self.assertFalse(evaluation_parts.issubset(fixture_parts))
        for row in self.rows:
            # UTF-8 bytes are a conservative upper bound for a byte-backed tokenizer.
            self.assertLessEqual(len(row["raw"].encode("utf-8")), 1_000)


if __name__ == "__main__":
    unittest.main()
