"""Verify an encrypted snapshot or restore it to an empty local test database.

Install scripts/requirements-restore.txt. Secrets are entered at hidden prompts.
This is an application-data drill, not a full Supabase/platform restore.
"""

import argparse
import base64
import copy
from datetime import datetime
import getpass
import json
from pathlib import Path
import re
import sys
import uuid
import warnings
import zipfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"JAGBK1\n"
MAX_BYTES = 128 * 1024 * 1024
TABLES = (
    "profiles",
    "applications",
    "application_events",
    "career_profiles",
    "saved_searches",
)
COLUMNS = {
    "profiles": "id email full_name country date_of_birth password_hash created_at "
    "session_version email_verified_at requires_verification onboarding_complete auth_user_id",
    "applications": "id user_id job_title company_name company_website location source_url "
    "source date_applied status notes salary_min salary_max salary_currency salary_period "
    "contact_person deadline reminder_date email_reminder email_reminder_sent_at created_at "
    "updated_at reminder_auto deleted_at",
    "application_events": "id application_id event_type old_value new_value note created_at",
    "career_profiles": "user_id verified_text updated_at",
    "saved_searches": "id user_id name filters email_alert last_checked_at seen_ids created_at",
}

# Reviewed against column/constraint/index metadata on 21 October 2026.
# This deliberately excludes platform extensions, cron jobs and delivery queues.
SCHEMA = """
CREATE TABLE public.profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    full_name text NOT NULL,
    country text NOT NULL,
    date_of_birth date,
    password_hash text NOT NULL,
    created_at timestamptz DEFAULT now(),
    session_version integer NOT NULL DEFAULT 1,
    email_verified_at timestamptz,
    requires_verification boolean NOT NULL DEFAULT false,
    onboarding_complete boolean NOT NULL DEFAULT true,
    auth_user_id uuid
);
CREATE UNIQUE INDEX profiles_email_casefold ON public.profiles (lower(email));
CREATE TABLE public.applications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    job_title text NOT NULL, company_name text NOT NULL,
    company_website text NOT NULL DEFAULT '', location text NOT NULL DEFAULT '',
    source_url text NOT NULL DEFAULT '', source text NOT NULL DEFAULT 'manual',
    date_applied date,
    status text NOT NULL DEFAULT 'started'
        CHECK (status IN ('started','applied','interview','offer','rejected','ghosted')),
    notes text NOT NULL DEFAULT '', salary_min numeric, salary_max numeric,
    salary_currency text NOT NULL DEFAULT '', salary_period text NOT NULL DEFAULT '',
    contact_person text NOT NULL DEFAULT '', deadline date, reminder_date date,
    email_reminder boolean NOT NULL DEFAULT false,
    email_reminder_sent_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    reminder_auto boolean NOT NULL DEFAULT true, deleted_at timestamptz
);
CREATE INDEX applications_user_date ON public.applications (user_id,date_applied DESC);
CREATE INDEX applications_due_reminders ON public.applications (reminder_date)
    WHERE email_reminder AND email_reminder_sent_at IS NULL
    AND status = 'started' AND deleted_at IS NULL;
CREATE TABLE public.application_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id uuid NOT NULL REFERENCES public.applications(id) ON DELETE CASCADE,
    event_type text NOT NULL, old_value text, new_value text, note text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX application_events_application_date
    ON public.application_events (application_id,created_at DESC);
CREATE TABLE public.career_profiles (
    user_id uuid PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
    verified_text text NOT NULL DEFAULT '', updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE public.saved_searches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    name text NOT NULL, filters jsonb NOT NULL,
    email_alert boolean NOT NULL DEFAULT false, last_checked_at timestamptz,
    seen_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX saved_searches_owner ON public.saved_searches (user_id,created_at DESC);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.career_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_searches ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.profiles,public.applications,public.application_events,
    public.career_profiles,public.saved_searches FROM PUBLIC;
"""

# Install after importing historical events to avoid creating duplicate events.
EVENT_TRIGGER = """
CREATE FUNCTION public.record_application_event() RETURNS trigger
LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO public.application_events(application_id,event_type,new_value)
        VALUES (new.id,'created',new.status);
    ELSE
        IF old.status IS DISTINCT FROM new.status THEN
            INSERT INTO public.application_events(application_id,event_type,old_value,new_value)
            VALUES (new.id,'status_change',old.status,new.status);
        END IF;
        IF old.notes IS DISTINCT FROM new.notes THEN
            INSERT INTO public.application_events(application_id,event_type,note)
            VALUES (new.id,'note',new.notes);
        END IF;
    END IF;
    RETURN new;
END $$;
REVOKE ALL ON FUNCTION public.record_application_event() FROM PUBLIC;
CREATE TRIGGER application_event_log AFTER INSERT OR UPDATE ON public.applications
    FOR EACH ROW EXECUTE FUNCTION public.record_application_event();
"""


