"""Authenticated operational checks without recipient, token or password disclosure."""

from typing import Literal
from fastapi import APIRouter, Header
from database.supabase_client import supabase
from security import require_cron
from mailer import email_enabled, check_email_connection

router = APIRouter()


@router.get("/cron/email-status")
def email_status(
    authorization: str = Header(default=""), port: Literal["465", "587"] | None = None
):
    require_cron(authorization)
    return check_email_connection(int(port) if port else None)


@router.get("/cron/status")
def status(authorization: str = Header(default="")):
    require_cron(authorization)
    from catalogue import refresh_state

    s = refresh_state()
    outbox = (
        supabase.table("email_outbox")
        .select("id", count="exact", head=True)
        .in_("status", ["queued", "failed"])
        .execute()
        .count
        or 0
    )
    return {
        "protected": True,
        "email_configured": email_enabled(),
        "queued_deliveries": outbox,
        "catalogue_completed_at": s.get("completed_at"),
        "next_refresh_at": s.get("next_refresh_at"),
        "catalogue_error": s.get("last_error"),
    }
