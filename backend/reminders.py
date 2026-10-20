"""Daily reminder reconciliation with a durable retry queue."""

import os
from datetime import date
from fastapi import APIRouter, Header
from database.supabase_client import supabase
from mailer import email_enabled, enqueue, deliver
from security import require_cron

router = APIRouter()


def queue_reminders():
    today, offset, queued = date.today().isoformat(), 0, 0
    while True:
        rows = (
            supabase.table("applications")
            .select("id,user_id,job_title,company_name,deadline,reminder_date")
            .eq("email_reminder", True)
            .eq("status", "started")
            .is_("deleted_at", "null")
            .lte("reminder_date", today)
            .is_("email_reminder_sent_at", "null")
            .or_(f"deadline.is.null,deadline.gte.{today}")
            .order("id")
            .range(offset, offset + 199)
            .execute()
            .data
        )
        for item in rows:
            profile = (
                supabase.table("profiles")
                .select("email,email_verified_at")
                .eq("id", item["user_id"])
                .execute()
                .data
            )
            if not profile or not profile[0].get("email_verified_at"):
                continue
            body = f"Your reminder for {item['job_title']} at {item['company_name']} is due.\n"
            if item.get("deadline"):
                body += f"Application deadline: {item['deadline']}\n"
            body += f"\nReview your tracker: {os.getenv('FRONTEND_URL', 'https://zagjobsearch.vercel.app').rstrip('/')}/tracker\n\nYou requested this reminder. Turn it off in your application record at any time."
            enqueue(
                f"deadline:{item['id']}:{item['reminder_date']}",
                profile[0]["email"],
                "Your jobs.ac.ghana deadline reminder",
                body,
                item["user_id"],
                item["id"],
            )
            queued += 1
        if len(rows) < 200:
            return queued
        offset += 200


@router.get("/cron/reminders")
def send_reminders(authorization: str = Header(default="")):
    require_cron(authorization)
    if not email_enabled():
        return {"sent": 0, "configured": False}
    queued = queue_reminders()
    from saved_searches import queue_search_alerts

    alerts = queue_search_alerts()
    return {**deliver(), "queued_reminders": queued, "queued_alerts": alerts}
