"""
fuzu.py

Wrapper for the Fuzu Jobs API (Africa-focused).
Fuzu has a public endpoint that requires no authentication.
"""

import httpx
from typing import Optional


FUZU_BASE_URL = "https://www.fuzu.com/api"


class FuzuClient:
    """Client for querying Fuzu's public job feed."""

    async def search(
        self,
        query: str = "",
        country_code: str = "GH",
        page: int = 1,
        results_per_page: int = 20,
    ) -> dict:
        """
        Search jobs on Fuzu.

        Args:
            query: Job title or keywords
            country_code: 2-letter country code (GH, NG, KE, ZA, etc.)
            page: Page number (Fuzu uses offset-based pagination)
            results_per_page: Jobs per page

        Returns:
            Normalized dict with a 'jobs' list.
        """
        url = f"{FUZU_BASE_URL}/all_jobs"

        params = {
            "page": page,
            "per_page": results_per_page,
        }

        if query:
            params["search"] = query

        if country_code:
            params["country_code"] = country_code.upper()

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            raw = response.json()

        # Fuzu returns a list directly or wrapped in 'data' — handle both
        items = raw if isinstance(raw, list) else raw.get("data", [])

        jobs = []
        for job in items:
            jobs.append(
                {
                    "id": job.get("id"),
                    "title": job.get("title") or job.get("name"),
                    "company": (job.get("company") or {}).get("name")
                    if isinstance(job.get("company"), dict)
                    else job.get("company"),
                    "location": job.get("location") or job.get("city"),
                    "description": (job.get("description") or "")[:300],
                    "url": job.get("url") or job.get("apply_url"),
                    "created": job.get("created_at"),
                    "salary_min": job.get("salary_min"),
                    "salary_max": job.get("salary_max"),
                    "source": "fuzu",
                }
            )

        return {"jobs": jobs, "count": len(jobs)}