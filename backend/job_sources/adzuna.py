"""
adzuna.py

Wrapper for the Adzuna Jobs API.
Docs: https://developer.adzuna.com/docs/search
"""

import os
import httpx
from typing import Optional


ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs"


class AdzunaClient:
    """Client for querying the Adzuna Jobs API."""

    def __init__(self):
        self.app_id = os.getenv("ADZUNA_APP_ID")
        self.app_key = os.getenv("ADZUNA_APP_KEY")

        if not self.app_id or not self.app_key:
            raise ValueError(
                "ADZUNA_APP_ID and ADZUNA_APP_KEY must be set in environment variables."
            )

    async def search(
        self,
        query: str,
        country: str = "gb",
        page: int = 1,
        results_per_page: int = 20,
        remote_only: bool = False,
        location: Optional[str] = None,
    ) -> dict:
        """
        Search for jobs on Adzuna.

        Args:
            query: Job title or keywords (e.g. "software engineer")
            country: 2-letter country code (gb, us, ca, au, de, fr, in, etc.)
            page: Page number (1-indexed)
            results_per_page: Jobs per page (max 50)
            remote_only: Filter for remote jobs only
            location: Optional location filter (city or region)

        Returns:
            Raw JSON response from Adzuna as a dict.
        """
        url = f"{ADZUNA_BASE_URL}/{country}/search/{page}"

        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": results_per_page,
            "what": query,
            "content-type": "application/json",
        }

        if location:
            params["where"] = location

        if remote_only:
            params["what_and"] = "remote"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()