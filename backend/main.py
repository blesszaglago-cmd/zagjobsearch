"""
main.py

FastAPI server for jobs.ac.ghana.
Aggregates job listings from multiple sources.
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from auth import (
    SignupRequest,
    SignupResponse,
    validate_signup,
    LoginRequest,
    LoginResponse,
    login_user,
)

# Load environment variables
load_dotenv()


app = FastAPI(
    title="jobs.ac.ghana API",
    description="Ghana jobs, remote roles accepting Ghana applicants, and scholarships",
    version="2.1.0",
)

# CORS — allow the frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "https://zagjobsearch.vercel.app"),
        "http://localhost:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "message": "jobs.ac.ghana API is running.",
        "endpoints": ["/search", "/health"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


from catalogue import router as catalogue_router, search_catalogue

app.include_router(catalogue_router)


@app.get("/search")
def search_jobs(request: Request):
    return search_catalogue(request)


@app.post("/signup", response_model=SignupResponse)
def signup(data: SignupRequest, request: Request):
    """
    Register a new user.
    Validates age (13+), password match, and terms acceptance.
    Creates a real record in Supabase.
    """
    try:
        from security import rate_limit

        rate_limit(request, "signup", str(data.email), 5, 3600)
        return validate_signup(data)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Signup is unavailable. Please try again shortly."
        )


@app.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, request: Request):
    """
    Authenticate a user.
    Verifies email exists and password matches the stored hash.
    """
    try:
        from security import rate_limit

        rate_limit(request, "login", str(data.email), 8, 900)
        return login_user(data)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Login is unavailable. Please try again shortly."
        )


from workspace_api import router as workspace_router

app.include_router(workspace_router)


@app.get("/auth/config")
def auth_config():
    from mailer import email_enabled

    return {
        "supabase_url": os.getenv("SUPABASE_URL", ""),
        "publishable_key": os.getenv("SUPABASE_PUBLISHABLE_KEY", ""),
        "google_enabled": os.getenv("GOOGLE_AUTH_ENABLED", "false").lower() == "true",
        "email_enabled": email_enabled(),
    }


from reminders import router as reminder_router

app.include_router(reminder_router)

from account_security import router as account_security_router
from saved_searches import router as saved_search_router

app.include_router(account_security_router)
app.include_router(saved_search_router)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith(("/account", "/auth", "/login", "/signup")):
        response.headers["Cache-Control"] = "no-store"
    return response


from reports import router as report_router

app.include_router(report_router)

from operations import router as operations_router

app.include_router(operations_router)
