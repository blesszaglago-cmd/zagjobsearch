"""Private leased email outbox. Delivery is recorded only after SMTP succeeds."""

import time
import logging
import os
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from database.supabase_client import supabase


def email_enabled():
    return all(
        os.getenv(k) for k in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]
    )


def smtp_failure(error):
    """Describe a failure without retaining provider replies or credentials."""
    if isinstance(error, smtplib.SMTPAuthenticationError):
        problem = "smtp_authentication_failed"
    elif isinstance(error, ssl.SSLCertVerificationError):
        problem = "smtp_certificate_failed"
    elif isinstance(error, TimeoutError):
        problem = "smtp_timeout"
    elif isinstance(error, smtplib.SMTPResponseException):
        problem = "smtp_provider_rejected"
    elif isinstance(error, OSError):
        problem = "smtp_connection_failed"
    elif isinstance(error, (KeyError, ValueError)):
        problem = "smtp_configuration_invalid"
    else:
        problem = "smtp_delivery_failed"
    result = {"problem": problem}
    code = getattr(error, "smtp_code", None)
    if isinstance(code, int):
        result["smtp_code"] = code
    return result


def open_smtp():
    host = os.environ["SMTP_HOST"].strip()
    password = os.environ["SMTP_PASSWORD"]
    # Google displays its generated password in four groups. Accept that paste
    # format without altering passwords belonging to another SMTP provider.
    if host.casefold() == "smtp.gmail.com":
        compact = "".join(password.split())
        if len(compact) == 16 and compact.isascii() and compact.isalpha():
            password = compact
    connection = smtplib.SMTP_SSL(
        host,
        int(os.getenv("SMTP_PORT", "465").strip()),
        timeout=8,
        context=ssl.create_default_context(),
    )
    try:
        connection.login(os.environ["SMTP_USER"].strip(), password)
        return connection
    except Exception:
        try:
            connection.close()
        except Exception:
            pass
        raise


def check_email_connection():
    """Authenticate without sending mail. Only the private operations API uses it."""
    if not email_enabled():
        return {"configured": False, "authenticated": False}
    try:
        connection = open_smtp()
    except Exception as error:
        return {"configured": True, "authenticated": False, **smtp_failure(error)}
    try:
        connection.quit()
    except Exception:
        try:
            connection.close()
        except Exception:
            pass
    return {"configured": True, "authenticated": True}


def enqueue(
    key, recipient, subject, body, user_id=None, application_id=None, expires_at=None
):
    existing = (
        supabase.table("email_outbox")
        .select("id")
        .eq("dedupe_key", key)
        .limit(1)
        .execute()
        .data
    )
    if existing:
        return existing[0]["id"]
    row = {
        "dedupe_key": key,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "user_id": user_id,
        "application_id": application_id,
        "expires_at": expires_at,
    }
    try:
        return supabase.table("email_outbox").insert(row).execute().data[0]["id"]
    except Exception:
        rows = (
            supabase.table("email_outbox")
            .select("id")
            .eq("dedupe_key", key)
            .limit(1)
            .execute()
            .data
        )
        if rows:
            return rows[0]["id"]
        raise


