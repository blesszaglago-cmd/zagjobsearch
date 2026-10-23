"""Password authentication with versioned hashes and verified provider identities."""

import hashlib
import secrets
import hmac
import logging
import re
from datetime import date
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from fastapi import HTTPException
from database.supabase_client import supabase
from sessions import issue_session

ITERATIONS = 600_000
logger = logging.getLogger(__name__)


def application_return_path(value):
    """Only return to a public listing, never a caller-selected external URL."""
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"/jobs/[a-f0-9]{32}", value)
        else ""
    )


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str
    date_of_birth: date | None = None
    age_confirmed: bool = False
    country: str = Field(default="GH", min_length=2, max_length=2)
    accepted_terms: bool
    next_path: str = Field(default="", max_length=200)

    @field_validator("next_path")
    @classmethod
    def safe_return_path(cls, value):
        return application_return_path(value)

    @field_validator("email")
    @classmethod
    def normalise_email(cls, value):
        return str(value).casefold()

    @field_validator("full_name", mode="before")
    @classmethod
    def clean_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def valid_account(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        if not self.accepted_terms:
            raise ValueError("You must accept the Terms of Service")
        if self.date_of_birth:
            today = date.today()
            age = (
                today.year
                - self.date_of_birth.year
                - (
                    (today.month, today.day)
                    < (self.date_of_birth.month, self.date_of_birth.day)
                )
            )
            if age < 13:
                raise ValueError("You must be at least 13 years old")
        elif not self.age_confirmed:
            raise ValueError("Confirm that you are at least 13 years old")
        return self


class SignupResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    user_id: str
    email: str
    full_name: str
    country: str
    message: str


def hash_password(password: str, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str):
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, count, salt, expected = stored.split("$")
            count = int(count)
            if not 100_000 <= count <= 2_000_000:
                return False
        else:
            salt, expected = stored.split("$")
            count = 100_000
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), count
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


DUMMY_HASH = hash_password("unavailable-account")


def find_email(email):
    # Escape pattern metacharacters: ilike is case insensitive, not an exact-match operator.
    safe = str(email).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = (
        supabase.table("profiles")
        .select("*")
        .ilike("email", safe)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def login_user(data):
    user = find_email(data.email)
    # Spend comparable hashing work on unknown accounts.
    valid = (
        verify_password(data.password, user["password_hash"])
        if user
        else verify_password(data.password, DUMMY_HASH)
    )
    if not user or not valid:
        raise ValueError("Invalid email or password")
    if user.get("requires_verification") and not user.get("email_verified_at"):
        raise HTTPException(
            403,
            "Verify your email before logging in. You can request another link on the account recovery page.",
        )
    if not user["password_hash"].startswith(f"pbkdf2_sha256${ITERATIONS}$"):
        supabase.table("profiles").update(
            {"password_hash": hash_password(data.password)}
        ).eq("id", user["id"]).eq("password_hash", user["password_hash"]).eq(
            "session_version", user.get("session_version", 1)
        ).execute()
    return LoginResponse(
        access_token=issue_session(user["id"], user.get("session_version", 1)),
        user_id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        country=user["country"],
        message="Login successful",
    )


def validate_signup(data):
    from mailer import email_enabled

    verification_required = email_enabled()
    message = (
        "Check your inbox and spam folder for the next steps. If no message arrives, "
        "use 'Forgot password or verify email' to recover your account or request a new link."
        if verification_required
        else "Try logging in with your password. If you already have an account, use your existing password or account recovery."
    )
    # Do the same hashing work for existing addresses, and return the same public
    # response without exposing whether a mailbox already owns a workspace.
    password_hash = hash_password(data.password)
    if find_email(data.email):
        return SignupResponse(message=message)
    result = (
        supabase.table("profiles")
        .insert(
            {
                "email": str(data.email).casefold(),
                "full_name": data.full_name.strip(),
                "country": data.country.upper(),
                "date_of_birth": None,
                "password_hash": password_hash,
                "requires_verification": verification_required,
            }
        )
        .execute()
    )
    user = result.data[0]
    if verification_required:
        from account_security import send_account_link

        try:
            send_account_link(user, "verify", next_path=data.next_path)
        except Exception:
            # The profile already exists. Keep verification required and explain
            # recovery without logging provider replies, addresses or tokens.
            logger.warning("signup_verification_delivery_failed")
    return SignupResponse(message=message)
