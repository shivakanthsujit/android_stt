from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/fixtures/s1-mini-direct-representative-v1.jsonl"
LITERT = ROOT / "scripts/fixtures/s1-mini-litert-representative-v1.jsonl"
EXPECTED_COUNTS = [22, 18, 26, 23, 21, 20, 22, 21, 51, 53]


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


class LiteRtRepresentativeFixtureTest(unittest.TestCase):
    def test_is_exact_transcript_projection_with_frozen_token_counts(self) -> None:
        source = load(SOURCE)
        litert = load(LITERT)
        self.assertEqual(len(source), len(litert))
        self.assertEqual(EXPECTED_COUNTS, [row["raw_tokens"] for row in litert])
        for source_row, litert_row in zip(source, litert, strict=True):
            self.assertEqual(source_row, {key: litert_row[key] for key in source_row})
            self.assertEqual({"id", "raw", "categories", "raw_tokens"}, set(litert_row))


if __name__ == "__main__":
    unittest.main()
