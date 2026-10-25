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

    def test_source_progress_migration_preserves_private_table_access_and_bounds_json(
        self,
    ):
        from pathlib import Path
        from psycopg.types.json import Jsonb

        with self.connect() as connection:
            connection.execute(
                """
                do $$ begin
                  if not exists(select 1 from pg_roles where rolname='anon') then create role anon; end if;
                  if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
                  if not exists(select 1 from pg_roles where rolname='service_role') then create role service_role; end if;
                end $$;
                create table public.catalogue_refresh(id integer primary key);
                alter table public.catalogue_refresh enable row level security;
                grant all on public.catalogue_refresh to service_role;
                insert into public.catalogue_refresh(id) values(1);
            """
            )
            migration = (
                Path(__file__).resolve().parents[2]
                / "supabase/migrations/20261025041956_source_progress_queue.sql"
            )
            connection.execute(migration.read_text())
            self.assertEqual(
                connection.execute(
                    "select source_progress from public.catalogue_refresh where id=1"
                ).fetchone()[0],
                {},
            )
            progress = {
                "version": 1,
                "pending": {"jobweb-ghana": ["https://jobwebghana.com/jobs/test/"]},
                "hosts": {},
            }
            connection.execute(
                "update public.catalogue_refresh set source_progress=%s where id=1",
                (Jsonb(progress),),
            )
            self.assertEqual(
                connection.execute(
                    "select source_progress from public.catalogue_refresh where id=1"
                ).fetchone()[0],
                progress,
            )
            for invalid in [[], {"large": "x" * 1048576}]:
                with self.assertRaises(self.psycopg.errors.CheckViolation):
                    connection.execute(
                        "update public.catalogue_refresh set source_progress=%s where id=1",
                        (Jsonb(invalid),),
                    )
            for role in ["anon", "authenticated"]:
                self.assertFalse(
                    connection.execute(
                        "select has_column_privilege(%s,'public.catalogue_refresh','source_progress','SELECT')",
                        (role,),
                    ).fetchone()[0]
                )
            self.assertTrue(
                connection.execute(
                    "select has_column_privilege('service_role','public.catalogue_refresh','source_progress','UPDATE')"
                ).fetchone()[0]
            )
            self.assertTrue(
                connection.execute(
                    "select relrowsecurity from pg_class where oid='public.catalogue_refresh'::regclass"
                ).fetchone()[0]
            )

    def test_academic_catalogue_migration_filters_windows_and_privileges(self):
        from datetime import datetime, timedelta, timezone
        from pathlib import Path
        from psycopg.types.json import Jsonb

        with self.connect() as connection:
            connection.execute(
                """
                do $$ begin
                  if not exists(select 1 from pg_roles where rolname='anon') then create role anon; end if;
                  if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
                  if not exists(select 1 from pg_roles where rolname='service_role') then create role service_role; end if;
                end $$;
                create table public.job_catalogue(
                  id text primary key, source_key text, payload jsonb,
                  status text default 'active', first_seen_at timestamptz default now(),
                  last_checked_at timestamptz default now(), deadline timestamptz
                );
                alter table public.job_catalogue enable row level security;
            """
            )
            migration = (
                Path(__file__).resolve().parents[2]
                / "supabase/migrations/20261022223645_academic_opportunity_filters.sql"
            )
            connection.execute(migration.read_text())
            connection.execute(
                (
                    migration.parent / "20261023145423_standalone_pay_period_filter.sql"
                ).read_text()
            )
            now = datetime.now(timezone.utc)
            for identity, provider, window, deadline in [
                ("dated", "university", "deadline", now + timedelta(days=2)),
                ("rolling", "university", "rolling", None),
                ("unknown", "university", "not_provided", None),
                ("expired", "authority", "deadline", now - timedelta(days=2)),
            ]:
                payload = {
                    "id": identity,
                    "title": "Research funding",
                    "company": "Test provider",
                    "description": "An eligible academic call",
                    "category": "scholarships",
                    "job_type": "research-grant",
                    "study_levels": [],
                    "application_window": window,
                    "check_url": "https://example.com/internal-check",
                }
                connection.execute(
                    "insert into public.job_catalogue(id,source_key,payload,deadline) values(%s,%s,%s,%s)",
                    (identity, provider, Jsonb(payload), deadline),
                )

            def search(**filters):
                return connection.execute(
                    "select public.search_ghana_catalogue(%s)",
                    (Jsonb({"category": "scholarships", **filters}),),
                ).fetchone()[0]

            opened = search()
            self.assertEqual({j["id"] for j in opened["jobs"]}, {"dated", "rolling"})
            self.assertEqual(
                opened["scholarship_counts"], {"open": 2, "unconfirmed": 1, "closed": 1}
            )
            self.assertTrue(all(j["can_apply"] for j in opened["jobs"]))
            self.assertTrue(all("check_url" not in j for j in opened["jobs"]))
            self.assertEqual(search(availability="all")["total"], 4)
            self.assertEqual(search(availability="all", source="authority")["total"], 1)
            self.assertEqual(search(job_type="fellowship")["total"], 0)
            self.assertEqual(search(source="' OR true --")["total"], 0)
            self.assertEqual(
                search(availability="unconfirmed")["jobs"][0]["id"], "unknown"
            )
            for role, expected in [
                ("anon", False),
                ("authenticated", False),
                ("service_role", True),
            ]:
                self.assertEqual(
                    connection.execute(
                        "select has_function_privilege(%s,'public.search_ghana_catalogue(jsonb)','execute')",
                        (role,),
                    ).fetchone()[0],
                    expected,
                )
            self.assertFalse(
                connection.execute(
                    "select prosecdef from pg_proc where oid='public.search_ghana_catalogue(jsonb)'::regprocedure"
                ).fetchone()[0]
            )
            for identity, currency, period, minimum, maximum in [
                ("ghs-month", "GHS", "month", 1000, 2000),
                ("ghs-year", "GHS", "year", 12000, 24000),
                ("usd-month", "USD", "month", 3000, 4000),
                ("unstated-pay", "", "", None, None),
            ]:
                connection.execute(
                    "insert into public.job_catalogue(id,source_key,payload) values(%s,%s,%s)",
                    (
                        identity,
                        "employer",
                        Jsonb(
                            {
                                "id": identity,
                                "title": (
                                    "Sr. Analyst"
                                    if identity == "ghs-year"
                                    else "Analyst"
                                ),
                                "category": "jobs",
                                "experience": "unspecified",
                                "salary_currency": currency,
                                "salary_period": period,
                                "salary_min": minimum,
                                "salary_max": maximum,
                            }
                        ),
                    ),
                )
            connection.execute(
                (
                    migration.parent / "20261023145423_standalone_pay_period_filter.sql"
                ).read_text()
            )
            self.assertEqual(search(category="jobs")["total"], 4)
            yearly = search(category="jobs", salary_period="year")["jobs"]
            self.assertEqual(yearly[0]["experience"], "senior")
            monthly = search(category="jobs", salary_period="month")["jobs"]
            self.assertEqual(monthly[0]["experience"], "unspecified")
            self.assertEqual(
                [
                    j["id"]
                    for j in search(category="jobs", salary_period="month")["jobs"]
                ],
                ["ghs-month"],
            )
            self.assertEqual(
                [
                    j["id"]
                    for j in search(
                        category="jobs", salary_period="month", salary_currency="USD"
                    )["jobs"]
                ],
                ["usd-month"],
            )
            self.assertEqual(
                [
                    j["id"]
                    for j in search(category="jobs", salary_period="year")["jobs"]
                ],
                ["ghs-year"],
            )
            self.assertEqual(search(category="jobs", salary_period="hour")["total"], 0)
            self.assertEqual(search(category="jobs", salary_min="10000")["total"], 1)
            self.assertEqual(
                search(
                    category="jobs",
                    salary_period="month",
                    salary_min="1500",
                    salary_max="2500",
                )["total"],
                1,
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
