"""Restore-file and destination guards without a database or real secrets."""

import base64
import copy
import io
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock
import zipfile

from restore_fixtures import backup, fixture, restore, TEST_KEY, USER


class RestoreGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "application-backup.enc"
        self.path.write_bytes(backup.seal(fixture(), TEST_KEY))
        self.encoded_key = base64.b64encode(TEST_KEY).decode()

    def test_exporter_format_and_artifact_zip_are_compatible(self):
        self.assertEqual(restore.read_snapshot(self.path, self.encoded_key), fixture())
        archive = self.path.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("application-backup.enc", self.path.read_bytes())
        self.assertEqual(restore.read_snapshot(archive, self.encoded_key), fixture())
        self.assertEqual(
            set(p.name for p in self.path.parent.iterdir()),
            {self.path.name, archive.name},
        )

    def test_wrong_or_regenerated_key_and_modified_ciphertext_fail(self):
        other = base64.b64encode(b"b" * 32).decode()
        with self.assertRaises(restore.RestoreError) as error:
            restore.read_snapshot(self.path, other)
        self.assertNotIn(other, str(error.exception))
        ciphertext = self.path.read_bytes()
        self.path.write_bytes(ciphertext[:-1] + bytes([ciphertext[-1] ^ 1]))
        with self.assertRaises(restore.RestoreError):
            restore.read_snapshot(self.path, self.encoded_key)

    def test_invalid_keys_and_plaintext_fail_without_echoing_values(self):
        for key in [
            "",
            "not-a-key",
            "\u00e9" * 44,
            base64.b64encode(b"short").decode(),
        ]:
            with self.subTest(length=len(key)), self.assertRaises(
                restore.RestoreError
            ) as error:
                restore.read_snapshot(self.path, key)
            if key:
                self.assertNotIn(key, str(error.exception))
        self.path.write_text('{"tables": {}}')
        with self.assertRaises(restore.RestoreError):
            restore.read_snapshot(self.path, self.encoded_key)

    def test_zip_traversal_extra_files_and_oversize_fail(self):
        archive = self.path.with_suffix(".zip")
        for names in [["../stolen.enc"], ["application-backup.enc", "extra.txt"]]:
            with zipfile.ZipFile(archive, "w") as output:
                for name in names:
                    output.writestr(name, self.path.read_bytes())
            with self.assertRaises(restore.RestoreError):
                restore.read_snapshot(archive, self.encoded_key)
        with mock.patch.object(restore, "MAX_BYTES", 1):
            with self.assertRaises(restore.RestoreError):
                restore.read_snapshot(self.path, self.encoded_key)

    def test_schema_changes_incomplete_tables_and_orphans_fail(self):
        original = fixture()
        mutations = []
        changed = copy.deepcopy(original)
        changed["tables"]["profiles"][0]["future_column"] = "private-value"
        mutations.append(changed)
        changed = copy.deepcopy(original)
        del changed["tables"]["career_profiles"]
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["tables"]["application_events"][0]["application_id"] = USER
        mutations.append(changed)
        changed = copy.deepcopy(original)
        changed["tables"]["applications"][0][
            "user_id"
        ] = "50000000-0000-4000-8000-000000000001"
        mutations.append(changed)
        for changed in mutations:
            with self.subTest(tables=len(changed["tables"])):
                with self.assertRaises(restore.RestoreError):
                    restore.validate_snapshot(changed)

    def test_bad_record_types_duplicates_and_versions_fail(self):
        for value in [None, [], {"format": True, "tables": {}}]:
            with self.assertRaises(restore.RestoreError):
                restore.validate_snapshot(value)
        for change in ["duplicate", "bad_timestamp", "version", "table_type"]:
            data = fixture()
            if change == "duplicate":
                data["tables"]["profiles"].append(
                    copy.deepcopy(data["tables"]["profiles"][0])
                )
            elif change == "bad_timestamp":
                data["created_at"] = None
            elif change == "version":
                data["tables"]["profiles"][0]["session_version"] = True
            else:
                data["tables"]["saved_searches"] = {}
            with self.subTest(change=change), self.assertRaises(restore.RestoreError):
                restore.validate_snapshot(data)

    def test_production_names_dsns_and_bad_ports_fail_before_driver_access(self):
        driver = mock.MagicMock()
        targets = [
            None,
            "postgres",
            "production",
            "postgresql://example.com/database",
            "zag_restore_test_a options=x",
        ]
        with mock.patch.dict("sys.modules", {"psycopg": driver}):
            for target in targets:
                with self.subTest(target=target), self.assertRaises(
                    restore.RestoreError
                ):
                    restore.restore_snapshot(fixture(), target, "unused")
            for port in [0, 65536, True, "5432"]:
                with self.subTest(port=port), self.assertRaises(restore.RestoreError):
                    restore.restore_snapshot(
                        fixture(), "zag_restore_test_unit", "unused", port
                    )
        driver.connect.assert_not_called()

    def test_noninteractive_secret_prompt_is_refused(self):
        with mock.patch.object(
            restore.sys.stdin, "isatty", return_value=False
        ), mock.patch.object(restore.getpass, "getpass") as prompt:
            with self.assertRaises(restore.RestoreError):
                restore.hidden_prompt("Key: ")
            prompt.assert_not_called()

    def test_connection_ignores_remote_environment_and_refuses_nonempty_target(self):
        driver = types.ModuleType("psycopg")
        driver.Error = RuntimeError
        driver.sql = mock.MagicMock()
        driver.connect = mock.MagicMock()
        json_types = types.ModuleType("psycopg.types.json")
        json_types.Jsonb = mock.MagicMock()
        connection = driver.connect.return_value.__enter__.return_value
        connection.__exit__.return_value = False
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [("zag_restore_test_unit", "127.0.0.1"), (True,)]
        modules = {"psycopg": driver, "psycopg.types.json": json_types}
        with mock.patch.dict("sys.modules", modules), mock.patch.dict(
            "os.environ", {"PGHOST": "unused.example", "PGHOSTADDR": "203.0.113.10"}
        ):
            with self.assertRaises(restore.RestoreError):
                restore.restore_snapshot(fixture(), "zag_restore_test_unit", "not-real")
        kwargs = driver.connect.call_args.kwargs
        self.assertEqual(kwargs["host"], "127.0.0.1")
        self.assertEqual(kwargs["hostaddr"], "127.0.0.1")
        self.assertEqual(kwargs["dbname"], "zag_restore_test_unit")
        self.assertEqual(kwargs["options"], "-c search_path=pg_catalog")
        self.assertNotIn(
            restore.SCHEMA, [call.args[0] for call in cursor.execute.call_args_list]
        )

    def test_cli_verification_prints_only_aggregate_results(self):
        output = io.StringIO()
        with mock.patch.object(
            restore.sys, "argv", ["restore", str(self.path), "--verify-only"]
        ), mock.patch.object(
            restore, "hidden_prompt", return_value=self.encoded_key
        ), mock.patch.object(
            restore.sys, "stdout", output
        ):
            self.assertEqual(restore.main(), 0)
        self.assertIn('"encrypted_backup_verified": true', output.getvalue())
        for private in [
            self.encoded_key,
            "synthetic@example.com",
            "synthetic-hash",
            "Recovery fixture",
        ]:
            self.assertNotIn(private, output.getvalue())
