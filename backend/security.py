"""Shared rate limits and private cron authorisation."""

import hashlib
import hmac
import os
from fastapi import HTTPException, Request
from database.supabase_client import supabase


def require_cron(authorization):
    secret = os.getenv("CRON_SECRET", "")
    supplied = authorization or ""
    if not isinstance(supplied, str) or not supplied.isascii():
        raise HTTPException(401, "Not authorised")
    if secret and hmac.compare_digest(supplied, "Bearer " + secret):
        return
    if supplied.startswith("Bearer ") and 20 <= len(supplied) <= 300:
        valid = (
            supabase.rpc("verify_maintenance_key", {"candidate": supplied[7:]})
            .execute()
            .data
        )
        if valid:
            return
    raise HTTPException(401, "Not authorised")


def rate_limit(request: Request, scope: str, subject="", limit=20, seconds=900):
    address = (
        request.headers.get("x-vercel-forwarded-for")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    # Requests proxied by Next.js can share an egress IP. Keep that aggregate
    # budget generous and apply the strict threshold to each account as well.
    keys = [(scope + ":ip:" + address, max(1000, limit * 100) if subject else limit)]
    if subject:
        keys.append((scope + ":account:" + subject.strip().casefold(), limit))
    for key, maximum in keys:
        digest = hashlib.sha256(key.encode()).hexdigest()
        allowed = (
            supabase.rpc(
                "consume_request_limit",
                {"bucket": digest, "maximum": maximum, "period_seconds": seconds},
            )
            .execute()
            .data
        )
        if not allowed:
            raise HTTPException(
                429,
                "Too many attempts. Please try again later.",
                headers={"Retry-After": str(seconds)},
            )
