from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from database.supabase_client import supabase
from security import rate_limit

router = APIRouter()


class Report(BaseModel):
    reason: Literal["closed", "fraud", "broken_link", "wrong_location", "other"]
    details: str = Field(default="", max_length=2000)


@router.post("/catalogue/{job_id}/report")
def report(job_id: str, data: Report, request: Request):
    rate_limit(request, "listing-report", limit=10, seconds=86400)
    if (
        not supabase.table("job_catalogue")
        .select("id")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data
    ):
        raise HTTPException(404, "Listing not found")
    supabase.table("job_reports").insert(
        {"job_id": job_id, "reason": data.reason, "details": data.details}
    ).execute()
    return {"received": True}
