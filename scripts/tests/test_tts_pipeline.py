from __future__ import annotations

import importlib.util
import json
import math
import shutil
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/tts/tts_pipeline.py"
SPEC = importlib.util.spec_from_file_location("tts_pipeline", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def write_tone(path: Path, sample_rate: int = 24000, channels: int = 1) -> None:
    samples = []
    for index in range(sample_rate // 5):
        value = int(6000 * math.sin(2 * math.pi * 440 * index / sample_rate))
        samples.extend([value] * channels)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"".join(struct.pack("<h", value) for value in samples))


class TtsPipelineTest(unittest.TestCase):
    def test_cleanup_projection_uses_only_spoken_input_metadata(self) -> None:
        path = REPO / "docs/evaluation/cleanup_cases_heldout_v1.jsonl"
        cases = MODULE.project_cleanup_cases(path, "heldout", REPO)
        source_rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        self.assertEqual(45, len(cases))
        self.assertEqual(source_rows[0]["spoken"], cases[0].text)
        plan = MODULE.generation_plan(cases, 23)
        serialized = json.dumps(plan)
        self.assertNotIn('"raw"', serialized)
        self.assertNotIn('"expected"', serialized)
        self.assertNotIn('"must_preserve"', serialized)
        self.assertEqual("spoken", plan[0]["source_text_field"])

    def test_cleanup_projection_rejects_unallowlisted_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text('{"id":"case","spoken":"hello","categories":[]}\n')
            with self.assertRaisesRegex(RuntimeError, "not allowlisted"):
                MODULE.project_cleanup_cases(path, "fixture", REPO)

    def test_additional_suite_is_bounded_and_safe(self) -> None:
        path = REPO / "docs/evaluation/stt_personal_conversation_tts_cases_v3.jsonl"
        cases = MODULE.project_additional_cases(path, REPO)
        self.assertEqual(20, len(cases))
        self.assertEqual(20, len({case.case_id for case in cases}))
        self.assertTrue(all(MODULE.SAFE_ID.fullmatch(case.case_id) for case in cases))
        self.assertTrue(all(case.case_id.startswith("personal-v3-") for case in cases))
        combined = "\n".join(case.text.lower() for case in cases)
        for excluded in (
            "https", "checksum", "git clone", "tls", "max retries", ".jp",
            "reports/", "download csv", "version 2", "gradle",
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(excluded, combined)
        self.assertNotIn("phone", combined)
        self.assertNotIn("callback number", combined)
        source_rows = [json.loads(line) for line in path.read_text().splitlines() if line]
        sentence_counts = [len([part for part in row["spoken"].split(".") if part.strip()]) for row in source_rows]
        self.assertGreaterEqual(sum(count >= 3 for count in sentence_counts), 4)
        self.assertLessEqual(max(sentence_counts), 5)

    def test_personal_v3_audio_and_checkpoint_cases_match(self) -> None:
        audio_path = REPO / "docs/evaluation/stt_personal_conversation_tts_cases_v3.jsonl"
        checkpoint_path = REPO / "docs/evaluation/cleanup_personal_conversation_v3.jsonl"
        audio = [json.loads(line) for line in audio_path.read_text().splitlines() if line]
        checkpoint = [json.loads(line) for line in checkpoint_path.read_text().splitlines() if line]
        self.assertEqual([row["id"] for row in audio], [row["id"] for row in checkpoint])
        self.assertEqual(
            [(row["spoken"], row["expected"]) for row in audio],
            [(row["spoken"], row["expected"]) for row in checkpoint],
        )
        self.assertTrue(all(row["raw"] == row["spoken"] for row in checkpoint))
        self.assertEqual(4, sum("long_form" in row["categories"] for row in checkpoint))

    def test_case_seed_is_stable_and_text_sensitive(self) -> None:
        first = MODULE.TtsCase("case-1", "hello", (), "source", "path")
        changed = MODULE.TtsCase("case-1", "hello there", (), "source", "path")
        self.assertEqual(MODULE.case_seed(first, 23), MODULE.case_seed(first, 23))
        self.assertNotEqual(MODULE.case_seed(first, 23), MODULE.case_seed(changed, 23))

    def test_duplicate_ids_fail_closed(self) -> None:
        case = MODULE.TtsCase("case-1", "hello", (), "source", "path")
        with self.assertRaisesRegex(RuntimeError, "Duplicate"):
            MODULE.validate_cases([case, case])

    def test_profile_pins_full_model_and_runtime_revisions(self) -> None:
        profile = MODULE.read_json(REPO / "tts/config/qwen3-tts-customvoice-8bit-v1.json")
        MODULE.validate_profile(profile)
        self.assertEqual("Ryan", profile["voice"])
        self.assertEqual("English", profile["language"])
        self.assertEqual("0.4.6", profile["runtime"]["version"])
        self.assertEqual(40, len(profile["runtime"]["revision"]))
        self.assertEqual(40, len(profile["model"]["revision"]))

    def test_inspect_wav_accepts_canonical_tone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tone.wav"
            write_tone(path, sample_rate=16000)
            info = MODULE.inspect_wav(path, require_canonical=True)
            self.assertEqual(16000, info["sample_rate_hz"])
            self.assertEqual(1, info["channels"])
            self.assertGreater(info["rms_pcm16"], 1)

    def test_inspect_wav_rejects_wrong_rate_and_silence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wrong_rate = root / "wrong.wav"
            write_tone(wrong_rate, sample_rate=24000)
            with self.assertRaisesRegex(RuntimeError, "not 16 kHz"):
                MODULE.inspect_wav(wrong_rate, require_canonical=True)
            silence = root / "silence.wav"
            with wave.open(str(silence), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(16000)
                handle.writeframes(b"\x00\x00" * 1600)
            with self.assertRaisesRegex(RuntimeError, "silent"):
                MODULE.inspect_wav(silence, require_canonical=True)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_canonicalize_wav_derives_android_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "master.wav"
            destination = root / "canonical.wav"
            write_tone(source, sample_rate=24000, channels=2)
            MODULE.canonicalize_wav(source, destination, shutil.which("ffmpeg"))
            info = MODULE.inspect_wav(destination, require_canonical=True)
            self.assertEqual((16000, 1, 16), (
                info["sample_rate_hz"], info["channels"], info["sample_width_bits"]
            ))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
    def test_prepare_corpus_writes_android_manifest_and_resumes(self) -> None:
        class FakeBackend:
            def __init__(self, _profile):
                pass

            def generate(self, _case, _seed, destination):
                write_tone(destination, sample_rate=24000)
                return {}

        original = MODULE.MlxAudioBackend
        MODULE.MlxAudioBackend = FakeBackend
        try:
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "corpus"
                case = MODULE.TtsCase(
                    "fixture-1", "Hello fixture.", ("fixture",),
                    "fixture", "manual-test-input",
                )
                profile = REPO / "tts/config/qwen3-tts-customvoice-8bit-v1.json"
                first = MODULE.prepare_corpus(
                    cases=[case], profile_path=profile, output=output,
                    repo_root=REPO, resume=False,
                )
                manifest_before = (output / "manifest.jsonl").read_bytes()
                row = json.loads(manifest_before)
                self.assertEqual(
                    {"case_id", "audio_file", "audio_sha256", "reference"},
                    {"case_id", "audio_file", "audio_sha256", "reference"} & set(row),
                )
                self.assertEqual("spoken", row["source_text_field"])
                self.assertNotIn("expected", row)
                self.assertTrue(MODULE.SHA256.fullmatch(first["manifest_sha256"]))
                MODULE.prepare_corpus(
                    cases=[case], profile_path=profile, output=output,
                    repo_root=REPO, resume=True,
                )
                self.assertEqual(manifest_before, (output / "manifest.jsonl").read_bytes())
        finally:
            MODULE.MlxAudioBackend = original


if __name__ == "__main__":
    unittest.main()
