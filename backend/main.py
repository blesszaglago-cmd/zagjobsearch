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
    version="1.0.0",
)

# CORS — allow the frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
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
def signup(data: SignupRequest):
    """
    Register a new user.
    Validates age (13+), password match, and terms acceptance.
    Creates a real record in Supabase.
    """
    try:
        return validate_signup(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Signup is unavailable. Please try again shortly.")
@app.post("/login", response_model=LoginResponse)
def login(data: LoginRequest):
    """
    Authenticate a user.
    Verifies email exists and password matches the stored hash.
    """
    try:
        return login_user(data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Login is unavailable. Please try again shortly.")
from workspace_api import router as workspace_router
app.include_router(workspace_router)

@app.get("/auth/config")
def auth_config():
    return {"supabase_url": os.getenv("SUPABASE_URL", ""), "publishable_key": os.getenv("SUPABASE_PUBLISHABLE_KEY", ""), "google_enabled": os.getenv("GOOGLE_AUTH_ENABLED", "false").lower() == "true"}
from reminders import router as reminder_router
app.include_router(reminder_router)
