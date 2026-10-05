"""
himalayas.py

Wrapper for the Himalayas Remote Jobs API.
Free, no authentication required.
Docs: https://himalayas.app/docs/remote-jobs-api
"""

import httpx
from datetime import datetime, timezone


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
        employment_type: str = "",
        seniority: str = "",
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

        if employment_type: params["employment_type"] = employment_type
        if seniority: params["seniority"] = seniority
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
                location_names = [r if isinstance(r, str) else r.get("name", "") for r in restrictions if isinstance(r, (str, dict))]
                location = ", ".join(location_names) if location_names else "See posting for restrictions"
            else:
                location = "Worldwide"

            expiry = job.get("expiryDate")
            if expiry:
                try:
                    expiry_dt = datetime.fromtimestamp(float(expiry), timezone.utc) if isinstance(expiry, (int, float)) else datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
                    if expiry_dt.replace(tzinfo=expiry_dt.tzinfo or timezone.utc) < datetime.now(timezone.utc):
                        continue
                except (ValueError, OverflowError, OSError):
                    pass
            jobs.append(
                {
                    "id": f"himalayas:{job.get('guid')}",
                    "title": job.get("title"),
                    "company": job.get("companyName"),
                    "location": location,
                    "description": job.get("description") or job.get("excerpt", ""),
                    "job_type": job.get("employmentType"),
                    "industry": ", ".join(job.get("categories") or job.get("category") or []) if isinstance(job.get("categories") or job.get("category"), list) else (job.get("category") or ""),
                    "source_url": job.get("guid") if str(job.get("guid", "")).startswith("https://himalayas.app/") else (f"https://himalayas.app/companies/{job.get('companySlug')}/jobs" if job.get("companySlug") else "https://himalayas.app"),
                    "url": job.get("applicationLink"),
                    "created": job.get("pubDate"),
                    "salary_min": job.get("minSalary"),
                    "salary_max": job.get("maxSalary"),
                    "salary_currency": job.get("currency"),
                    "salary_period": job.get("salaryPeriod"),
                    "deadline": expiry,
                    "source": "himalayas",
                    "remote": True,
                }
            )

        return {"jobs": jobs, "count": len(jobs)}