import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "run-s1-mini-direct-pixel-benchmark.sh"


class RunS1MiniDirectPixelBenchmarkTest(unittest.TestCase):
    def test_runner_uses_isolated_release_contract_and_transcript_projection(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('package_name="dev.localflow.llamacppbenchmark"', source)
        self.assertIn("llamacpp-benchmark-release.apk", source)
        self.assertIn('device_model="files/models/$model_name"', source)
        self.assertIn('device_cases="files/benchmark/cases.jsonl"', source)
        self.assertIn('device_result="files/benchmark/results-$run_id.jsonl"', source)
        self.assertIn("prepare-s1-mini-direct-cases.py", source)
        self.assertNotIn("cleanup_personal_conversation_v3", source)
        self.assertIn("ANDROID_SERIAL", source)
        self.assertIn("ro.product.cpu.abi", source)
        self.assertIn('device_brand" != "google"', source)
        self.assertIn('adb push "$prepared_cases"', source)
        self.assertNotIn('adb push "$cases_file"', source)
        self.assertIn('thermal_status" != "0"', source)
        self.assertIn('manifest["start_thermal_status"]', source)
        self.assertIn("localflow_llamacpp_benchmark", source)
        self.assertIn("localflow_llamacpp_inference", source)
        for extra in (
            "context_tokens", "generation_threads", "batch_threads", "batch_size",
            "micro_batch_size", "use_mmap", "flash_attention", "gpu_layers",
        ):
            self.assertIn(extra, source)

    def test_invalid_matrix_value_fails_before_adb(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adb_marker = root / "adb-called"
            adb = root / "adb"
            adb.write_text(
                f"#!/usr/bin/env bash\nprintf called > {adb_marker}\nexit 99\n",
                encoding="utf-8",
            )
            adb.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{root}:{env['PATH']}"
            env["S1_DIRECT_GENERATION_THREADS"] = "5"
            result = subprocess.run(
                [str(SCRIPT), "unused-model", "/tmp/non-eval-cases.jsonl"],
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("Invalid S1_DIRECT_GENERATION_THREADS", result.stderr)
            self.assertFalse(adb_marker.exists())

    def test_missing_explicit_cases_fails_before_adb(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adb_marker = root / "adb-called"
            adb = root / "adb"
            adb.write_text(
                f"#!/usr/bin/env bash\nprintf called > {adb_marker}\nexit 99\n",
                encoding="utf-8",
            )
            adb.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{root}:{env['PATH']}"
            env["ANDROID_SERIAL"] = "pixel-test"
            result = subprocess.run(
                [str(SCRIPT)], cwd=REPO, env=env, capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(0, result.returncode)
            self.assertIn("explicit non-evaluation transcript JSONL", result.stderr)
            self.assertFalse(adb_marker.exists())

    def test_relative_evaluation_path_fails_before_adb(self) -> None:
        env = os.environ.copy()
        env["ANDROID_SERIAL"] = "pixel-test"
        result = subprocess.run(
            [str(SCRIPT), "unused-model", "docs/evaluation/cleanup_cases.jsonl"],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(0, result.returncode)
        self.assertIn("Evaluation corpora are prohibited", result.stderr)

    def test_runner_retains_error_and_partial_results(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("retain_failure_artifacts", source)
        self.assertIn('device_partial="$device_result.partial"', source)
        self.assertIn('device_error="files/benchmark/error-$run_id.json"', source)
        self.assertIn('--control "$control_file"', source)


if __name__ == "__main__":
    unittest.main()
