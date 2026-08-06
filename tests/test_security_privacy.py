from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from trajectory_ledger.cli import run_fixture
from trajectory_ledger.core import ingest_fixture
from trajectory_ledger.replay import _invoke


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class SecurityPrivacyTests(unittest.TestCase):
    def test_unknown_value_has_no_raw_encoded_or_digest_disclosure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = json.loads((FIXTURES / "clean.json").read_text(encoding="ascii"))
            secret = "pin-0427"
            source["records"][0]["private_note"] = secret
            fixture = root / "fixture.json"
            fixture.write_text(json.dumps(source), encoding="ascii")

            records = ingest_fixture(fixture.name, root)
            artifact = json.dumps(records, sort_keys=True)
            redacted = records[1]["payload"]["redacted_fields"]["private_note"]

            self.assertEqual(set(redacted), {"classification", "byte_length", "redacted"})
            self.assertTrue(redacted["redacted"])
            self.assertNotIn(secret, artifact)
            self.assertNotIn(secret.encode().hex(), artifact)

    def test_replay_child_receives_no_ambient_credentials_or_proxy_settings(self):
        captured = {}

        def fake_run(command, **kwargs):
            captured.update(kwargs)
            return mock.Mock(returncode=0, stdout=b"", stderr=b"")

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.replay.subprocess.run", side_effect=fake_run
        ):
            with mock.patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "secret", "HTTPS_PROXY": "http://proxy.invalid"},
            ):
                _invoke(Path(directory))

        self.assertEqual(
            captured["env"],
            {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_committed_packet_is_private_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "packet"
            run_fixture(FIXTURES / "clean.json", output)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            artifacts = list(output.iterdir())
            self.assertTrue(artifacts)
            for artifact in artifacts:
                self.assertEqual(artifact.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
