"""Bounded readers for public Ghana vacancy pages, without private APIs or logins.

Discovery windows are deliberately partial. A vacancy falling out of a window is
not evidence that it closed; it expires from public results after 48h unchecked.
"""

import asyncio
import json
import re
import xml.etree.ElementTree as ET
import httpx
from datetime import timedelta
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

WINDOWED_SOURCES = {"ghana-current-jobs", "hireghana", "glmis"}
SOURCE_NAMES = ["ghana-current-jobs", "hireghana", "glmis", "newmont", "telecel"]
SOURCE_INFO = {
    "ghana-current-jobs": (
        "Ghana Current Jobs",
        "https://www.ghanacurrentjobs.com/",
        "Job board",
        "Recent public vacancies; factual summaries link to the original posting.",
    ),
    "hireghana": (
        "HIREghana",
        "https://hiregh.com/",
        "Recruitment agency",
        "Public vacancy RSS feed; applications go to the agency's original instructions.",
    ),
    "glmis": (
        "Ghana Labour Market Information System",
        "https://www.glmis.gov.gh/jobs",
        "Government portal",
        "Recent public vacancies with Ghana work locations. Overseas placements are excluded.",
    ),
    "newmont": (
        "Newmont",
        "https://jobs.newmont.com/us/en/search-results?keywords=Ghana",
        "Direct employer",
        "Public employer vacancies with an explicit Ghana location.",
    ),
    "telecel": (
        "Telecel Ghana",
        "https://telecel.zohorecruit.com/jobs/Careers",
        "Direct employer",
        "Public official career board, filtered to recent Ghana vacancies.",
    ),
}
EXTERNAL_SOURCES = [
    (
        "LinkedIn Ghana",
        "https://gh.linkedin.com/jobs/ghana-jobs",
        "Professional network",
        "Search on LinkedIn. Automatic import requires an authorised integration; it is not connected here.",
    ),
    (
        "Jobberman Ghana",
        "https://www.jobberman.com.gh/jobs",
        "Job board",
        "Search on Jobberman. Written approval is required for automated collection.",
    ),
    (
        "JobsInGhana",
        "https://www.jobsinghana.com/",
        "Job board",
        "Search at source. Public redistribution needs a suitable agreement.",
    ),
    (
        "Ghanajob.com",
        "https://www.ghanajob.com/",
        "Job board",
        "Visit the board. Automated access was unavailable at our source audit.",
    ),
    (
        "Jobwebghana",
        "https://jobwebghana.com/",
        "Job board",
        "Visit the board. Automated access was unavailable at our source audit.",
    ),
    (
        "SokoJob",
        "https://sokojob.com/",
        "Job board",
        "Search at source. Automated collection requires permission under its terms.",
    ),
    (
        "JobHouse",
        "https://jobhouse.com.gh/",
        "Recruitment agency",
        "Visit the agency. A reliable public feed is not connected.",
    ),
    (
        "Job Linq Africa",
        "https://joblinqafrica.com/",
        "Recruitment agency",
        "Visit the agency. No public vacancy feed is connected; some placements are abroad.",
    ),
    (
        "Petroleum Commission",
        "https://petrocom.gov.gh/upstream-oil-and-gas-industry-job-application-portal/",
        "Candidate registration",
        "Register at the Commission. This is a candidate pool, not a public vacancy feed.",
    ),
    (
        "MTN Ghana",
        "https://mtn.com.gh/careers/",
        "Direct employer",
        "Visit MTN careers. Some MTN notices are discoverable through Ghana Current Jobs, attributed to that board.",
    ),
]

FOREIGN_LOCATION = re.compile(
    r"\b(?:united arab emirates|u\.?a\.?e|dubai|abu dhabi|bulgaria|saudi arabia|qatar|oman|kuwait|"
    r"bahrain|europe|united kingdom|london|united states|usa|canada|australia|germany|france|"
    r"nigeria|lagos|abuja|kenya|nairobi|south africa|cote d.ivoire|ivory coast|abidjan|senegal|dakar)\b",
    re.I,
)


def on_host(url, host):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == host and not parsed.username


def ghana_location(location):
    from catalogue import regions_for

    return not FOREIGN_LOCATION.search(location) and bool(
        regions_for(location)
        or re.search(r"\bghana\b|\bnationwide\b|\ball regions\b", location, re.I)
    )


async def page(client, url):
    response = await client.get(url)
    response.raise_for_status()
    # Do not follow a source's redirect into an unrelated host or an auth wall.
    if urlparse(str(response.url)).hostname != urlparse(url).hostname:
        raise ValueError("Source redirected to another host")
    return BeautifulSoup(response.text, "html.parser")