class RestoreError(ValueError):
    """A message safe to show without private records or credentials."""


def validate_target(database, port):
    if not isinstance(database, str) or not re.fullmatch(
        r"zag_restore_test_[a-z0-9_]{1,40}", database
    ):
        raise RestoreError("Use a database name beginning zag_restore_test_.")
    if type(port) is not int or not 1 <= port <= 65535:
        raise RestoreError("Invalid local PostgreSQL port.")


def validate_snapshot(snapshot):
    if (
        not isinstance(snapshot, dict)
        or type(snapshot.get("format")) is not int
        or snapshot["format"] != 1
        or not isinstance(snapshot.get("tables"), dict)
        or set(snapshot["tables"]) != set(TABLES)
    ):
        raise RestoreError("Incomplete or unsupported application backup.")
    try:
        datetime.fromisoformat(snapshot["created_at"].replace("Z", "+00:00"))
        keys = {}
        for table in TABLES:
            rows = snapshot["tables"][table]
            if not isinstance(rows, list):
                raise RestoreError("Invalid backup table structure.")
            expected = set(COLUMNS[table].split())
            primary = "user_id" if table == "career_profiles" else "id"
            identifiers = set()
            for row in rows:
                if not isinstance(row, dict) or set(row) != expected:
                    raise RestoreError(
                        "Backup columns differ from the recovery schema."
                    )
                identifier = str(uuid.UUID(row[primary]))
                if identifier in identifiers:
                    raise RestoreError("Duplicate backup record identifier.")
                identifiers.add(identifier)
                if table == "profiles" and (
                    type(row["session_version"]) is not int
                    or not 1 <= row["session_version"] < 2_147_483_647
                ):
                    raise RestoreError("Invalid account session version.")
            keys[table] = identifiers
        for table in ("applications", "career_profiles", "saved_searches"):
            if any(
                str(uuid.UUID(row["user_id"])) not in keys["profiles"]
                for row in snapshot["tables"][table]
            ):
                raise RestoreError("Backup has an orphaned account record.")
        if any(
            str(uuid.UUID(row["application_id"])) not in keys["applications"]
            for row in snapshot["tables"]["application_events"]
        ):
            raise RestoreError("Backup has an orphaned application event.")
    except (KeyError, TypeError, AttributeError, ValueError) as error:
        if isinstance(error, RestoreError):
            raise
        raise RestoreError("Invalid backup structure or field value.") from None
    return {table: len(snapshot["tables"][table]) for table in TABLES}


def read_snapshot(path, encoded_key):
    try:
        encryption_key = base64.b64decode(encoded_key.strip(), validate=True)
        if len(encryption_key) != 32:
            raise RestoreError("The saved encryption key must decode to 32 bytes.")
        path = Path(path)
        if path.stat().st_size > MAX_BYTES:
            raise RestoreError("Backup exceeds the 128 MiB restore-drill limit.")
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as archive:
                entries = archive.infolist()
                if len(entries) != 1 or entries[0].filename != "application-backup.enc":
                    raise RestoreError(
                        "Expected a ZIP containing only application-backup.enc."
                    )
                if entries[0].file_size > MAX_BYTES:
                    raise RestoreError(
                        "Backup exceeds the 128 MiB restore-drill limit."
                    )
                with archive.open(entries[0]) as source:
                    ciphertext = source.read(MAX_BYTES + 1)
        else:
            with path.open("rb") as source:
                ciphertext = source.read(MAX_BYTES + 1)
        if len(ciphertext) > MAX_BYTES:
            raise RestoreError("Backup exceeds the 128 MiB restore-drill limit.")
        if not ciphertext.startswith(MAGIC) or len(ciphertext) < len(MAGIC) + 28:
            raise RestoreError("Unknown encrypted backup format.")
        offset = len(MAGIC)
        plaintext = AESGCM(encryption_key).decrypt(
            ciphertext[offset : offset + 12], ciphertext[offset + 12 :], MAGIC
        )
        snapshot = json.loads(plaintext)
        validate_snapshot(snapshot)
        return snapshot
    except InvalidTag:
        raise RestoreError(
            "The key does not decrypt this backup, or the file was changed."
        ) from None
    except RestoreError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile, ValueError, UnicodeError):
        raise RestoreError(
            "Could not read the backup or decode the saved encryption key."
        ) from None


