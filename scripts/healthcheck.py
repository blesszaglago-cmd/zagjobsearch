"""Public health checks; never read or log account data or credentials."""

import json
import html
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta


def get(url, as_json=True):
    with urllib.request.urlopen(
        urllib.request.Request(
            url, headers={"User-Agent": "jobs-ac-ghana-healthcheck"}
        ),
        timeout=30,
    ) as response:
        content = response.read().decode()
        return json.loads(content) if as_json else content


def main():
    api = "https://zagjobsearch-api.vercel.app"
    site = "https://zagjobsearch.vercel.app"
    coverage = get(api + "/catalogue/coverage")
    completed = coverage.get("updated_at")
    if not completed or datetime.fromisoformat(
        completed.replace("Z", "+00:00")
    ) < datetime.now(timezone.utc) - timedelta(hours=24):
        raise RuntimeError("Catalogue has not completed a refresh in 24 hours")
    data = get(api + "/catalogue?category=jobs")
    unavailable = [
        s.get("source", "unknown")
        for s in data.get("source_status", [])
        if s.get("state") != "ok"
    ]
    if unavailable or coverage.get("last_error"):
        raise RuntimeError(
            "Catalogue source checks need attention: "
            + ", ".join(unavailable or ["refresh failed"])
        )
    if not data.get("jobs"):
        raise RuntimeError("No current Ghana jobs returned")
    first = data["jobs"][0]
    page = get(site + "/jobs/" + first["id"], False)
    if (
        first["title"] not in html.unescape(page)
        or 'class="job-description-copy"' not in page
        or 'rel="canonical"' not in page
    ):
        raise RuntimeError("Job details are absent from server HTML")
    sitemap = get(site + "/sitemap.xml", False)
    if "/jobs/" not in sitemap or "<urlset" not in sitemap:
        raise RuntimeError("Job sitemap is empty or invalid")
    robots = get(site + "/robots.txt", False)
    if "Sitemap:" not in robots or "Disallow: /\n" in robots:
        raise RuntimeError("Robots configuration does not permit discovery")
    config = get(api + "/auth/config")
    print(
        json.dumps(
            {
                "healthy": True,
                "last_refresh": completed,
                "jobs": data["total"],
                "email_configured": config.get("email_enabled", False),
                "google_configured": config.get("google_enabled", False),
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Health check failed: " + str(error), file=sys.stderr)
        sys.exit(1)