def factual_summary(job, source, extra=None):
    """Display facts, not a copy of another board's full article."""
    facts = [
        f"{job['title']} at {job['company']}.",
        f"Work location: {job['location']}.",
    ]
    if job.get("employment_label"):
        facts.append(f"Job type: {job['employment_label']}.")
    for key, value in (extra or {}).items():
        if value:
            facts.append(f"{key}: {value}.")
    facts.append(
        f"Listed by {source}. Open the original posting for the full responsibilities, eligibility requirements and application instructions."
    )
    job.update(
        description=" ".join(facts), source=source, description_kind="source_summary"
    )
    return job


def parse_current_jobs(soup, url):
    from catalogue import make_job, closing, date

    summary = {}
    for row in soup.select(".summary .row"):
        values = row.select("h4")
        if len(values) == 2:
            summary[values[0].get_text(" ", strip=True).strip(": ").lower()] = values[
                1
            ].get_text(" ", strip=True)
    title = soup.select_one("h3.special:not(.cat)")
    body = soup.select_one(".content.text-justify")
    location = summary.get("location", "")
    if not title or not body or not summary.get("company"):
        raise ValueError("Vacancy detail format changed")
    if not ghana_location(location):
        return None
    body_text = body.get_text(" ", strip=True)
    published = soup.select_one('meta[property="article:published_time"]')
    deadline = closing(body_text) or date(summary.get("job expires"))
    # Board notices must have an explicit application deadline, not just a live URL.
    if not deadline:
        return None
    j = make_job(
        "ghana-current-jobs",
        url,
        re.sub(r"^Job Vacancy For\s+", "", title.get_text(" ", strip=True), flags=re.I),
        summary["company"],
        location,
        body_text,
        url,
        posted=published.get("content") if published else None,
        deadline=deadline,
        employment=summary.get("job status", ""),
        industry=summary.get("category", ""),
        experience=summary.get("experience", ""),
        check_url=url,
    )
    return (
        factual_summary(
            j,
            "Ghana Current Jobs",
            {
                "Education": summary.get("education"),
                "Experience requested": summary.get("experience"),
            },
        )
        if j
        else None
    )


async def current_jobs(client, archive_page=9):
    base = "https://www.ghanacurrentjobs.com/"
    links = set()
    # Eight recent index pages, 160 notices at most, revisited on every refresh.
    indexes = await asyncio.gather(
        *(
            page(client, base if n == 1 else f"{base}page/{n}/")
            for n in list(range(1, 9)) + list(range(archive_page, archive_page + 4))
        ),
        return_exceptions=True,
    )
    if all(isinstance(s, Exception) for s in indexes):
        raise ValueError("Job board unavailable")
    for soup in indexes:
        if isinstance(soup, Exception):
            continue
        for a in soup.select('.content a[href*="/job-vacancy-for-"]'):
            u = urljoin(base, a["href"])
            if on_host(u, "www.ghanacurrentjobs.com"):
                links.add(u.split("#")[0])
    if not links:
        raise ValueError("Job board format changed")

    async def one(url):
        return parse_current_jobs(await page(client, url), url)

    result = await asyncio.gather(
        *(one(u) for u in sorted(links)), return_exceptions=True
    )
    if any(
        isinstance(j, Exception)
        and not (
            isinstance(j, httpx.HTTPStatusError)
            and j.response.status_code in (404, 410)
        )
        for j in result
    ):
        raise ValueError("Vacancy details were incomplete or changed format")
    return "ghana-current-jobs", [j for j in result if isinstance(j, dict)]


def parse_hire_item(item):
    from catalogue import make_job, date, NOW

    title, url = item.findtext("title", ""), item.findtext("link", "")
    published = item.findtext("pubDate")
    if not on_host(url, "hiregh.com") or not ghana_location(title):
        return None
    if not date(published) or date(published) < NOW() - timedelta(days=60):
        return None
    body = item.findtext(
        "{http://purl.org/rss/1.0/modules/content/}encoded", ""
    ) or item.findtext("description", "")
    plain = BeautifulSoup(body, "html.parser").get_text(" ", strip=True)
    # The agency's client is often confidential. Never invent a client company.
    location = title.split(":", 1)[0].strip()
    j = make_job(
        "hireghana",
        url,
        title,
        "Employer not disclosed (HIREghana)",
        location,
        plain,
        url,
        posted=published,
        check_url=url,
    )
    return factual_summary(j, "HIREghana") if j else None


