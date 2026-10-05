"""Signed sessions for legacy accounts. Tokens never contain provider credentials."""
import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)

def signing_key():
    secret = os.getenv("SESSION_SECRET") or os.getenv("SUPABASE_SECRET_KEY")
    if not secret:
        raise HTTPException(503, "Account service is not configured.")
    return hmac.new(secret.encode(), b"zagjobsearch/session/v1", hashlib.sha256).digest()

def encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def issue_session(user_id):
    payload = encode(json.dumps({"sub": str(user_id), "exp": int(time.time()) + 43200, "aud": "zagjobsearch"}).encode())
    signature = encode(hmac.new(signing_key(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"

def verify_session(token):
    try:
        payload, signature = token.split(".")
        expected = encode(hmac.new(signing_key(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            raise ValueError()
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if data.get("aud") != "zagjobsearch" or data.get("exp", 0) <= time.time() or not data.get("sub"):
            raise ValueError()
        return data["sub"]
    except (ValueError, TypeError, KeyError, binascii.Error, json.JSONDecodeError):
        raise HTTPException(401, "Please log in again.")

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)):
    if not credentials:
        raise HTTPException(401, "Log in to use this feature.")
    return verify_session(credentials.credentials)
