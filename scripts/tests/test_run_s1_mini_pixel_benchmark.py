from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "run-s1-mini-pixel-benchmark.sh"


class RunS1MiniPixelBenchmarkTest(unittest.TestCase):
    def run_until_model_check(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for variable in (
            "S1_MINI_LEAP_CPU_THREADS",
            "S1_MINI_LEAP_CONTEXT_SIZE",
            "S1_MINI_LEAP_CACHE_MB",
        ):
            env.pop(variable, None)
        env.update(
            {
                "JAVA_HOME": "/nonexistent-test-jdk",
                "ANDROID_HOME": "/nonexistent-test-android-sdk",
                **overrides,
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            missing_model = Path(directory) / "s1-mini-q4_k_m.gguf"
            return subprocess.run(
                ["bash", str(SCRIPT), str(missing_model)],
                cwd=REPO,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(SCRIPT)], cwd=REPO, check=True)

    def test_default_and_allowed_leap_values_pass_config_validation(self) -> None:
        configurations = [
            {},
            {"S1_MINI_LEAP_CPU_THREADS": "2"},
            {"S1_MINI_LEAP_CPU_THREADS": "3"},
            {"S1_MINI_LEAP_CPU_THREADS": "4"},
            {"S1_MINI_LEAP_CONTEXT_SIZE": "3072"},
            {"S1_MINI_LEAP_CONTEXT_SIZE": "2560"},
            {"S1_MINI_LEAP_CACHE_MB": "32"},
            {"S1_MINI_LEAP_CACHE_MB": "64"},
        ]
        for configuration in configurations:
            with self.subTest(configuration=configuration):
                result = self.run_until_model_check(**configuration)
                self.assertNotEqual(0, result.returncode)
                self.assertIn("Missing pinned S1-mini Q4_K_M model", result.stderr)
                self.assertNotIn("must be implicit", result.stderr)
                self.assertNotIn("must be 4096", result.stderr)
                self.assertNotIn("must be 0", result.stderr)

    def test_invalid_leap_values_are_rejected_before_model_or_device_work(self) -> None:
        invalid = [
            ("S1_MINI_LEAP_CPU_THREADS", "1", "must be implicit, 2, 3, or 4"),
            ("S1_MINI_LEAP_CPU_THREADS", "2/bad", "must be implicit, 2, 3, or 4"),
            ("S1_MINI_LEAP_CONTEXT_SIZE", "2048", "must be 4096, 3072, or 2560"),
            ("S1_MINI_LEAP_CONTEXT_SIZE", "4096-bad", "must be 4096, 3072, or 2560"),
            ("S1_MINI_LEAP_CACHE_MB", "16", "must be 0, 32, or 64"),
            ("S1_MINI_LEAP_CACHE_MB", "64/bad", "must be 0, 32, or 64"),
        ]
        for variable, value, message in invalid:
            with self.subTest(variable=variable, value=value):
                result = self.run_until_model_check(**{variable: value})
                self.assertNotEqual(0, result.returncode)
                self.assertIn(message, result.stderr)
                self.assertNotIn("Missing pinned S1-mini", result.stderr)

    def test_validated_config_is_in_run_id_and_activity_extras(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(
            'leap_config_suffix="leap-t${leap_cpu_threads}-ctx${leap_context_tokens}'
            '-cache${leap_cache_memory_mb}mb"',
            source,
        )
        self.assertIn('s1-mini-pixel-${leap_config_suffix}', source)
        self.assertIn('--ei leap_cpu_threads "$leap_cpu_threads_extra"', source)
        self.assertIn('--ei leap_context_tokens "$leap_context_tokens"', source)
        self.assertIn('--ei leap_cache_memory_mb "$leap_cache_memory_mb"', source)


if __name__ == "__main__":
    unittest.main()