async def hireghana(client):
    feeds = await asyncio.gather(
        *(client.get(f"https://hiregh.com/feed/?paged={n}") for n in (1, 2)),
        return_exceptions=True,
    )
    jobs, valid = [], False
    for response in feeds:
        if isinstance(response, Exception) or response.status_code != 200:
            continue
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            continue
        items = root.findall("./channel/item")
        valid = valid or bool(items)
        jobs.extend(j for item in items if (j := parse_hire_item(item)))
    if not valid:
        raise ValueError("Agency feed unavailable")
    return "hireghana", jobs


def parse_glmis(soup, url):
    from catalogue import make_job

    title, employer = soup.select_one("#jobTitle"), soup.select_one("#employerName")
    marker = soup.select_one(".fa-map-marker")
    body_sections = soup.select(".pt-2:has(h5) p")
    if not title or not employer or not marker or not body_sections:
        raise ValueError("Government vacancy detail format changed")
    location = marker.parent.get_text(" ", strip=True)
    # Overseas placements can still include an Accra agency address in this field.
    if not ghana_location(location):
        return None
    container = title.parent.parent
    posted = re.search(
        r"Posted\s+(\d+)\s+(minute|hour|day|week|month|year)s?\s+ago",
        container.get_text(" ", strip=True),
        re.I,
    )
    if (
        not posted
        or int(posted[1])
        * {
            "minute": 1 / 1440,
            "hour": 1 / 24,
            "day": 1,
            "week": 7,
            "month": 30,
            "year": 365,
        }[posted[2].lower()]
        > 60
    ):
        return None
    clock = soup.select_one(".fa-clock")
    industry = soup.select_one(".fa-building")
    employment = (
        clock.parent.get_text(" ", strip=True).split(".")[0].strip() if clock else ""
    )
    body = " ".join(x.get_text(" ", strip=True) for x in body_sections)
    j = make_job(
        "glmis",
        url,
        title.get_text(" ", strip=True),
        employer.get_text(" ", strip=True),
        location,
        body,
        url,
        employment=employment,
        remote=bool(clock and re.search(r"\bremote\b", clock.parent.get_text(), re.I)),
        industry=industry.parent.get_text(" ", strip=True) if industry else "",
        check_url=url,
    )
    if j:
        j["source_posted_label"] = posted[0]
        return factual_summary(j, "GLMIS")
    return None


async def glmis(client):
    base = "https://www.glmis.gov.gh"
    urls = [f"{base}/jobs?page={n}" for n in range(1, 9)]
    urls += [f"{base}/Jobs/Joblistings?regionStateId={n}" for n in range(1, 17)]
    urls += [f"{base}/Jobs/Joblistings?jobTypeId={n}" for n in [2, 5]]
    indexes = await asyncio.gather(
        *(page(client, u) for u in urls), return_exceptions=True
    )
    links = set()
    for soup in indexes:
        if isinstance(soup, Exception):
            continue
        for a in soup.select('a[href*="/JobPostings/JobDetails/"]'):
            card = a.find_parent("div", class_="card")
            marker = card.select_one(".mdi-map-marker") if card else None
            if marker and FOREIGN_LOCATION.search(
                marker.parent.get_text(" ", strip=True)
            ):
                continue
            u = urljoin(base, a["href"])
            if on_host(u, "www.glmis.gov.gh") and re.fullmatch(
                r"/JobPostings/JobDetails/\d+", urlparse(u).path
            ):
                links.add(u)
    if not links:
        raise ValueError("Government board unavailable or changed")
    result = await asyncio.gather(
        *(page(client, u) for u in sorted(links)), return_exceptions=True
    )
    if any(
        isinstance(s, Exception)
        and not (
            isinstance(s, httpx.HTTPStatusError)
            and s.response.status_code in (404, 410)
        )
        for s in result
    ):
        raise ValueError("Government vacancy details were incomplete or changed format")
    return "glmis", [
        j
        for u, s in zip(sorted(links), result)
        if not isinstance(s, Exception) and (j := parse_glmis(s, u))
    ]


def embedded_json(raw, key):
    match = re.search(r'"' + re.escape(key) + r'"\s*:\s*\{', raw)
    if not match:
        raise ValueError("Public source data changed")
    return json.JSONDecoder().raw_decode(raw[match.end() - 1 :])[0]


