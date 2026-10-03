"""
himalayas.py

Wrapper for the Himalayas Remote Jobs API.
Free, no authentication required.
Docs: https://himalayas.app/docs/remote-jobs-api
"""

import httpx


HIMALAYAS_BASE_URL = "https://himalayas.app/jobs/api"


class HimalayasClient:
    """Client for querying the Himalayas Remote Jobs API."""

    async def search(
        self,
        query: str = "",
        country: str = "",
        page: int = 1,
        results_per_page: int = 20,
        worldwide_only: bool = False,
    ) -> dict:
        """
        Search remote jobs on Himalayas.

        Args:
            query: Job title or keywords
            country: ISO alpha-2 country code (e.g. 'gh' for Ghana)
            page: Page number
            results_per_page: Jobs per page (max 20)
            worldwide_only: Only return jobs open worldwide

        Returns:
            Normalized dict with a 'jobs' list.
        """
        url = f"{HIMALAYAS_BASE_URL}/search"

        params = {
            "page": page,
            "limit": min(results_per_page, 20),
        }

        if query:
            params["q"] = query

        if country:
            params["country"] = country.upper()

        if worldwide_only:
            params["worldwide"] = "true"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            raw = response.json()

        # Himalayas returns jobs under 'jobs' key
        items = raw.get("jobs", [])

        jobs = []
        for job in items:
            # Get location restrictions
            restrictions = job.get("locationRestrictions") or []
            if restrictions:
                location_names = [r.get("name", "") for r in restrictions if isinstance(r, dict)]
                location = ", ".join(location_names) if location_names else "Worldwide"
            else:
                location = "Worldwide"

            jobs.append(
                {
                    "id": job.get("guid"),
                    "title": job.get("title"),
                    "company": job.get("companyName"),
                    "location": location,
                    "description": job.get("excerpt", "")[:300],
                    "url": job.get("applicationLink"),
                    "created": job.get("pubDate"),
                    "salary_min": job.get("minSalary"),
                    "salary_max": job.get("maxSalary"),
                    "source": "himalayas",
                    "remote": True,
                }
            )

        return {"jobs": jobs, "count": len(jobs)}