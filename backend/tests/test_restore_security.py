"""Account takeover and concurrency regressions on disposable loopback PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import time
import unittest
import uuid


@unittest.skipUnless(
    os.getenv("RESTORE_INTEGRATION_TESTS") == "1",
    "Requires disposable local PostgreSQL",
)
class AccountDatabaseTests(unittest.TestCase):
    def connect(self, database=None):
        import psycopg

        return psycopg.connect(
            host="127.0.0.1",
            hostaddr="127.0.0.1",
            port=5432,
            dbname=database or self.database,
            user="postgres",
            password=os.environ["RESTORE_TEST_PASSWORD"],
            autocommit=True,
        )

    def setUp(self):
        from psycopg import sql

        self.database = "zag_restore_test_security_" + uuid.uuid4().hex[:12]
        self.owner = uuid.uuid4()
        self.provider = uuid.uuid4()
        control = self.connect("postgres")
        self.addCleanup(control.close)
        self.assertEqual(
            control.execute("select host(inet_server_addr())").fetchone()[0],
            "127.0.0.1",
        )
        control.execute(
            sql.SQL("create database {} template template0").format(
                sql.Identifier(self.database)
            )
        )
        self.addCleanup(
            lambda: control.execute(
                sql.SQL("drop database {}").format(sql.Identifier(self.database))
            )
        )
        with self.connect() as connection:
            connection.execute("""
              do $$ begin
                if not exists(select 1 from pg_roles where rolname='anon') then create role anon; end if;
                if not exists(select 1 from pg_roles where rolname='authenticated') then create role authenticated; end if;
                if not exists(select 1 from pg_roles where rolname='service_role') then create role service_role; end if;
              end $$;
              create table public.profiles(
                id uuid primary key default gen_random_uuid(), email text not null unique,
                full_name text not null, country text not null default 'GH',date_of_birth date,
                password_hash text not null,session_version integer not null default 1,
                email_verified_at timestamptz,requires_verification boolean not null default false,
                onboarding_complete boolean not null default true,auth_user_id uuid
              );
              create table public.account_tokens(
                token_hash text primary key,user_id uuid not null references public.profiles(id),
                purpose text not null,target_email text not null,expires_at timestamptz not null,used_at timestamptz
              );
              alter table public.profiles enable row level security;
              alter table public.account_tokens enable row level security;
            """)
            migration = (
                Path(__file__).resolve().parents[2]
                / "supabase/migrations/20261023191550_atomic_account_security.sql"
            )
            connection.execute(migration.read_text())
            connection.execute(
                "insert into public.profiles(id,email,full_name,password_hash,requires_verification) values(%s,'owner@example.com','Test owner','attacker-chosen-password',true)",
                (self.owner,),
            )

    def bind(self, connection, provider=None, address="owner@example.com"):
        return connection.execute(
            "select public.bind_google_account(%s,%s,%s,%s)",
            (provider or self.provider, address, "Test owner", "!google:" + "a" * 64),
        ).fetchone()[0]

    def token(
        self,
        connection,
        digest,
        purpose="reset",
        version=None,
        target="owner@example.com",
    ):
        connection.execute(
            "insert into public.account_tokens(token_hash,user_id,purpose,target_email,expires_at,issued_session_version) values(%s,%s,%s,%s,%s,%s)",
            (
                digest,
                self.owner,
                purpose,
                target,
                datetime.now(timezone.utc) + timedelta(minutes=30),
                version,
            ),
        )

    def consume(self, digest):
        with self.connect() as connection:
            return connection.execute(
                "select public.consume_account_token(%s,'reset',%s)",
                (digest, "replacement-" + digest),
            ).fetchone()[0]

    def test_unverified_google_claim_discards_the_attackers_password_sessions_and_links(
        self,
    ):
        with self.connect() as connection:
            self.token(connection, "old-reset")
            self.token(
                connection, "old-email", "change_email", target="attacker@example.com"
            )
            result = self.bind(connection)
            self.assertEqual(result["id"], str(self.owner))
            self.assertEqual(result["session_version"], 2)
            password, verified, provider = connection.execute(
                "select password_hash,email_verified_at,auth_user_id from public.profiles where id=%s",
                (self.owner,),
            ).fetchone()
            self.assertEqual(password, "!google:" + "a" * 64)
            self.assertIsNotNone(verified)
            self.assertEqual(provider, self.provider)
            self.assertEqual(
                connection.execute(
                    "select count(*) from public.account_tokens where used_at is null"
                ).fetchone()[0],
                0,
            )
        self.assertIsNone(self.consume("old-reset"))

    def test_verified_password_is_retained_but_another_identity_cannot_replace_the_owner(
        self,
    ):
        import psycopg

        with self.connect() as connection:
            connection.execute(
                "update public.profiles set email_verified_at=now() where id=%s",
                (self.owner,),
            )
            self.bind(connection)
            self.assertEqual(
                connection.execute(
                    "select password_hash from public.profiles"
                ).fetchone()[0],
                "attacker-chosen-password",
            )
            with self.assertRaises(psycopg.Error):
                self.bind(connection, provider=uuid.uuid4())
            self.assertEqual(
                connection.execute(
                    "select auth_user_id from public.profiles"
                ).fetchone()[0],
                self.provider,
            )

    def test_provider_binding_survives_a_verified_profile_email_change(self):
        with self.connect() as connection:
            self.bind(connection)
            connection.execute(
                "update public.profiles set email='changed@example.com' where id=%s",
                (self.owner,),
            )
            result = self.bind(connection)
            self.assertEqual(result["id"], str(self.owner))
            self.assertEqual(
                connection.execute(
                    "select email,count(*) over() from public.profiles"
                ).fetchone(),
                ("changed@example.com", 1),
            )

    def test_new_google_identity_creates_only_one_workspace(self):
        with self.connect() as connection:
            first = self.bind(connection, address="new@example.com")
            second = self.bind(connection, address="new@example.com")
            self.assertEqual(first, second)
            self.assertFalse(first["onboarding_complete"])
            self.assertEqual(
                connection.execute(
                    "select count(*) from public.profiles where auth_user_id=%s",
                    (self.provider,),
                ).fetchone()[0],
                1,
            )

    def run_concurrently_behind_profile_lock(self, operations):
        with self.connect() as blocker, ThreadPoolExecutor(max_workers=2) as pool:
            blocker.execute("begin")
            blocker.execute(
                "select id from public.profiles where id=%s for update", (self.owner,)
            )
            futures = [pool.submit(operation) for operation in operations]
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    waiting = blocker.execute(
                        "select count(*) from pg_stat_activity where datname=%s and wait_event_type='Lock'",
                        (self.database,),
                    ).fetchone()[0]
                    if waiting >= 2:
                        break
                    time.sleep(0.02)
                self.assertGreaterEqual(
                    waiting, 2, "Both synthetic requests must overlap"
                )
            finally:
                blocker.execute("commit")
            return [future.result(timeout=5) for future in futures]

    def test_two_concurrent_reset_links_cannot_both_change_credentials(self):
        with self.connect() as connection:
            self.token(connection, "first")
            self.token(connection, "second")
        results = self.run_concurrently_behind_profile_lock(
            [lambda: self.consume("first"), lambda: self.consume("second")]
        )
        self.assertEqual(sum(result == self.owner for result in results), 1)
        self.assertEqual(results.count(None), 1)
        with self.connect() as connection:
            self.assertEqual(
                connection.execute(
                    "select session_version from public.profiles"
                ).fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute(
                    "select count(*) from public.account_tokens where used_at is null"
                ).fetchone()[0],
                0,
            )

    def test_concurrent_signouts_cannot_reuse_or_regress_the_session_version(self):
        def rotate():
            with self.connect() as connection:
                return connection.execute(
                    "select public.rotate_account_session(%s,1)", (self.owner,)
                ).fetchone()[0]

        self.assertCountEqual(
            self.run_concurrently_behind_profile_lock([rotate, rotate]), [2, None]
        )
        with self.connect() as connection:
            self.assertIsNone(
                connection.execute(
                    "select public.rotate_account_session(%s,1)", (self.owner,)
                ).fetchone()[0]
            )
            self.assertEqual(
                connection.execute(
                    "select session_version from public.profiles"
                ).fetchone()[0],
                2,
            )

    def test_stale_password_change_cannot_overwrite_a_reset_and_stale_email_link_is_invalid(
        self,
    ):
        with self.connect() as connection:
            self.token(connection, "reset")
        self.consume("reset")
        with self.connect() as connection:
            changed = connection.execute(
                "select public.rotate_account_session(%s,1,'attacker-chosen-password','stale-overwrite')",
                (self.owner,),
            ).fetchone()[0]
            self.assertIsNone(changed)
            self.token(
                connection,
                "stale-email",
                "change_email",
                version=1,
                target="attacker@example.com",
            )
            self.assertIsNone(
                connection.execute(
                    "select public.consume_account_token('stale-email','change_email')"
                ).fetchone()[0]
            )
            self.assertEqual(
                connection.execute(
                    "select password_hash,email from public.profiles"
                ).fetchone(),
                ("replacement-reset", "owner@example.com"),
            )

    def test_old_api_token_issuance_is_stamped_with_the_current_version(self):
        with self.connect() as connection:
            self.token(connection, "old-api")
            self.assertEqual(
                connection.execute(
                    "select issued_session_version from public.account_tokens"
                ).fetchone()[0],
                1,
            )
        self.assertEqual(self.consume("old-api"), self.owner)

    def test_account_rpcs_are_invoker_and_service_only(self):
        signatures = [
            "bind_google_account(uuid,text,text,text)",
            "rotate_account_session(uuid,integer,text,text)",
            "consume_account_token(text,text,text)",
            "stamp_account_token_version()",
        ]
        with self.connect() as connection:
            for signature in signatures:
                for role, expected in [
                    ("anon", False),
                    ("authenticated", False),
                    ("service_role", True),
                ]:
                    self.assertEqual(
                        connection.execute(
                            "select has_function_privilege(%s,%s,'execute')",
                            (role, "public." + signature),
                        ).fetchone()[0],
                        expected,
                    )
                self.assertFalse(
                    connection.execute(
                        "select prosecdef from pg_proc where oid=%s::regprocedure",
                        ("public." + signature,),
                    ).fetchone()[0]
                )
