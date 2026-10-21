"""Real PostgreSQL recovery tests using only a local disposable CI database."""

import copy
import csv
import io
import os
import types
import unittest
from unittest import mock
import uuid

from restore_fixtures import APPLICATION, fixture, restore, USER


@unittest.skipUnless(
    os.getenv("RESTORE_INTEGRATION_TESTS") == "1",
    "Requires disposable local PostgreSQL",
)
class RestoreDatabaseTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from psycopg import sql

        self.psycopg = psycopg
        self.sql = sql
        self.database = "zag_restore_test_" + uuid.uuid4().hex[:16]
        self.password = os.environ["RESTORE_TEST_PASSWORD"]
        control = self.connect("postgres")
        self.addCleanup(control.close)
        self.assertEqual(
            control.execute("SELECT host(inet_server_addr())").fetchone()[0],
            "127.0.0.1",
        )
        control.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                sql.Identifier(self.database)
            )
        )
        self.addCleanup(
            lambda: control.execute(
                sql.SQL("DROP DATABASE {}").format(sql.Identifier(self.database))
            )
        )

    def connect(self, database=None):
        return self.psycopg.connect(
            host="127.0.0.1",
            port=5432,
            dbname=database or self.database,
            user="postgres",
            password=self.password,
            autocommit=True,
        )

    def test_all_values_ids_history_json_and_rls_survive(self):
        data = fixture()
        result = restore.restore_snapshot(data, self.database, self.password)
        self.assertTrue(result["restore_verified"])
        self.assertEqual(
            result["record_counts"], {table: 1 for table in restore.TABLES}
        )
        self.assertEqual(data["tables"]["profiles"][0]["session_version"], 7)
        with self.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT session_version FROM public.profiles"
                ).fetchone()[0],
                8,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT job_title FROM public.applications"
                ).fetchone()[0],
                data["tables"]["applications"][0]["job_title"],
            )
            self.assertEqual(
                connection.execute(
                    "SELECT count(*) FROM public.application_events"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity"
                ).fetchone()[0],
                5,
            )
            connection.execute(
                "UPDATE public.applications SET status='interview',notes='next interview' WHERE id=%s",
                (APPLICATION,),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT count(*) FROM public.application_events"
                ).fetchone()[0],
                3,
            )
            self.assertEqual(
                connection.execute("SELECT count(*) FROM public.profiles").fetchone()[
                    0
                ],
                1,
            )

    def test_invalid_data_rolls_back_schema_and_rows(self):
        data = fixture()
        duplicate = copy.deepcopy(data["tables"]["profiles"][0])
        duplicate["id"] = str(uuid.uuid4())
        data["tables"]["profiles"].append(duplicate)
        with self.assertRaises(restore.RestoreError) as error:
            restore.restore_snapshot(data, self.database, self.password)
        self.assertNotIn("synthetic@example.com", str(error.exception))
        with self.connect() as connection:
            self.assertIsNone(
                connection.execute("SELECT to_regclass('public.profiles')").fetchone()[
                    0
                ]
            )

    def test_existing_database_is_not_overwritten(self):
        with self.connect() as connection:
            connection.execute("CREATE TABLE public.keep_me (value text)")
            connection.execute("INSERT INTO public.keep_me VALUES (%s)", ("keep this",))
        with self.assertRaises(restore.RestoreError):
            restore.restore_snapshot(fixture(), self.database, self.password)
        with self.connect() as connection:
            self.assertEqual(
                connection.execute("SELECT value FROM public.keep_me").fetchone()[0],
                "keep this",
            )
            self.assertIsNone(
                connection.execute("SELECT to_regclass('public.profiles')").fetchone()[
                    0
                ]
            )

    def test_account_login_helper_and_csv_use_recovered_records(self):
        # Exercise production helpers with restored SQL rows. This is not a browser,
        # PostgREST or Supabase Auth test; only their data lookups are substituted.
        stub = types.ModuleType("database.supabase_client")
        stub.supabase = mock.MagicMock()
        with mock.patch.dict("sys.modules", {"database.supabase_client": stub}):
            import auth
            import account_security
            import sessions
        data = fixture()
        password = "synthetic-recovery-password"
        data["tables"]["profiles"][0]["password_hash"] = auth.hash_password(password)
        restore.restore_snapshot(data, self.database, self.password)
        with self.connect() as connection:
            profile = connection.execute(
                "SELECT row_to_json(p) FROM public.profiles p WHERE id=%s", (USER,)
            ).fetchone()[0]
            applications = [
                row[0]
                for row in connection.execute(
                    "SELECT row_to_json(a) FROM public.applications a WHERE user_id=%s",
                    (USER,),
                )
            ]
        with mock.patch.object(
            auth, "find_email", return_value=profile
        ), mock.patch.dict(os.environ, {"SESSION_SECRET": "restore-ci-only-secret"}):
            login = auth.login_user(
                auth.LoginRequest(email=profile["email"], password=password)
            )
            self.assertEqual(login.user_id, USER)
            self.assertEqual(sessions.session_payload(login.access_token)["v"], 8)
        with mock.patch.object(
            account_security, "all_applications", return_value=applications
        ):
            response = account_security.export(USER)
        exported = list(csv.DictReader(io.StringIO(response.body.decode())))
        self.assertEqual(len(exported), 1)
        self.assertEqual(exported[0]["job_title"], "'" + applications[0]["job_title"])
        self.assertEqual(exported[0]["notes"], applications[0]["notes"])