def restore_snapshot(snapshot, database, password, port=5432):
    validate_target(database, port)
    counts = validate_snapshot(snapshot)
    try:
        import psycopg
        from psycopg import sql
        from psycopg.types.json import Jsonb
    except ImportError:
        raise RestoreError("Install scripts/requirements-restore.txt first.") from None
    try:
        # No DSN, host option, .env import or connection to snapshot['source'].
        with psycopg.connect(
            host="127.0.0.1",
            hostaddr="127.0.0.1",
            port=port,
            dbname=database,
            user="postgres",
            password=password,
            connect_timeout=10,
            sslmode="disable",
            client_encoding="UTF8",
            options="-c search_path=pg_catalog",
            application_name="jobs-ac-ghana-local-restore-drill",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(),host(inet_server_addr())")
                if cursor.fetchone() != (database, "127.0.0.1"):
                    raise RestoreError(
                        "Restore destination is not the expected local test database."
                    )
                cursor.execute("SET LOCAL statement_timeout = '60s'")
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
                        AND c.relkind IN ('r','p','v','m','S','f')
                    )
                """)
                if cursor.fetchone()[0]:
                    raise RestoreError(
                        "The test database contains objects; nothing was overwritten."
                    )
                cursor.execute(SCHEMA)
                for table in TABLES:
                    identifier = sql.Identifier("public", table)
                    cursor.execute(
                        sql.SQL(
                            "INSERT INTO {} SELECT * FROM jsonb_populate_recordset(NULL::{},%s)"
                        ).format(identifier, identifier),
                        (Jsonb(snapshot["tables"][table]),),
                    )
                cursor.execute(
                    "UPDATE public.profiles SET session_version=session_version+1"
                )
                expected = copy.deepcopy(snapshot["tables"])
                for row in expected["profiles"]:
                    row["session_version"] += 1
                for table in TABLES:
                    identifier = sql.Identifier("public", table)
                    cursor.execute(
                        sql.SQL("""
                            WITH expected AS (
                                SELECT * FROM jsonb_populate_recordset(NULL::{},%s)
                            ), differences AS (
                                (SELECT * FROM {} EXCEPT ALL SELECT * FROM expected)
                                UNION ALL
                                (SELECT * FROM expected EXCEPT ALL SELECT * FROM {})
                            ) SELECT EXISTS (SELECT 1 FROM differences)
                        """).format(identifier, identifier, identifier),
                        (Jsonb(expected[table]),),
                    )
                    if cursor.fetchone()[0]:
                        raise RestoreError(
                            "Restored values differ; the restore was rolled back."
                        )
                cursor.execute(EVENT_TRIGGER)
        return {
            "restore_verified": True,
            "record_counts": counts,
            "snapshot_session_versions_advanced": True,
        }
    except psycopg.Error:
        raise RestoreError(
            "Local restore failed. No restore changes were committed. "
            "Check the local database, password, port and recovery-schema compatibility."
        ) from None


def hidden_prompt(label):
    if not sys.stdin.isatty():
        raise RestoreError(
            "Run interactively in PowerShell to use hidden secret prompts."
        )
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            return getpass.getpass(label)
        except getpass.GetPassWarning:
            raise RestoreError("This terminal cannot hide secret input.") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "file", help="Downloaded encrypted ZIP or application-backup.enc"
    )
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--database", help="Existing empty zag_restore_test_... database"
    )
    parser.add_argument("--port", type=int, default=5432)
    args = parser.parse_args()
    try:
        if not args.verify_only:
            validate_target(args.database or "", args.port)
        snapshot = read_snapshot(
            args.file, hidden_prompt("Saved backup encryption key: ")
        )
        if args.verify_only:
            result = {
                "encrypted_backup_verified": True,
                "record_counts": validate_snapshot(snapshot),
            }
        else:
            result = restore_snapshot(
                snapshot,
                args.database,
                hidden_prompt("Local PostgreSQL password: "),
                args.port,
            )
        print(json.dumps(result))
        return 0
    except RestoreError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("Restore cancelled.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
