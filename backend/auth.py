"""
auth.py

Authentication logic for ZagJobSearch.
Handles signup validation, password hashing, and user creation in Supabase.
"""

import hashlib
import secrets
from datetime import date
from pydantic import BaseModel, EmailStr, Field, field_validator

from database.supabase_client import supabase


class SignupRequest(BaseModel):
    """Request model for user signup."""

    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    confirm_password: str
    date_of_birth: date
    country: str = Field(..., min_length=2, max_length=2)
    accepted_terms: bool

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(cls, v, info):
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def age_gate(cls, v):
        """COPPA age gate: reject users under 13."""
        today = date.today()
        age = today.year - v.year - ((today.month, today.day) < (v.month, v.day))
        if age < 13:
            raise ValueError("You must be at least 13 years old to use ZagJobSearch")
        return v

    @field_validator("accepted_terms")
    @classmethod
    def terms_accepted(cls, v):
        if not v:
            raise ValueError("You must accept the Terms of Service")
        return v


class SignupResponse(BaseModel):
    """Response model for successful signup."""
    user_id: str
    email: str
    full_name: str
    country: str
    message: str


def hash_password(password: str, salt: str = None) -> str:
    """
    Hash a password using PBKDF2-HMAC-SHA256.
    Returns: 'salt$hash' format.
    """
    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,  # iterations
    )
    return f"{salt}${hashed.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash."""
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False

    return hash_password(password, salt) == stored 

class LoginRequest(BaseModel):
    """Request model for user login."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Response model for successful login."""
    user_id: str
    email: str
    full_name: str
    country: str
    message: str


def login_user(data: LoginRequest) -> LoginResponse:
    """
    Verify login credentials against the database.
    Returns user info if valid, raises ValueError if not.
    """
    # Find user by email
    result = (
        supabase.table("profiles")
        .select("id, email, full_name, country, password_hash")
        .eq("email", data.email)
        .execute()
    )

    if not result.data:
        raise ValueError("Invalid email or password")

    user = result.data[0]

    # Verify the password
    if not verify_password(data.password, user["password_hash"]):
        raise ValueError("Invalid email or password")

    return LoginResponse(
        user_id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        country=user["country"],
        message="Login successful",
    )
def validate_signup(data: SignupRequest) -> SignupResponse:
    """
    Validate a signup request and create the user in Supabase.
    """
    # Check if email already exists
    existing = (
        supabase.table("profiles")
        .select("id")
        .eq("email", data.email)
        .execute()
    )

    if existing.data:
        raise ValueError("An account with this email already exists")

    # Hash the password
    password_hash = hash_password(data.password)

    # Insert the new user
    result = (
        supabase.table("profiles")
        .insert(
            {
                "email": data.email,
                "full_name": data.full_name,
                "country": data.country,
                "date_of_birth": data.date_of_birth.isoformat(),
                "password_hash": password_hash,
            }
        )
        .execute()
    )

    if not result.data:
        raise RuntimeError("Failed to create user")

    user = result.data[0]

    return SignupResponse(
        user_id=user["id"],
        email=user["email"],
        full_name=user["full_name"],
        country=user["country"],
        message="Account created successfully. You can now log in.",
    )