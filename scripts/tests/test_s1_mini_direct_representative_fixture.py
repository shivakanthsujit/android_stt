import json
import re
import statistics
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "scripts" / "fixtures" / "s1-mini-direct-representative-v1.jsonl"
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
REQUIRED_CATEGORIES = {
    "message",
    "reminder",
    "short-list",
    "uncertainty",
    "natural-correction",
    "formatting-request",
    "brief-journal",
    "names",
    "numbers",
}
FORBIDDEN_FIELDS = {
    "expected",
    "expected_output",
    "must_preserve",
    "output",
    "reference",
    "target",
}


def surface_units(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE))


class S1MiniDirectRepresentativeFixtureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = [
            json.loads(line)
            for line in FIXTURE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_schema_ids_and_transcript_only_contract(self) -> None:
        self.assertEqual(10, len(self.rows))
        ids: set[str] = set()
        for row in self.rows:
            self.assertEqual({"id", "raw", "categories"}, set(row))
            self.assertFalse(FORBIDDEN_FIELDS & set(row))
            self.assertIsInstance(row["id"], str)
            self.assertRegex(row["id"], SAFE_ID)
            self.assertNotIn(row["id"], ids)
            ids.add(row["id"])
            self.assertIsInstance(row["raw"], str)
            self.assertTrue(row["raw"].strip())
            self.assertIsInstance(row["categories"], list)
            self.assertEqual(len(row["categories"]), len(set(row["categories"])))
            self.assertTrue(all(isinstance(value, str) and value for value in row["categories"]))

    def test_representative_shapes_and_categories_are_covered(self) -> None:
        categories = {value for row in self.rows for value in row["categories"]}
        self.assertTrue(REQUIRED_CATEGORIES.issubset(categories))
        for row in self.rows:
            self.assertIn("representative-v1", row["categories"])
            shapes = [value for value in row["categories"] if value.startswith("shape-")]
            self.assertEqual(1, len(shapes))
        self.assertEqual(8, sum("shape-short" in row["categories"] for row in self.rows))
        self.assertEqual(2, sum("shape-medium" in row["categories"] for row in self.rows))

    def test_tokenizer_independent_length_guard(self) -> None:
        units = [surface_units(row["raw"]) for row in self.rows]
        self.assertEqual(8, sum(value <= 28 for value in units))
        self.assertEqual(2, sum(29 <= value <= 80 for value in units))
        self.assertLessEqual(statistics.median(units), 22)
        self.assertLessEqual(max(units), 80)
        for row in self.rows:
            self.assertLessEqual(len(row["raw"].encode("utf-8")), 320)

    def test_fixture_path_is_outside_evaluation_tree(self) -> None:
        evaluation = (REPO / "docs" / "evaluation").resolve()
        self.assertNotIn(evaluation, FIXTURE.resolve().parents)


if __name__ == "__main__":
    unittest.main()
