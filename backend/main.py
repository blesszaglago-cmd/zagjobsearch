"""
main.py

FastAPI server for ZagJobSearch.
Aggregates job listings from multiple sources.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

from job_sources.adzuna import AdzunaClient
from job_sources.himalayas import HimalayasClient
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
    title="ZagJobSearch API",
    description="Global job search aggregator",
    version="1.0.0",
)

# CORS — allow the frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize clients
adzuna = AdzunaClient() if os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY") else None
himalayas = HimalayasClient()


@app.get("/")
def read_root():
    return {
        "message": "ZagJobSearch API is running.",
        "endpoints": ["/search", "/health"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/search")
async def search_jobs(
    q: str = Query(..., description="Job title or keywords"),
    country: str = Query("gb", description="2-letter country code (gb, us, gh, ng, ke, za)"),
    page: int = Query(1, ge=1, le=10),
    remote: bool = Query(False, description="Filter for remote jobs"),
    job_type: str = Query("all"),
    experience: str = Query(""),
):
    """
    Search jobs across multiple sources.
    - Fuzu: REMOVED (blocked)
    - Himalayas: Remote jobs (global, no key)
    - Adzuna: Local jobs (18 countries, requires key)
    """
    q = q.strip()
    country = country.lower()
    if len(q) > 200 or len(country) != 2 or not country.isalpha():
        raise HTTPException(status_code=400, detail="Enter keywords and a two-letter country code.")
    supported_countries = {"at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb", "in", "it", "mx", "nl", "nz", "pl", "sg", "us", "za"}

    jobs = []
    errors = []

    # Always query Himalayas for remote jobs (or if African country)
    try:
        result = await himalayas.search(
            query=q,
            country=country.upper(),
            page=page,
            worldwide_only=False,
            employment_type={"permanent":"Full Time", "part-time":"Part Time", "internship":"Intern", "contract":"Contractor"}.get(job_type, ""),
            seniority={"entry":"Entry-level", "mid":"Mid-level", "senior":"Senior", "manager":"Manager"}.get(experience, ""),
        )
        jobs.extend(result["jobs"])
    except Exception as e:
        errors.append("Himalayas temporarily unavailable")

    # Query local listings only in supported countries, including South Africa.
    if adzuna is not None and country in supported_countries and not remote:
        try:
            result = await adzuna.search(
                query=q,
                country=country,
                page=page,
                remote_only=remote,
            )
            for job in result.get("results", []):
                jobs.append(
                    {
                        "id": f"adzuna:{job.get('id')}",
                        "title": job.get("title"),
                        "company": job.get("company", {}).get("display_name"),
                        "location": job.get("location", {}).get("display_name"),
                        "description": job.get("description", ""),
                        "job_type": job.get("contract_time") or job.get("contract_type"),
                        "industry": job.get("category", {}).get("label"),
                        "url": job.get("redirect_url"),
                        "created": job.get("created"),
                        "salary_min": job.get("salary_min"),
                        "salary_max": job.get("salary_max"),
                        "source": "adzuna",
                    }
                )
        except Exception as e:
            errors.append("Adzuna temporarily unavailable")

    return {
        "query": q,
        "country": country,
        "page": page,
        "count": len(jobs),
        "jobs": jobs,
        "errors": errors if errors else None,
    }
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
