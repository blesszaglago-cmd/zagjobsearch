"""Check public availability; report incomplete publisher checks separately.

Source warnings never skip page, SEO or guest-Apply checks. A stale or failed
refresh, no checked listings, or a broken public flow still fails the run.
No accounts, private records, emails or credentials are used.
"""

import html
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

API = "https://zagjobsearch-api.vercel.app"
SITE = "https://zagjobsearch.vercel.app"
PARTIAL_REFRESH_MESSAGE = "Some sources need another check"


def get(url, as_json=True):
    with urllib.request.urlopen(
        urllib.request.Request(
            url, headers={"User-Agent": "jobs-ac-ghana-healthcheck"}
        ),
        timeout=30,
    ) as response:
        content = response.read().decode()
        return json.loads(content) if as_json else content


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def expect_guest_denied(url):
    # Do not follow an accidental external Apply redirect while checking the gate.
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "jobs-ac-ghana-healthcheck",
            "Accept": "application/json",
        },
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(request, timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        if response.code != 401:
            raise RuntimeError("Guest Apply protection did not return 401")
        if "no-store" not in response.headers.get("Cache-Control", ""):
            raise RuntimeError("Guest Apply denial could be cached")
        content = json.loads(response.read(12 * 1024).decode())
        if not isinstance(content, dict) or not isinstance(content.get("detail"), str):
            raise RuntimeError("Guest Apply protection returned an unexpected response")


def command_text(value):
    """Do not let a remote value inject GitHub workflow commands."""
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def source_issues(statuses):
    issues = []
    for status in statuses:
        if status.get("state") == "ok":
            continue
        name = str(status.get("source", "unknown"))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:-]{0,99}", name):
            name = "unknown-source"
        state = status.get("state")
        issues.append(
            {
                "source": name,
                "state": state if state in {"partial", "unavailable"} else "unknown",
                "accepted": int(status.get("accepted", 0)),
                "failed_checks": int(status.get("failed_checks", 0)),
            }
        )
    return issues


def write_summary(result):
    destination = os.getenv("GITHUB_STEP_SUMMARY")
    if not destination:
        return
    lines = [
        "## Live site health",
        "",
        "Public browsing, job details, discovery and guest Apply protection: passed.",
        f"Catalogue status: **{result['catalogue_status']}**.",
        f"Last completed refresh: {result['last_refresh']}.",
        f"Current Ghana jobs: {result['jobs']}.",
    ]
    if result["source_issues"]:
        lines += [
            "",
            "Incomplete publisher checks remain visible on the site's Sources page.",
            "",
            "| Source | State | Accepted in refresh | Failed checks |",
            "| --- | --- | ---: | ---: |",
        ]
        for issue in result["source_issues"]:
            lines.append(
                f"| {issue['source']} | {issue['state']} | {issue['accepted']} | {issue['failed_checks']} |"
            )
    with Path(destination).open("a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")


def main():
    if get(API + "/health").get("status") != "ok":
        raise RuntimeError("Backend health endpoint is not healthy")
    coverage = get(API + "/catalogue/coverage")
    completed = coverage.get("updated_at")
    refreshed = (
        datetime.fromisoformat(completed.replace("Z", "+00:00")) if completed else None
    )
    now = datetime.now(timezone.utc)
    if (
        not refreshed
        or refreshed.tzinfo is None
        or refreshed < now - timedelta(hours=24)
    ):
        raise RuntimeError("Catalogue has not completed a refresh in 24 hours")
    if refreshed > now + timedelta(minutes=5):
        raise RuntimeError("Catalogue refresh timestamp is in the future")
    if coverage.get("last_error") not in {None, "", PARTIAL_REFRESH_MESSAGE}:
        raise RuntimeError("Catalogue reports a refresh failure")
    data = get(API + "/catalogue?category=jobs")
    statuses = data.get("source_status", [])
    if not statuses or not any(
        row.get("state") in {"ok", "partial"} and row.get("accepted", 0) > 0
        for row in statuses
    ):
        raise RuntimeError("No listing source completed any successful checks")
    issues = source_issues(statuses)
    if os.getenv("GITHUB_ACTIONS") == "true":
        for issue in issues:
            detail = (
                f"{issue['source']}: {issue['state']}; accepted {issue['accepted']}; "
                f"failed checks {issue['failed_checks']}. Public site checks continue."
            )
            print(
                "::warning title=Source coverage needs attention::"
                + command_text(detail)
            )
    if not data.get("jobs"):
        raise RuntimeError("No current Ghana jobs returned")
    first = data["jobs"][0]
    if not re.fullmatch(r"[a-f0-9]{32}", str(first.get("id", ""))):
        raise RuntimeError("Job listing identifier is invalid")
    page = get(SITE + "/jobs/" + first["id"], False)
    if (
        first["title"] not in html.unescape(page)
        or 'class="job-description-copy"' not in page
        or 'rel="canonical"' not in page
    ):
        raise RuntimeError("Job details are absent from server HTML")
    sitemap = get(SITE + "/sitemap.xml", False)
    if "/jobs/" not in sitemap or "<urlset" not in sitemap:
        raise RuntimeError("Job sitemap is empty or invalid")
    robots = get(SITE + "/robots.txt", False)
    if "Sitemap:" not in robots or "Disallow: /\n" in robots:
        raise RuntimeError("Robots configuration does not permit discovery")
    expect_guest_denied(SITE + "/api/jobs/" + first["id"] + "/apply")
    expect_guest_denied(API + "/catalogue/" + first["id"] + "?verify=true")
    config = get(API + "/auth/config")
    result = {
        "site_healthy": True,
        "catalogue_status": "degraded" if issues else "ok",
        "last_refresh": completed,
        "jobs": data["total"],
        "checked_sources": len(statuses),
        "source_issues": issues,
        "email_configured": config.get("email_enabled", False),
        "google_configured": config.get("google_enabled", False),
    }
    write_summary(result)
    print(json.dumps(result))
    return result


def run():
    try:
        main()
        return 0
    except Exception as error:
        print("Health check failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run())
