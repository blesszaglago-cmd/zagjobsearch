"""Account recovery, verification, Google linking and self-service controls."""

import csv
import hashlib
import io
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials
import time
from pydantic import BaseModel, EmailStr, Field, field_validator
from database.supabase_client import supabase
from sessions import current_user, issue_session, bearer, session_payload
from auth import find_email, hash_password, verify_password
from mailer import email_enabled, enqueue, deliver
from security import rate_limit

router = APIRouter()


def profile(user):
    rows = supabase.table("profiles").select("*").eq("id", user).execute().data
    if not rows:
        raise HTTPException(401, "Account not found")
    return rows[0]


def require_password(user, password):
    if not verify_password(password, user["password_hash"]):
        raise HTTPException(
            403,
            "Your current password is incorrect. Recover your account if you need to set a password.",
        )


def send_account_link(user, purpose, target=None):
    if not email_enabled():
        raise HTTPException(
            503,
            "Email delivery is not configured. Contact blesszaglago@gmail.com for account help.",
        )
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    email = target or user["email"]
    supabase.table("account_tokens").insert(
        {
            "token_hash": digest,
            "user_id": user["id"],
            "purpose": purpose,
            "target_email": email,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=30)
            ).isoformat(),
        }
    ).execute()
    route = "reset-password" if purpose == "reset" else "verify-email"
    link = f"{os.getenv('FRONTEND_URL', 'https://zagjobsearch.vercel.app').rstrip('/')}/{route}#token={token}&purpose={purpose}"
    subject = (
        "Reset your jobs.ac.ghana password"
        if purpose == "reset"
        else "Verify your email for jobs.ac.ghana"
    )
    delivery = enqueue(
        f"account:{digest}",
        email,
        subject,
        f"{subject}\n\nOpen this link within 30 minutes:\n{link}\n\nIf you did not request this, ignore this email.",
        user["id"],
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
    )
    result = deliver(delivery, 1)
    if not result["sent"]:
        raise HTTPException(
            503,
            "The email provider could not send your link. Please try again shortly.",
        )


class EmailRequest(BaseModel):
    email: EmailStr
    purpose: str = "reset"


@router.post("/auth/recovery")
def recovery(data: EmailRequest, request: Request):
    rate_limit(request, "recovery", str(data.email), 3, 3600)
    if data.purpose not in ["reset", "verify"]:
        raise HTTPException(400, "Choose password recovery or email verification")
    if not email_enabled():
        raise HTTPException(
            503,
            "Email delivery is not configured. Contact blesszaglago@gmail.com for account help.",
        )
    user = find_email(data.email)
    if user:
        send_account_link(user, data.purpose)
    return {
        "message": "If an account matches that address, a link has been sent. Check your inbox and spam folder."
    }


