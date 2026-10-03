"""
supabase_client.py

Initializes the Supabase client using environment variables.
Used by all database operations.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client


# Load .env from the backend root (one level up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env"
    )


supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)