"""Signed sessions for legacy accounts. Tokens never contain provider credentials."""

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
import re
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def signing_key():
    secret = os.getenv("SESSION_SECRET") or os.getenv("SUPABASE_SECRET_KEY")
    if not secret:
        raise HTTPException(503, "Account service is not configured.")
    return hmac.new(
        secret.encode(), b"zagjobsearch/session/v1", hashlib.sha256
    ).digest()


def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def issue_session(user_id, session_version=1):
    payload = encode(
        json.dumps(
            {
                "sub": str(user_id),
                "exp": int(time.time()) + 43200,
                "aud": "zagjobsearch",
                "v": session_version,
                "iat": int(time.time()),
            }
        ).encode()
    )
    signature = encode(
        hmac.new(signing_key(), payload.encode(), hashlib.sha256).digest()
    )
    return f"{payload}.{signature}"


def verify_session(token):
    try:
        if (
            not isinstance(token, str)
            or len(token) > 2048
            or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}", token)
        ):
            raise ValueError()
        payload, signature = token.split(".")
        expected = encode(
            hmac.new(signing_key(), payload.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected, signature):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        now = time.time()
        if (
            not isinstance(data, dict)
            or data.get("aud") != "zagjobsearch"
            or not isinstance(data.get("sub"), str)
            or not 1 <= len(data["sub"]) <= 100
            or type(data.get("exp")) is not int
            or type(data.get("iat")) is not int
            or type(data.get("v")) is not int
            or data["v"] < 1
            or data["exp"] <= now
            or data["iat"] > now + 60
            or not 0 < data["exp"] - data["iat"] <= 43200
        ):
            raise ValueError()
        return data["sub"]
    except (ValueError, TypeError, KeyError, binascii.Error, json.JSONDecodeError):
        raise HTTPException(401, "Please log in again.")


def current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer), request: Request = None
):
    if not credentials:
        raise HTTPException(401, "Log in to use this feature.")
    user_id = verify_session(credentials.credentials)
    from database.supabase_client import supabase

    rows = (
        supabase.table("profiles")
        .select("id,session_version")
        .eq("id", user_id)
        .limit(1)
        .execute()
        .data
    )
    data = session_payload(credentials.credentials)
    if not rows or rows[0].get("session_version", 1) != data.get("v", 1):
        raise HTTPException(401, "This session has ended. Please log in again.")
    if request is not None:
        from security import rate_limit

        writing = request.method not in {"GET", "HEAD", "OPTIONS"}
        rate_limit(
            request,
            "private-write" if writing else "private-read",
            user_id,
            limit=30 if writing else 180,
            seconds=60,
        )
    return user_id


def session_payload(token):
    payload = token.split(".")[0]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
