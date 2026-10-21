"""Synthetic recovery fixtures. Never read production records or keys."""

import importlib.util
from pathlib import Path


def script(name):
    path = Path(__file__).resolve().parents[2] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


restore = script("restore_backup")
backup = script("backup")
TEST_KEY = b"a" * 32
USER = "10000000-0000-4000-8000-000000000001"
APPLICATION = "20000000-0000-4000-8000-000000000001"
STAMP = "2026-10-21T16:46:00+00:00"


def fixture():
    return {
        "format": 1,
        "created_at": STAMP,
        "source": "https://unused.example",
        "tables": {
            "profiles": [
                {
                    "id": USER,
                    "email": "synthetic@example.com",
                    "full_name": "Recovery fixture",
                    "country": "GH",
                    "date_of_birth": None,
                    "password_hash": "synthetic-hash",
                    "created_at": STAMP,
                    "session_version": 7,
                    "email_verified_at": None,
                    "requires_verification": False,
                    "onboarding_complete": True,
                    "auth_user_id": None,
                }
            ],
            "applications": [
                {
                    "id": APPLICATION,
                    "user_id": USER,
                    "job_title": "=1+1'); DROP TABLE public.profiles; --",
                    "company_name": "Synthetic employer",
                    "company_website": "https://example.com",
                    "location": "Accra",
                    "source_url": "https://example.com/job",
                    "source": "manual",
                    "date_applied": "2026-10-20",
                    "status": "applied",
                    "notes": "Quoted ' text: kente \u2665",
                    "salary_min": 2500.25,
                    "salary_max": 4000,
                    "salary_currency": "GHS",
                    "salary_period": "month",
                    "contact_person": "",
                    "deadline": "2026-10-30",
                    "reminder_date": "2026-10-28",
                    "email_reminder": False,
                    "email_reminder_sent_at": None,
                    "created_at": STAMP,
                    "updated_at": STAMP,
                    "reminder_auto": True,
                    "deleted_at": None,
                }
            ],
            "application_events": [
                {
                    "id": "30000000-0000-4000-8000-000000000001",
                    "application_id": APPLICATION,
                    "event_type": "created",
                    "old_value": None,
                    "new_value": "applied",
                    "note": None,
                    "created_at": STAMP,
                }
            ],
            "career_profiles": [
                {
                    "user_id": USER,
                    "verified_text": "retired synthetic data",
                    "updated_at": STAMP,
                }
            ],
            "saved_searches": [
                {
                    "id": "40000000-0000-4000-8000-000000000001",
                    "user_id": USER,
                    "name": "Synthetic Accra search",
                    "filters": {"q": "engineer", "salary_min": "2500.25"},
                    "email_alert": False,
                    "last_checked_at": None,
                    "seen_ids": [APPLICATION],
                    "created_at": STAMP,
                }
            ],
        },
    }
