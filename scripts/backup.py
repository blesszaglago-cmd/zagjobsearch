"""Encrypted application-data snapshots. No plaintext backup is written to disk.

This is not a full PostgreSQL or Supabase Auth backup. See docs/operations.md.
"""

import argparse
import base64
import json
import os
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

TABLES = (
    "profiles",
    "applications",
    "application_events",
    "career_profiles",
    "saved_searches",
)
MAGIC = b"JAGBK1\n"


def key():
    value = base64.b64decode(os.environ["BACKUP_ENCRYPTION_KEY"], validate=True)
    if len(value) != 32:
        raise ValueError("BACKUP_ENCRYPTION_KEY must encode exactly 32 random bytes")
    return value


def seal(snapshot, encryption_key):
    nonce = secrets.token_bytes(12)
    return (
        MAGIC
        + nonce
        + AESGCM(encryption_key).encrypt(nonce, json.dumps(snapshot).encode(), MAGIC)
    )


def open_snapshot(ciphertext, encryption_key):
    if not ciphertext.startswith(MAGIC):
        raise ValueError("Unknown backup format")
    offset = len(MAGIC)
    return json.loads(
        AESGCM(encryption_key).decrypt(
            ciphertext[offset : offset + 12], ciphertext[offset + 12 :], MAGIC
        )
    )


def capture():
    url = os.environ["SUPABASE_URL"].rstrip("/")
    credential = os.environ["SUPABASE_SECRET_KEY"].strip()
    if (
        not credential
        or not credential.isascii()
        or any(ord(char) < 33 or ord(char) > 126 for char in credential)
    ):
        raise ValueError("Invalid SUPABASE_SECRET_KEY configuration")
    if credential.startswith("sb_publishable_"):
        raise ValueError("Backups require a Supabase secret or service-role key")
    headers = {"apikey": credential}
    if not credential.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {credential}"
    tables = {}
    for name in TABLES:
        rows, offset = [], 0
        while True:
            query = urllib.parse.urlencode(
                {
                    "select": "*",
                    "order": "user_id.asc" if name == "career_profiles" else "id.asc",
                    "offset": offset,
                    "limit": 500,
                }
            )
            request = urllib.request.Request(
                f"{url}/rest/v1/{name}?{query}",
                headers=headers,
            )
            with urllib.request.urlopen(request, timeout=40) as response:
                page = json.load(response)
            rows.extend(page)
            if len(page) < 500:
                break
            offset += 500
        tables[name] = rows
    return {
        "format": 1,
        "source": url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }


def validate(snapshot):
    if snapshot.get("format") != 1 or set(snapshot.get("tables", {})) != set(TABLES):
        raise ValueError("Incomplete backup")
    profiles = {r["id"] for r in snapshot["tables"]["profiles"]}
    applications = {r["id"] for r in snapshot["tables"]["applications"]}
    for table in ("applications", "career_profiles", "saved_searches"):
        if any(row["user_id"] not in profiles for row in snapshot["tables"][table]):
            raise ValueError("Orphaned workspace record")
    if any(
        row["application_id"] not in applications
        for row in snapshot["tables"]["application_events"]
    ):
        raise ValueError("Orphaned event")
    return {name: len(rows) for name, rows in snapshot["tables"].items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create", "verify"])
    parser.add_argument("file")
    args = parser.parse_args()
    if args.command == "create":
        snapshot = capture()
        counts = validate(snapshot)
        encrypted = seal(snapshot, key())
        if validate(open_snapshot(encrypted, key())) != counts:
            raise ValueError("Backup round-trip failed")
        path = Path(args.file)
        path.write_bytes(encrypted)
        path.chmod(0o600)
    else:
        counts = validate(open_snapshot(Path(args.file).read_bytes(), key()))
    print(json.dumps({"verified": True, "record_counts": counts}))


if __name__ == "__main__":
    main()
