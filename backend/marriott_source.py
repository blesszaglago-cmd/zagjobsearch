"""Complete, bounded public Marriott Ghana index and individual posting checks."""

import asyncio
import json
import math
import re
from urllib.parse import urljoin, urlparse

from ghana_sources import on_host, page

BASE = "https://careers.marriott.com"
COUNTRY_FILTER = "filter%5Bcountry%5D%5B0%5D=Ghana"
INDEX = BASE + "/jobs?" + COUNTRY_FILTER
SOURCE_NAMES = ["marriott-ghana"]
SOURCE_INFO = {
    "marriott-ghana": (
        "Marriott International",
        INDEX,
        "Direct employer",
        "All pages of the public Ghana-filtered careers index, bounded to 100 postings. Individual schema locations must also confirm Ghana. A trainee title alone does not prove a graduate programme or internship.",
    )
}


def vacancy_url(value):
    url = urljoin(BASE, value)
    parsed = urlparse(url)
    if (
        not on_host(url, "careers.marriott.com")
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/[^/?#]+/job/P\d+-\d+-\d+", parsed.path)
    ):
        raise ValueError("Employer vacancy URL changed")
    return url


def parse_index(soup):
    root = soup.select_one("main")
    body = root.get_text(" ", strip=True) if root else ""
    count = re.search(r"Showing\s+\d+\s*[-–]\s*\d+\s+of\s+(\d+)\s+jobs", body, re.I)
    if not count:
        if root and re.search(
            r"no (?:jobs|results|current openings) found", body, re.I
        ):
            return 0, set()
        raise ValueError("Employer Ghana index changed")
    total = int(count[1])
    if total > 100:
        raise ValueError("Employer Ghana index exceeds its bounded complete snapshot")
    links = {vacancy_url(a["href"]) for a in root.select('a[href*="/job/"]')}
    if total and not links:
        raise ValueError("Employer vacancy cards missing")
    return total, links


async def index_links(client):
    total, links = parse_index(await page(client, INDEX))
    remaining = await asyncio.gather(
        *(
            page(client, BASE + f"/jobs/page/{n}?" + COUNTRY_FILTER)
            for n in range(2, math.ceil(total / 10) + 1)
        )
    )
    for soup in remaining:
        page_total, extra = parse_index(soup)
        if page_total != total:
            raise ValueError("Employer index changed during pagination")
        links.update(extra)
    if len(links) != total:
        raise ValueError("Employer Ghana pagination incomplete")
    return links


def parse_detail(soup, url):
    from catalogue import make_job, text

    url = vacancy_url(url)
    jobs = []
    for node in soup.select('script[type="application/ld+json"]'):
        data = json.loads(node.string or "{}")
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            jobs.append(data)
    if len(jobs) != 1:
        raise ValueError("Employer posting schema missing or ambiguous")
    data = jobs[0]
    if (
        data.get("url") != url
        or data.get("identifier", {}).get("value") != urlparse(url).path.split("/")[-1]
    ):
        raise ValueError("Employer posting identity changed")
    locations = data.get("jobLocation", [])
    locations = locations if isinstance(locations, list) else [locations]
    places = []
    for location in locations:
        address = location.get("address", {})
        if address.get("addressCountry") not in ("GH", "Ghana"):
            continue
        places.append(
            ", ".join(
                dict.fromkeys(
                    filter(
                        None,
                        [
                            address.get("addressLocality"),
                            address.get("addressRegion"),
                            "Ghana",
                        ],
                    )
                )
            )
        )
    if not places:
        return None
    employment = data.get("employmentType", [])
    employment = employment if isinstance(employment, list) else [employment]
    return make_job(
        "marriott-ghana",
        url,
        data.get("title", ""),
        "Marriott International",
        "; ".join(places),
        text(data.get("description")),
        url,
        posted=data.get("datePosted"),
        deadline=data.get("validThrough"),
        employment=" ".join(
            {
                "FULL_TIME": "Full-time",
                "PART_TIME": "Part-time",
                "CONTRACTOR": "Contract",
                "INTERN": "Internship",
            }.get(value, value)
            for value in employment
        ),
        check_url=url,
        active_confirmed=True,
        industry="Hospitality and tourism",
        structured_salary=data.get("baseSalary"),
    )


async def collect(client):
    links = sorted(await index_links(client))
    details = await asyncio.gather(*(page(client, url) for url in links))
    return "marriott-ghana", [
        job for url, detail in zip(links, details) if (job := parse_detail(detail, url))
    ]


async def recheck(client, job, response):
    url = vacancy_url(job["check_url"])
    if str(response.url) != url:
        raise ValueError("Employer posting redirected")
    if url not in await index_links(client):
        return None
    from bs4 import BeautifulSoup

    return parse_detail(BeautifulSoup(response.text, "html.parser"), url)