def parse_newmont(soup, url):
    from catalogue import make_job, text

    raw = str(soup)
    detail = embedded_json(raw, "jobDetail")
    j = detail.get("data", {}).get("job", {})
    # Phenom includes a hidden 'job closed' template even on active pages.
    if (
        detail.get("status") != 200
        or j.get("postingStatus") != "Open"
        or j.get("country") != "Ghana"
    ):
        return None
    schema = next(
        (
            json.loads(s.string or "{}")
            for s in soup.select('script[type="application/ld+json"]')
            if '"JobPosting"' in (s.string or "")
        ),
        {},
    )
    if not schema or str(schema.get("identifier", {}).get("value")) != str(
        j.get("jobId")
    ):
        return None
    return make_job(
        "newmont",
        j["jobId"],
        schema.get("title") or j.get("title"),
        "Newmont",
        j.get("location", ""),
        text(schema.get("description")),
        url,
        posted=j.get("postedDate"),
        deadline=schema.get("validThrough"),
        employment=(
            "Full-time" if "FULL_TIME" in schema.get("employmentType", []) else ""
        ),
        industry=j.get("category", ""),
        check_url=url,
        active_confirmed=True,
        structured_salary=schema.get("baseSalary"),
    )


async def newmont(client):
    url = "https://jobs.newmont.com/us/en/search-results?keywords=Ghana"
    response = await client.get(url)
    response.raise_for_status()
    data = embedded_json(response.text, "eagerLoadRefineSearch")
    if data.get("status") != 200 or data.get("totalHits", 0) > data.get("hits", 0):
        raise ValueError("Employer search unavailable or requires pagination")
    rows = data.get("data", {}).get("jobs", [])
    links = []
    for j in rows:
        if j.get("country") != "Ghana" or not str(j.get("jobId", "")).isdigit():
            continue
        slug = re.sub(r"[^A-Za-z0-9]+", "-", j["title"]).strip("-")
        links.append(f"https://jobs.newmont.com/us/en/job/{j['jobId']}/{slug}")
    results = await asyncio.gather(*(page(client, u) for u in links))
    return "newmont", [j for u, s in zip(links, results) if (j := parse_newmont(s, u))]


def telecel_rows(soup):
    data = soup.select_one("input#jobs[value]")
    if not data:
        raise ValueError("Official career board changed")
    rows = json.loads(data["value"])
    if not isinstance(rows, list):
        raise ValueError("Official career board changed")
    return rows


def parse_telecel(row):
    from catalogue import make_job, text

    if (
        row.get("Country") != "Ghana"
        or not row.get("Publish")
        or row.get("Is_Locked")
        or not str(row.get("id", "")).isdigit()
    ):
        return None
    title = row.get("Posting_Title", "")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", title).strip("-")
    url = f"https://telecel.zohorecruit.com/jobs/Careers/{row['id']}/{slug}"
    j = make_job(
        "telecel",
        row["id"],
        title,
        "Telecel Ghana",
        f"{row.get('City') or 'Ghana'}, Ghana",
        text(row.get("Job_Description")),
        url,
        posted=row.get("Date_Opened"),
        deadline=row.get("Target_Date"),
        employment=row.get("Job_Type", ""),
        experience=row.get("Work_Experience") or "",
        industry=row.get("Industry", ""),
        remote=bool(row.get("Remote_Job")),
        check_url="https://telecel.zohorecruit.com/jobs/Careers",
        active_confirmed=True,
    )
    if j:
        j["employer_job_id"] = row["id"]
    return j


async def telecel(client):
    soup = await page(client, "https://telecel.zohorecruit.com/jobs/Careers")
    return "telecel", [j for row in telecel_rows(soup) if (j := parse_telecel(row))]


def tasks(client, archive_page=9):
    return [
        current_jobs(client, archive_page),
        hireghana(client),
        glmis(client),
        newmont(client),
        telecel(client),
    ]


async def recheck_tracked(client, rows, present):
    from catalogue import NOW, date

    async def one(row):
        job = row["payload"]
        if job["id"] in present or job.get("source_key") not in WINDOWED_SOURCES:
            return None
        if job.get("deadline") and date(job["deadline"]) < NOW():
            return None
        url = job.get("check_url")
        if not url:
            return None
        soup = await page(client, url)
        if job["source_key"] == "ghana-current-jobs":
            return parse_current_jobs(soup, url)
        if job["source_key"] == "glmis":
            return parse_glmis(soup, url)
        return None

    results = await asyncio.gather(*(one(row) for row in rows), return_exceptions=True)
    return [j for j in results if isinstance(j, dict)]
