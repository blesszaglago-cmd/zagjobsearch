"""Private application records and account profile access."""

import re
from datetime import date, timedelta, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from database.supabase_client import supabase
from sessions import current_user, issue_session

router = APIRouter()


class Application(BaseModel):
    job_title: str = Field(min_length=1, max_length=250)
    company_name: str = Field(min_length=1, max_length=250)
    company_website: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=250)
    source_url: str = Field(default="", max_length=2000)
    source: str = Field(default="manual", max_length=100)
    date_applied: date | None = None
    status: Literal[
        "started", "applied", "interview", "offer", "rejected", "ghosted"
    ] = "started"
    notes: str = Field(default="", max_length=10000)
    salary_min: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    salary_max: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    salary_currency: str = Field(default="", max_length=10)
    salary_period: str = Field(default="", max_length=30)
    contact_person: str = Field(default="", max_length=250)
    deadline: date | None = None
    reminder_date: date | None = None
    email_reminder: bool = False
    reminder_auto: bool = True

    @field_validator(
        "job_title",
        "company_name",
        "company_website",
        "location",
        "source_url",
        "source",
        "salary_currency",
        "salary_period",
        "contact_person",
        mode="before",
    )
    @classmethod
    def trim_fields(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def valid_salary(self):
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("The maximum salary must be at least the minimum salary.")
        return self

    @field_validator("source_url", "company_website")
    @classmethod
    def safe_url(cls, value):
        if value:
            parsed = urlsplit(value)
            if (
                parsed.scheme not in ("https", "http")
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or "\\" in value
                or any(ord(c) < 33 for c in value)
            ):
                raise ValueError(
                    "Use a complete http or https link without embedded credentials."
                )
            _ = parsed.port  # Reject malformed ports before a browser renders the link.
        return value

    def record(self):
        data = self.model_dump(mode="json")
        if self.status == "applied" and not self.date_applied:
            data["date_applied"] = date.today().isoformat()
        if self.deadline and self.reminder_auto:
            data["reminder_date"] = (self.deadline - timedelta(days=2)).isoformat()
        return data


@router.get("/account/me")
def me(user=Depends(current_user)):
    result = (
        supabase.table("profiles")
        .select(
            "id,email,full_name,country,email_verified_at,onboarding_complete,auth_user_id"
        )
        .eq("id", user)
        .execute()
    )
    if not result.data:
        raise HTTPException(401, "Account not found.")
    p = result.data[0]
    p["auth_provider"] = "google" if p.pop("auth_user_id", None) else "password"
    return p


@router.get("/account/applications")
def applications(page: int = 1, user=Depends(current_user)):
    from account_security import all_applications

    # Explicit export/all helper removes the previous silent 500-record cap.
    rows = all_applications(user)
    return {"applications": rows, "total": len(rows)}


@router.post("/account/applications")
def add_application(data: Application, user=Depends(current_user)):
    p = (
        supabase.table("profiles")
        .select("onboarding_complete,email_verified_at")
        .eq("id", user)
        .execute()
        .data
    )
    if not p or not p[0].get("onboarding_complete", True):
        raise HTTPException(403, "Complete your account setup in Settings first.")
    if data.email_reminder:
        from mailer import email_enabled

        if not email_enabled() or not p[0].get("email_verified_at"):
            raise HTTPException(
                400,
                "Email reminders need a configured email service and a verified email address.",
            )
    if data.source_url:
        existing = (
            supabase.table("applications")
            .select("*")
            .eq("user_id", user)
            .eq("source_url", data.source_url)
            .eq("job_title", data.job_title)
            .eq("company_name", data.company_name)
            .is_("deleted_at", "null")
            .limit(1)
            .execute()
            .data
        )
        if existing:
            return existing[0]
    return (
        supabase.table("applications")
        .insert({**data.record(), "user_id": user})
        .execute()
        .data[0]
    )


@router.put("/account/applications/{application_id}")
def update_application(
    application_id: UUID, data: Application, user=Depends(current_user)
):
    application_id = str(application_id)
    existing = (
        supabase.table("applications")
        .select("reminder_date,email_reminder")
        .eq("id", application_id)
        .eq("user_id", user)
        .is_("deleted_at", "null")
        .execute()
        .data
    )
    if not existing:
        raise HTTPException(404, "Application not found.")
    if data.email_reminder:
        from mailer import email_enabled

        p = (
            supabase.table("profiles")
            .select("email_verified_at")
            .eq("id", user)
            .execute()
            .data
        )
        if not email_enabled() or not p or not p[0].get("email_verified_at"):
            raise HTTPException(
                400,
                "Verify your email and enable the email service before requesting reminders.",
            )
    payload = {**data.record(), "updated_at": datetime.now(timezone.utc).isoformat()}
    if payload["reminder_date"] != existing[0].get("reminder_date") or payload[
        "email_reminder"
    ] != existing[0].get("email_reminder"):
        payload["email_reminder_sent_at"] = None
    result = (
        supabase.table("applications")
        .update(payload)
        .eq("id", application_id)
        .eq("user_id", user)
        .is_("deleted_at", "null")
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Application not found.")
    return result.data[0]


@router.delete("/account/applications/{application_id}")
def delete_application(application_id: UUID, user=Depends(current_user)):
    application_id = str(application_id)
    result = (
        supabase.table("applications")
        .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", application_id)
        .eq("user_id", user)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Application not found.")
    return {"deleted": True, "undo_available": True}


@router.post("/account/applications/{application_id}/restore")
def restore_application(application_id: UUID, user=Depends(current_user)):
    application_id = str(application_id)
    result = (
        supabase.table("applications")
        .update({"deleted_at": None})
        .eq("id", application_id)
        .eq("user_id", user)
        .execute()
    )
    if not result.data:
        raise HTTPException(404, "Application not found")
    return {"restored": True}


@router.get("/account/applications/{application_id}/events")
def events(application_id: UUID, user=Depends(current_user)):
    application_id = str(application_id)
    owns = (
        supabase.table("applications")
        .select("id")
        .eq("id", application_id)
        .eq("user_id", user)
        .is_("deleted_at", "null")
        .execute()
    )
    if not owns.data:
        raise HTTPException(404, "Application not found.")
    return {
        "events": supabase.table("application_events")
        .select("*")
        .eq("application_id", application_id)
        .order("created_at", desc=True)
        .execute()
        .data
    }


class Profile(BaseModel):
    verified_text: str = Field(max_length=30000)


@router.get("/account/profile")
def get_profile(user=Depends(current_user)):
    raise HTTPException(
        410,
        "CV assistance has been retired. Delete previously saved profile text in account settings.",
    )


@router.put("/account/profile")
def save_profile(data: Profile, user=Depends(current_user)):
    raise HTTPException(
        410, "CV assistance has been retired. No new profile text is accepted."
    )


@router.delete("/account/profile")
def delete_profile(user=Depends(current_user)):
    supabase.table("career_profiles").delete().eq("user_id", user).execute()
    return {"deleted": True}
