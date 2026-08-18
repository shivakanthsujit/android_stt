from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


merger = _load("merge_cleanup_openai_shards_test", "merge-cleanup-openai-shards.py")
launcher = _load("run_cleanup_openai_sharded_test", "run-cleanup-openai-sharded.py")


def _case(case_id: str, raw: str) -> dict:
    return {
        "id": case_id,
        "raw": raw,
        "expected": raw.capitalize() + ".",
        "categories": ["test"],
        "must_preserve": [raw],
        "must_remove": [],
    }


class MergerTest(unittest.TestCase):
    def _fixture(self, root: Path, shard_count: int = 3):
        cases_path = root / "cases.jsonl"
        case_rows = [_case("zeta", "zeta"), _case("alpha", "alpha"), _case("middle", "middle")]
        cases_path.write_text(
            "".join(json.dumps(row) + "\n" for row in case_rows), encoding="utf-8"
        )
        cases_hash = merger.runner.sha256_file(cases_path)
        shard_paths = [root / f"shard-{index}.jsonl" for index in range(shard_count)]
        grouped: list[list[dict]] = [[] for _ in range(shard_count)]
        for source_index, case in enumerate(case_rows):
            shard_index = merger.runner.stable_shard_index(case["id"], shard_count)
            grouped[shard_index].append(
                {
                    "case_id": case["id"],
                    "source_index": source_index,
                    "shard_count": shard_count,
                    "shard_index": shard_index,
                    "cases_sha256": cases_hash,
                    "evaluation_fingerprint": "f" * 64,
                    "raw": case["raw"],
                    "expected": case["expected"],
                    "categories": case["categories"],
                    "must_preserve": case["must_preserve"],
                    "must_remove": [],
                    "model_text": case["expected"],
                    "selected_text": case["expected"],
                    "raw_model_output_is_selected_for_scoring": True,
                    "guardrail_selected_text": case["expected"],
                    "timings": {"ttft_ms": 1.0, "total_ms": 2.0},
                }
            )
        for path, rows in zip(shard_paths, grouped):
            path.write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
            )
        return cases_path, shard_paths, grouped

    def test_merge_validates_and_restores_source_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cases, shard_paths, _ = self._fixture(Path(directory))
            rows = merger.validate_and_order(
                cases_path=cases, shard_paths=shard_paths, shard_count=3
            )
            self.assertEqual(["zeta", "alpha", "middle"], [row["case_id"] for row in rows])

    def test_merge_rejects_missing_and_duplicate_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases, shard_paths, grouped = self._fixture(root)
            populated = next(index for index, rows in enumerate(grouped) if rows)
            removed = grouped[populated].pop()
            shard_paths[populated].write_text(
                "".join(json.dumps(row) + "\n" for row in grouped[populated]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(merger.MergeError, "missing 1 case"):
                merger.validate_and_order(
                    cases_path=cases, shard_paths=shard_paths, shard_count=3
                )
            wrong_path = shard_paths[(populated + 1) % 3]
            with wrong_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(removed) + "\n")
            with self.assertRaisesRegex(
                merger.MergeError, "belongs to shard|duplicate case_id"
            ):
                merger.validate_and_order(
                    cases_path=cases, shard_paths=shard_paths, shard_count=3
                )

    def test_merge_rejects_source_schema_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases, shard_paths, grouped = self._fixture(root)
            populated = next(index for index, rows in enumerate(grouped) if rows)
            grouped[populated][0]["raw"] = "tampered"
            shard_paths[populated].write_text(
                "".join(json.dumps(row) + "\n" for row in grouped[populated]),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(merger.MergeError, "raw differs"):
                merger.validate_and_order(
                    cases_path=cases, shard_paths=shard_paths, shard_count=3
                )


class _FakeProcess:
    def __init__(self, command: list[str], return_code: int = 0):
        self.command = command
        self.return_code = return_code

    def wait(self) -> int:
        return self.return_code

    def poll(self) -> int:
        return self.return_code

    def terminate(self) -> None:
        self.return_code = -15


class LauncherTest(unittest.TestCase):
    def _arguments(self, root: Path) -> SimpleNamespace:
        return SimpleNamespace(
            model="adapter",
            base_url="http://127.0.0.1:8000/v1",
            cases=root / "cases.jsonl",
            output_dir=root / "shards",
            output=root / "merged.jsonl",
            clients=3,
            quantization="bf16-lora",
            prompt_variant="cleanup_instruction_v2",
            temperature=0.0,
            request_extra=root / "extras.json",
            output_token_field="max_completion_tokens",
            output_cap_policy="android",
            api_key_env="OPENAI_API_KEY",
            timeout=120.0,
            retries=1,
            retry_delay=0.5,
            token_progress_seconds=0.0,
            token_offset_input=0,
            token_offset_output=0,
            max_campaign_tokens=None,
            progress_every=100,
            case_id=[],
            resume=True,
            no_stream=False,
            omit_seed=False,
        )

    def test_launcher_starts_unique_raw_scoring_clients_then_merges(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = self._arguments(root)
            commands: list[list[str]] = []

            def popen(command: list[str]):
                commands.append(command)
                return _FakeProcess(command)

            with mock.patch.object(launcher.subprocess, "Popen", side_effect=popen), mock.patch.object(
                launcher.subprocess, "run", return_value=SimpleNamespace(returncode=0)
            ) as merge:
                self.assertEqual(0, launcher.run(arguments))
            self.assertEqual(3, len(commands))
            outputs = [command[command.index("--output") + 1] for command in commands]
            self.assertEqual(3, len(set(outputs)))
            self.assertTrue(all("--raw-scoring" in command for command in commands))
            self.assertTrue(all("--resume" in command for command in commands))
            self.assertTrue(
                all(
                    command[command.index("--progress-every") + 1] == "100"
                    for command in commands
                )
            )
            self.assertTrue(
                all(
                    command[command.index("--output-token-field") + 1]
                    == "max_completion_tokens"
                    for command in commands
                )
            )
            self.assertEqual(1, merge.call_count)

    def test_launcher_skips_merge_when_any_client_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arguments = self._arguments(root)
            call = 0

            def popen(command: list[str]):
                nonlocal call
                result = _FakeProcess(command, return_code=2 if call == 1 else 0)
                call += 1
                return result

            with mock.patch.object(launcher.subprocess, "Popen", side_effect=popen), mock.patch.object(
                launcher.subprocess, "run"
            ) as merge, self.assertRaisesRegex(launcher.LaunchError, "merge skipped"):
                launcher.run(arguments)
            merge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
