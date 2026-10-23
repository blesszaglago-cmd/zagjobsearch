"""Shared rate limits and private cron authorisation."""

import hashlib
import hmac
import os
import ipaddress
import time
import logging
import base64
import json
from fastapi import HTTPException, Request
from database.supabase_client import supabase


def public_supabase_key(value):
    """Configuration mistakes must never send an administrative key to browsers."""
    if not value or not value.isascii() or any(c.isspace() for c in value):
        return ""
    if value.startswith("sb_publishable_"):
        return value
    try:
        payload = value.split(".")[1]
        claims = json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )
        if isinstance(claims, dict) and claims.get("role") == "anon":
            return value
    except (ValueError, IndexError, TypeError):
        pass
    return ""


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


def client_address(request):
    address = request.headers.get("x-zag-client-ip", "")
    stamp = request.headers.get("x-zag-client-time", "")
    signature = request.headers.get("x-zag-client-signature", "")
    secret = os.getenv("INTERNAL_PROXY_SECRET", "")
    if (
        secret
        and stamp.isascii()
        and stamp.isdigit()
        and len(stamp) <= 12
        and abs(time.time() - int(stamp)) <= 60
    ):
        expected = hmac.new(
            secret.encode(),
            "\n".join(
                [
                    "zagjobsearch/client-ip/v1",
                    stamp,
                    request.method,
                    request.url.path,
                    address,
                ]
            ).encode(),
            hashlib.sha256,
        ).hexdigest()
        if signature.isascii() and hmac.compare_digest(expected, signature):
            try:
                return str(ipaddress.ip_address(address)), True
            except ValueError:
                pass
    platform = (
        request.headers.get("x-vercel-forwarded-for", "") if os.getenv("VERCEL") else ""
    )
    try:
        return str(ipaddress.ip_address(platform)), False
    except ValueError:
        return request.client.host if request.client else "unknown", False


def rate_limit(request: Request, scope: str, subject="", limit=20, seconds=900):
    address, delegated = client_address(request)
    # Signed forwarding preserves the visitor's IP across the Next.js proxy;
    # direct API callers use the platform IP and receive the same budget.
    maximum_ip = max(50, limit * 10)
    keys = [(scope + ":ip:" + address, maximum_ip if subject else limit)]
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
            logging.warning(
                "request_limit_reached scope=%s delegated=%s", scope, delegated
            )
            raise HTTPException(
                429,
                "Too many attempts. Please try again later.",
                headers={"Retry-After": str(seconds)},
            )
