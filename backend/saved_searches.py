"""Private saved searches and explicitly opted-in daily alerts."""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from uuid import UUID
from database.supabase_client import supabase
from sessions import current_user
from mailer import email_enabled, enqueue
import os

router = APIRouter()
ALLOWED = {
    "category",
    "q",
    "region",
    "town",
    "job_type",
    "experience",
    "industry",
    "study_level",
    "destination",
    "funding",
    "availability",
    "source",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_period",
}


class SavedSearch(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    filters: dict[str, str]
    email_alert: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.get("/account/saved-searches")
def searches(user=Depends(current_user)):
    return {
        "searches": supabase.table("saved_searches")
        .select("id,name,filters,email_alert,created_at")
        .eq("user_id", user)
        .order("created_at", desc=True)
        .execute()
        .data
    }


@router.post("/account/saved-searches")
def save_search(data: SavedSearch, user=Depends(current_user)):
    filters = {k: v[:200] for k, v in data.filters.items() if k in ALLOWED and v}
    from catalogue import query_catalogue

    first = query_catalogue(filters)
    if data.email_alert:
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
                "Email alerts need a configured email service and a verified address.",
            )
    count = (
        supabase.table("saved_searches")
        .select("id", count="exact", head=True)
        .eq("user_id", user)
        .execute()
        .count
        or 0
    )
    if count >= 20:
        raise HTTPException(
            400,
            "You can keep up to 20 saved searches. Delete one before adding another.",
        )
    row = (
        supabase.table("saved_searches")
        .insert(
            {
                "user_id": user,
                "name": data.name.strip(),
                "filters": filters,
                "email_alert": data.email_alert,
                "seen_ids": [j["id"] for j in first["jobs"]],
                "last_checked_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .execute()
        .data[0]
    )
    return {"id": row["id"], "saved": True}


@router.delete("/account/saved-searches/{search_id}")
def delete_search(search_id: UUID, user=Depends(current_user)):
    rows = (
        supabase.table("saved_searches")
        .delete()
        .eq("id", str(search_id))
        .eq("user_id", user)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(404, "Saved search not found")
    return {"deleted": True}


def queue_search_alerts():
    from catalogue import query_catalogue

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=23)).isoformat()
    rows = (
        supabase.table("saved_searches")
        .select("*")
        .eq("email_alert", True)
        .or_(f"last_checked_at.is.null,last_checked_at.lte.{cutoff}")
        .order("last_checked_at", nullsfirst=True)
        .limit(100)
        .execute()
        .data
    )
    queued = 0
    for saved in rows:
        p = (
            supabase.table("profiles")
            .select("email,email_verified_at")
            .eq("id", saved["user_id"])
            .execute()
            .data
        )
        if not p or not p[0].get("email_verified_at"):
            continue
        jobs = query_catalogue(saved["filters"])["jobs"]
        seen = set(saved.get("seen_ids") or [])
        fresh = [j for j in jobs if j["id"] not in seen]
        if fresh:
            root = os.getenv("FRONTEND_URL", "https://zagjobsearch.vercel.app").rstrip(
                "/"
            )
            body = (
                "New matches for your saved search: "
                + saved["name"]
                + "\n\n"
                + "\n\n".join(
                    f"{j['title']} at {j['company']}\n{j['location']}\n{root}/jobs/{j['id']}"
                    for j in fresh[:10]
                )
                + f"\n\nManage your saved searches: {root}/saved-searches"
            )
            signature = hashlib.sha256(
                json.dumps(sorted(j["id"] for j in fresh)).encode()
            ).hexdigest()[:24]
            enqueue(
                f"search:{saved['id']}:{signature}",
                p[0]["email"],
                "New Ghana opportunities for your saved search",
                body,
                saved["user_id"],
            )
            queued += 1
        supabase.table("saved_searches").update(
            {
                "last_checked_at": datetime.now(timezone.utc).isoformat(),
                "seen_ids": list(dict.fromkeys([j["id"] for j in jobs] + list(seen)))[
                    :1000
                ],
            }
        ).eq("id", saved["id"]).execute()
    return queued