class ConsumeToken(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    purpose: str
    password: str | None = Field(default=None, min_length=8, max_length=128)


@router.post("/auth/complete")
def complete(data: ConsumeToken, request: Request):
    rate_limit(request, "complete-token", limit=20)
    if data.purpose not in ["reset", "verify", "change_email"]:
        raise HTTPException(400, "Invalid verification request")
    if data.purpose == "reset" and not data.password:
        raise HTTPException(400, "Choose a new password")
    try:
        user = (
            supabase.rpc(
                "consume_account_token",
                {
                    "digest": hashlib.sha256(data.token.encode()).hexdigest(),
                    "token_purpose": data.purpose,
                    "new_password_hash": (
                        hash_password(data.password) if data.password else None
                    ),
                },
            )
            .execute()
            .data
        )
    except Exception:
        raise HTTPException(400, "This link could not be used. Request a fresh link.")
    if not user:
        raise HTTPException(
            400, "This link has expired or has already been used. Request a fresh link."
        )
    return {
        "message": (
            "Your password has been updated. Log in again."
            if data.purpose == "reset"
            else "Your email is verified. You can log in."
        )
    }


class GoogleRequest(BaseModel):
    access_token: str = Field(min_length=20, max_length=10000)


@router.post("/auth/google")
def google(data: GoogleRequest, request: Request):
    rate_limit(request, "google-login", limit=20)
    try:
        user = supabase.auth.get_user(data.access_token).user
        providers = (user.app_metadata or {}).get("providers", [])
        if not user.email or not user.email_confirmed_at or "google" not in providers:
            raise ValueError("Google did not confirm this email")
    except Exception:
        raise HTTPException(
            401, "Google could not confirm your identity. Please sign in again."
        )
    # A verified email change must not create a second workspace the next time
    # the same Google identity signs in with its original provider address.
    linked = (
        supabase.table("profiles")
        .select("*")
        .eq("auth_user_id", str(user.id))
        .limit(1)
        .execute()
        .data
    )
    existing = linked[0] if linked else find_email(user.email)
    if existing:
        supabase.table("profiles").update(
            {
                "email_verified_at": datetime.now(timezone.utc).isoformat(),
                "requires_verification": False,
                "auth_user_id": str(user.id),
            }
        ).eq("id", existing["id"]).execute()
    else:
        existing = (
            supabase.table("profiles")
            .insert(
                {
                    "email": user.email.casefold(),
                    "full_name": (user.user_metadata or {}).get("full_name")
                    or "Job seeker",
                    "country": "GH",
                    "date_of_birth": None,
                    "password_hash": "!google:" + secrets.token_hex(32),
                    "auth_user_id": str(user.id),
                    "email_verified_at": datetime.now(timezone.utc).isoformat(),
                    "onboarding_complete": False,
                }
            )
            .execute()
            .data[0]
        )
    return {
        "access_token": issue_session(
            existing["id"], existing.get("session_version", 1)
        ),
        "onboarding_complete": existing.get("onboarding_complete", True),
    }


@router.post("/account/logout")
def logout(user=Depends(current_user)):
    p = profile(user)
    supabase.table("profiles").update({"session_version": p["session_version"] + 1}).eq(
        "id", user
    ).execute()
    return {"logged_out": True}


class Preferences(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    country: str = Field(default="GH", min_length=2, max_length=2)
    accepted_terms: bool = False
    age_confirmed: bool = False

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value


@router.put("/account/settings")
def settings(data: Preferences, user=Depends(current_user)):
    p = profile(user)
    if not p.get("onboarding_complete") and not (
        data.accepted_terms and data.age_confirmed
    ):
        raise HTTPException(
            400, "Confirm your age and accept the Terms to complete your account"
        )
    supabase.table("profiles").update(
        {
            "full_name": data.full_name.strip(),
            "country": data.country.upper(),
            "onboarding_complete": True,
        }
    ).eq("id", user).execute()
    return {"saved": True}


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    password: str = Field(min_length=8, max_length=128)


@router.post("/account/password")
def change_password(data: PasswordChange, request: Request, user=Depends(current_user)):
    rate_limit(request, "change-password", user, 5)
    p = profile(user)
    require_password(p, data.current_password)
    supabase.table("profiles").update(
        {
            "password_hash": hash_password(data.password),
            "session_version": p["session_version"] + 1,
        }
    ).eq("id", user).execute()
    supabase.table("account_tokens").update(
        {"used_at": datetime.now(timezone.utc).isoformat()}
    ).eq("user_id", user).is_("used_at", "null").execute()
    return {"message": "Password changed. Log in with your new password."}


class EmailChange(BaseModel):
    email: EmailStr
    current_password: str = Field(max_length=128)


@router.post("/account/email")
def change_email(data: EmailChange, request: Request, user=Depends(current_user)):
    rate_limit(request, "change-email", user, 3, 3600)
    p = profile(user)
    require_password(p, data.current_password)
    if find_email(data.email):
        raise HTTPException(400, "This address cannot be used")
    send_account_link(p, "change_email", str(data.email).casefold())
    return {
        "message": "Check your new address for a verification link. Your current email stays active until you verify."
    }


@router.post("/account/verify-email")
def verify_email(request: Request, user=Depends(current_user)):
    rate_limit(request, "verify-email", user, 3, 3600)
    p = profile(user)
    if not p.get("email_verified_at"):
        send_account_link(p, "verify")
    return {"message": "Check your email for the verification link."}


def all_applications(user):
    rows, offset = [], 0
    while True:
        page = (
            supabase.table("applications")
            .select("*")
            .eq("user_id", user)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .range(offset, offset + 499)
            .execute()
            .data
        )
        rows.extend(page)
        if len(page) < 500:
            return rows
        offset += 500


@router.get("/account/export")
def export(user=Depends(current_user)):
    fields = [
        "job_title",
        "company_name",
        "company_website",
        "location",
        "source_url",
        "source",
        "date_applied",
        "status",
        "notes",
        "salary_min",
        "salary_max",
        "salary_currency",
        "salary_period",
        "contact_person",
        "deadline",
        "reminder_date",
        "created_at",
    ]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in all_applications(user):
        # Prevent formula execution when opening a user-authored field in Excel.
        writer.writerow(
            {
                k: (
                    "'" + str(v)
                    if isinstance(v, str)
                    and v.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                    else v
                )
                for k, v in row.items()
            }
        )
    return Response(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="jobs-ac-ghana-applications.csv"',
            "Cache-Control": "no-store",
        },
    )


class AccountDeletion(BaseModel):
    current_password: str = Field(default="", max_length=128)
    confirmation: str


@router.delete("/account/settings")
def delete_account(
    data: AccountDeletion,
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    user=Depends(current_user),
):
    p = profile(user)
    if data.confirmation != "DELETE MY ACCOUNT":
        raise HTTPException(400, "Type DELETE MY ACCOUNT to confirm")
    if p["password_hash"].startswith("!google:") and not data.current_password:
        if session_payload(credentials.credentials).get("iat", 0) < time.time() - 300:
            raise HTTPException(
                403, "Sign in with Google again before deleting your account."
            )
    else:
        require_password(p, data.current_password)
    if p.get("auth_user_id"):
        supabase.auth.admin.delete_user(p["auth_user_id"])
    supabase.table("profiles").delete().eq("id", user).execute()
    return {"deleted": True}