def deliver(delivery_id=None, batch_size=100):
    if not email_enabled():
        return {"sent": 0, "failed": 0, "configured": False}
    claimed = (
        supabase.rpc(
            "claim_email_outbox",
            {"batch_size": min(batch_size, 100), "wanted_id": delivery_id},
        )
        .execute()
        .data
    )
    sent, failed = 0, 0
    started = time.monotonic()
    if not claimed:
        return {"sent": 0, "failed": 0, "configured": True}
    connection_failure = None
    try:
        connection = open_smtp()
    except Exception as error:
        connection_failure = smtp_failure(error)
        connection = None
    try:
        for index, item in enumerate(claimed):
            if time.monotonic() - started > 110:
                remaining = [row["id"] for row in claimed[index:]]
                supabase.table("email_outbox").update(
                    {"status": "queued", "claimed_at": None}
                ).in_("id", remaining).execute()
                break
            now = datetime.now(timezone.utc)
            try:
                if connection is None:
                    raise RuntimeError("Email provider unavailable")
                if item["dedupe_key"].startswith("account:"):
                    token = (
                        supabase.table("account_tokens")
                        .select("used_at,expires_at")
                        .eq("token_hash", item["dedupe_key"].split(":", 1)[1])
                        .execute()
                        .data
                    )
                    if (
                        not token
                        or token[0].get("used_at")
                        or token[0]["expires_at"] < now.isoformat()
                    ):
                        supabase.table("email_outbox").update(
                            {"status": "cancelled", "claimed_at": None}
                        ).eq("id", item["id"]).execute()
                        continue
                if item.get("application_id"):
                    apps = (
                        supabase.table("applications")
                        .select(
                            "status,email_reminder,deadline,reminder_date,deleted_at"
                        )
                        .eq("id", item["application_id"])
                        .execute()
                        .data
                    )
                    if (
                        not apps
                        or apps[0].get("deleted_at")
                        or not apps[0]["email_reminder"]
                        or apps[0]["status"] != "started"
                        or (
                            apps[0].get("deadline")
                            and apps[0]["deadline"] < now.date().isoformat()
                        )
                        or not item["dedupe_key"].endswith(
                            ":" + str(apps[0].get("reminder_date"))
                        )
                    ):
                        supabase.table("email_outbox").update(
                            {"status": "cancelled", "claimed_at": None}
                        ).eq("id", item["id"]).execute()
                        continue
                if item.get("user_id") and not item["dedupe_key"].startswith(
                    "account:"
                ):
                    owners = (
                        supabase.table("profiles")
                        .select("email,email_verified_at")
                        .eq("id", item["user_id"])
                        .execute()
                        .data
                    )
                    if (
                        not owners
                        or not owners[0].get("email_verified_at")
                        or owners[0]["email"].casefold() != item["recipient"].casefold()
                    ):
                        supabase.table("email_outbox").update(
                            {"status": "cancelled", "claimed_at": None}
                        ).eq("id", item["id"]).execute()
                        continue
                if item["dedupe_key"].startswith("search:"):
                    search_id = item["dedupe_key"].split(":")[1]
                    saved = (
                        supabase.table("saved_searches")
                        .select("email_alert")
                        .eq("id", search_id)
                        .execute()
                        .data
                    )
                    if not saved or not saved[0]["email_alert"]:
                        supabase.table("email_outbox").update(
                            {"status": "cancelled", "claimed_at": None}
                        ).eq("id", item["id"]).execute()
                        continue
                message = EmailMessage()
                message["From"], message["To"], message["Subject"] = (
                    os.environ["SMTP_FROM"],
                    item["recipient"],
                    item["subject"],
                )
                message["Message-ID"] = f"<{item['id']}@jobs-ac-ghana>"
                message.set_content(item["body"])
                connection.send_message(message)
                stamp = now.isoformat()
                supabase.table("email_outbox").update(
                    {
                        "status": "sent",
                        "sent_at": stamp,
                        "claimed_at": None,
                        "last_error": None,
                    }
                ).eq("id", item["id"]).execute()
                if item.get("application_id"):
                    supabase.table("applications").update(
                        {"email_reminder_sent_at": stamp}
                    ).eq("id", item["application_id"]).execute()
                sent += 1
            except Exception as error:
                failed += 1
                delay = min(360, 5 * 2 ** min(item.get("attempts", 1), 6))
                failure = connection_failure or smtp_failure(error)
                description = failure["problem"]
                if "smtp_code" in failure:
                    description += f" ({failure['smtp_code']})"
                supabase.table("email_outbox").update(
                    {
                        "status": "failed",
                        "claimed_at": None,
                        "next_attempt_at": (now + timedelta(minutes=delay)).isoformat(),
                        "last_error": description + "; retry scheduled",
                    }
                ).eq("id", item["id"]).execute()
                logging.warning("Email delivery deferred: %s", description)
    finally:
        if connection:
            try:
                connection.quit()
            except Exception:
                pass
    return {"sent": sent, "failed": failed, "configured": True}
