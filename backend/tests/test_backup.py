"""Encrypted backup round-trip and corruption detection without production data."""

import importlib.util
from pathlib import Path
import unittest
from cryptography.exceptions import InvalidTag

spec = importlib.util.spec_from_file_location(
    "backup", Path(__file__).resolve().parents[2] / "scripts" / "backup.py"
)
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupTests(unittest.TestCase):
    def fixture(self):
        return {"format": 1, "tables": {name: [] for name in backup.TABLES}}

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
