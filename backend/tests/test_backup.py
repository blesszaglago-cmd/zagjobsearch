"""Encrypted backup round-trip and corruption detection without production data."""

import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest import mock
from cryptography.exceptions import InvalidTag

spec = importlib.util.spec_from_file_location(
    "backup", Path(__file__).resolve().parents[2] / "scripts" / "backup.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupTests(unittest.TestCase):
    def fixture(self):
        return {"format": 1, "tables": {name: [] for name in backup.TABLES}}

    def capture_with_key(self, credential):
        requests = []

        def respond(request, timeout):
            requests.append(request)
            return io.BytesIO(b"[]")

        with (
            mock.patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_SECRET_KEY": credential,
                },
            ),
            mock.patch.object(backup.urllib.request, "urlopen", side_effect=respond),
        ):
            snapshot = backup.capture()
        return snapshot, requests

    def test_modern_secret_uses_apikey_without_a_bearer_token(self):
        credential = "sb_secret_test_only_not_a_real_key"
        snapshot, requests = self.capture_with_key(credential)
        self.assertEqual(set(snapshot["tables"]), set(backup.TABLES))
        self.assertEqual(len(requests), len(backup.TABLES))
        for request in requests:
            headers = {name.lower(): value for name, value in request.header_items()}
            self.assertEqual(headers["apikey"], credential)
            self.assertNotIn("authorization", headers)

    def test_legacy_key_keeps_bearer_authentication(self):
        credential = "eyJtest_only.legacy.signature"
        _, requests = self.capture_with_key(credential)
        self.assertEqual(len(requests), len(backup.TABLES))
        for request in requests:
            headers = {name.lower(): value for name, value in request.header_items()}
            self.assertEqual(headers["apikey"], credential)
            self.assertEqual(headers["authorization"], f"Bearer {credential}")

    def test_invalid_keys_fail_before_http_without_echoing_the_key(self):
        invalid_keys = (
            "sb_publishable_test_only",
            "sb_secret_test_only\nInjected: header",
            "sb_secret_test_only_\N{LATIN SMALL LETTER E WITH ACUTE}",
            "",
        )
        for index, credential in enumerate(invalid_keys):
            with (
                self.subTest(configuration=index),
                mock.patch.dict(
                    os.environ,
                    {
                        "SUPABASE_URL": "https://example.supabase.co",
                        "SUPABASE_SECRET_KEY": credential,
                    },
                ),
                mock.patch.object(backup.urllib.request, "urlopen") as request,
            ):
                with self.assertRaises(ValueError) as error:
                    backup.capture()
                request.assert_not_called()
                if credential:
                    self.assertNotIn(credential, str(error.exception))

    def test_roundtrip_and_wrong_key(self):
        fixture = self.fixture()
        sealed = backup.seal(fixture, b"a" * 32)
        self.assertNotIn(b"tables", sealed)
        self.assertEqual(backup.open_snapshot(sealed, b"a" * 32), fixture)
        with self.assertRaises(InvalidTag):
            backup.open_snapshot(sealed, b"b" * 32)
        self.assertEqual(sum(backup.validate(fixture).values()), 0)

    def test_missing_tables_and_orphaned_records_fail_validation(self):
        with self.assertRaises(ValueError):
            backup.validate({"format": 1, "tables": {}})
        fixture = self.fixture()
        fixture["tables"]["applications"].append({"id": "app", "user_id": "unknown"})
        with self.assertRaises(ValueError):
            backup.validate(fixture)
