"""Private application records and account profile access."""
import re
from datetime import date, timedelta, datetime, timezone
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
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
    status: Literal["started", "applied", "interview", "offer", "rejected", "ghosted"] = "started"
    notes: str = Field(default="", max_length=10000)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="", max_length=10)
    salary_period: str = Field(default="", max_length=30)
    contact_person: str = Field(default="", max_length=250)
    deadline: date | None = None
    reminder_date: date | None = None
    email_reminder: bool = False

    @field_validator("source_url", "company_website")
    @classmethod
    def safe_url(cls, value):
        if value and (urlsplit(value).scheme not in ("https", "http") or not urlsplit(value).netloc):
            raise ValueError("Use a complete http or https link.")
        return value

    def record(self):
        data = self.model_dump(mode="json")
        if self.status == "applied" and not self.date_applied:
            data["date_applied"] = date.today().isoformat()
        if self.deadline and not self.reminder_date:
            data["reminder_date"] = (self.deadline - timedelta(days=2)).isoformat()
        return data

@router.get("/account/me")
def me(user=Depends(current_user)):
    result = supabase.table("profiles").select("id,email,full_name,country").eq("id", user).execute()
    if not result.data: raise HTTPException(401, "Account not found.")
    return result.data[0]

@router.get("/account/applications")
def applications(user=Depends(current_user)):
    return {"applications": supabase.table("applications").select("*").eq("user_id", user).order("date_applied", desc=True, nullsfirst=False).order("created_at", desc=True).limit(500).execute().data}

@router.post("/account/applications")
def add_application(data: Application, user=Depends(current_user)):
    if data.source_url:
        existing = supabase.table("applications").select("*").eq("user_id", user).eq("source_url", data.source_url).limit(1).execute().data
        if existing: return existing[0]
    return supabase.table("applications").insert({**data.record(), "user_id": user}).execute().data[0]

@router.put("/account/applications/{application_id}")
def update_application(application_id: str, data: Application, user=Depends(current_user)):
    existing = supabase.table("applications").select("reminder_date,email_reminder").eq("id", application_id).eq("user_id", user).execute().data
    if not existing: raise HTTPException(404, "Application not found.")
    payload = {**data.record(), "updated_at": datetime.now(timezone.utc).isoformat()}
    if payload["reminder_date"] != existing[0].get("reminder_date") or payload["email_reminder"] != existing[0].get("email_reminder"):
        payload["email_reminder_sent_at"] = None
    result = supabase.table("applications").update(payload).eq("id", application_id).eq("user_id", user).execute()
    if not result.data: raise HTTPException(404, "Application not found.")
    return result.data[0]

@router.delete("/account/applications/{application_id}")
def delete_application(application_id: str, user=Depends(current_user)):
    result = supabase.table("applications").delete().eq("id", application_id).eq("user_id", user).execute()
    if not result.data: raise HTTPException(404, "Application not found.")
    return {"deleted": True}

@router.get("/account/applications/{application_id}/events")
def events(application_id: str, user=Depends(current_user)):
    owns = supabase.table("applications").select("id").eq("id", application_id).eq("user_id", user).execute()
    if not owns.data: raise HTTPException(404, "Application not found.")
    return {"events": supabase.table("application_events").select("*").eq("application_id", application_id).order("created_at", desc=True).execute().data}

class Profile(BaseModel):
    verified_text: str = Field(max_length=30000)

@router.get("/account/profile")
def get_profile(user=Depends(current_user)):
    rows = supabase.table("career_profiles").select("verified_text").eq("user_id", user).execute().data
    return rows[0] if rows else {"verified_text": ""}

@router.put("/account/profile")
def save_profile(data: Profile, user=Depends(current_user)):
    supabase.table("career_profiles").upsert({"user_id": user, "verified_text": data.verified_text}, on_conflict="user_id").execute()
    return {"saved": True}

@router.delete("/account/profile")
def delete_profile(user=Depends(current_user)):
    supabase.table("career_profiles").delete().eq("user_id", user).execute()
    return {"deleted": True}
