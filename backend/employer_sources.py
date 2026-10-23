"""Fixed public employer sources with explicit Ghana eligibility and closure checks."""

import asyncio
import re
from urllib.parse import parse_qs, urljoin, urlparse

from ghana_sources import ghana_location, on_host, page

ASHBY_BOARDS = {"M-KOPA": "M-KOPA"}
FIDO_INDEX = "https://gh.fido.money/careers"
MPHARMA_INDEX = "https://erp.mpharma.com/jobs"
SOURCE_NAMES = ["ashby:" + board for board in ASHBY_BOARDS] + ["fido", "mpharma"]
SOURCE_INFO = {
    "ashby:M-KOPA": (
        "M-KOPA",
        "https://jobs.ashbyhq.com/M-KOPA",
        "Direct employer",
        "Published employer vacancies. Primary and secondary work locations are checked for Ghana.",
    ),
    "fido": (
        "Fido",
        FIDO_INDEX,
        "Direct employer",
        "Current vacancies on the official careers index, including Ghana national-service roles.",
    ),
    "mpharma": (
        "mPharma",
        MPHARMA_INDEX,
        "Direct employer",
        "Current openings on the employer's official ERPNext careers board, with explicit Ghana work locations.",
    ),
}


def ashby_url(board):
    if board not in ASHBY_BOARDS:
        raise ValueError("Unknown employer board")
    return f"https://api.ashbyhq.com/posting-api/job-board/{board}"


def ashby_jobs(data):
    if (
        not isinstance(data, dict)
        or data.get("apiVersion") != "1"
        or not isinstance(data.get("jobs"), list)
    ):
        raise ValueError("Employer feed format changed")
    if any(not isinstance(row, dict) for row in data["jobs"]):
        raise ValueError("Employer posting format changed")
    return data["jobs"]


def parse_ashby(row, board):
    from catalogue import make_job, REGIONS

    if (
        board not in ASHBY_BOARDS
        or not isinstance(row, dict)
        or not isinstance(row.get("isListed"), bool)
    ):
        raise ValueError("Employer posting format changed")
    if not row["isListed"]:
        return None
    secondary = row.get("secondaryLocations") or []
    if not isinstance(secondary, list) or any(
        not isinstance(location, dict) for location in secondary
    ):
        raise ValueError("Employer work locations changed")
    places = []
    for location in [row, *secondary]:
        address = location.get("address") or {}
        if not isinstance(address, dict):
            raise ValueError("Employer work address changed")
        address = address.get("postalAddress", address)
        if not isinstance(address, dict):
            raise ValueError("Employer work address changed")
        country = str(address.get("addressCountry") or "").casefold()
        label = str(location.get("location") or "")
        if country not in {"gh", "gha", "ghana"} and (
            country or not ghana_location(label)
        ):
            continue
        parts = [address.get("addressLocality"), address.get("addressRegion")]
        parts = [
            str(value)
            for value in parts
            if value and str(value).casefold() not in {"gh", "gha", "ghana"}
        ]
        places.append(", ".join(dict.fromkeys([*parts, "Ghana"])))
    if not places:
        return None
    title = str(row.get("title") or "").strip()
    job_url = str(row.get("jobUrl") or "")
    match = re.fullmatch(
        r"/" + re.escape(board) + r"/([a-fA-F0-9-]{36})/?", urlparse(job_url).path
    )
    if not on_host(job_url, "jobs.ashbyhq.com") or not match:
        raise ValueError("Employer posting URL changed")
    job_id = match[1]
    if row.get("id") and row["id"] != job_id:
        raise ValueError("Employer posting identity changed")
    apply_url = str(row.get("applyUrl") or job_url)
    job_path = urlparse(job_url).path.rstrip("/")
    apply_path = urlparse(apply_url).path.rstrip("/")
    if not on_host(apply_url, "jobs.ashbyhq.com") or not (
        apply_path == job_path or apply_path.startswith(job_path + "/")
    ):
        raise ValueError("Employer application URL changed")
    # Some boards publish only a country in the address but name the work towns
    # in the role title. Use that explicit suffix, never company-office addresses.
    suffix = re.search(r"\s[-–:]\s(.+)$", title)
    if suffix and any(
        re.search(r"\b" + re.escape(city) + r"\b", suffix[1], re.I)
        for cities in REGIONS.values()
        for city in cities
    ):
        places.insert(0, suffix[1])
    workplace = row.get("workplaceType")
    job = make_job(
        "ashby:" + board,
        job_id,
        title,
        ASHBY_BOARDS[board],
        " / ".join(dict.fromkeys(places)),
        row.get("descriptionPlain") or row.get("descriptionHtml") or "",
        apply_url,
        posted=row.get("publishedAt"),
        employment={
            "FullTime": "Full-time",
            "PartTime": "Part-time",
            "Intern": "Internship",
            "Contract": "Contract",
            "Temporary": "Temporary",
        }.get(row.get("employmentType"), ""),
        remote=workplace == "Remote" or not workplace and row.get("isRemote") is True,
        check_url=ashby_url(board),
        active_confirmed=True,
    )
    if not job:
        if (
            not title
            or len(str(row.get("descriptionPlain") or row.get("descriptionHtml") or ""))
            < 80
        ):
            raise ValueError("Employer posting details incomplete")
        return None
    job.update(
        source_url=job_url,
        source_urls=[job_url],
        employer_job_id=job_id,
        date_kind="source_updated",
    )
    return job


async def ashby(client, board):
    response = await client.get(ashby_url(board))
    response.raise_for_status()
    if urlparse(str(response.url)).hostname != "api.ashbyhq.com":
        raise ValueError("Employer feed redirected to another host")
    jobs = [
        job for row in ashby_jobs(response.json()) if (job := parse_ashby(row, board))
    ]
    return "ashby:" + board, jobs


def fido_cards(soup):
    wrapper = soup.select_one(".careers__career_list_wrapper")
    if wrapper is None or wrapper.select_one("a.w-pagination-next[href]"):
        raise ValueError("Employer careers index changed or needs pagination")
    cards = wrapper.select(".careers__career_list_item")
    if not cards and wrapper.select_one(".w-dyn-empty") is None:
        raise ValueError("Employer careers index changed")
    result = []
    for card in cards:
        link = card.select_one("a.careers__career_list_content_wrapper[href]")
        country = card.select_one('[fs-cmsfilter-field="country"]')
        if not link or not country:
            raise ValueError("Employer vacancy card changed")
        if not re.search(r"\bGhana\b", country.get_text(" ", strip=True), re.I):
            continue
        url = urljoin(FIDO_INDEX, link["href"])
        if not on_host(url, "gh.fido.money") or not re.fullmatch(
            r"/careers/[a-z0-9-]+", urlparse(url).path
        ):
            raise ValueError("Employer vacancy URL changed")
        result.append(url)
    return list(dict.fromkeys(result))


def parse_fido(soup, url):
    from catalogue import make_job

    title = soup.select_one("h1.vacancies-heading1")
    location = soup.select_one(".vacancies__location")
    sections = soup.select(".vacancies__rte")
    apply = [
        a for a in soup.select("a[href]") if a.get_text(" ", strip=True) == "Apply Now"
    ]
    if (
        not on_host(url, "gh.fido.money")
        or not title
        or not location
        or not sections
        or len(apply) != 1
    ):
        raise ValueError("Employer vacancy detail changed")
    if not re.search(r"\bGhana\b", location.get_text(" ", strip=True), re.I):
        return None
    target = apply[0]["href"]
    target_parts = urlparse(target)
    identifiers = parse_qs(target_parts.query).get("job", [])
    if (
        not on_host(target, "fidocredit.jh.frappe.cloud")
        or target_parts.path != "/apply"
        or len(identifiers) != 1
        or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", identifiers[0])
    ):
        raise ValueError("Employer application destination changed")
    body = "\n\n".join(section.get_text("\n", strip=True) for section in sections)
    if len(body) < 80:
        raise ValueError("Employer vacancy detail incomplete")
    job = make_job(
        "fido",
        url,
        title.get_text(" ", strip=True),
        "Fido",
        "Ghana",
        body,
        target,
        check_url=FIDO_INDEX,
        active_confirmed=True,
    )
    if job:
        job.update(source_url=url, source_urls=[url])
    return job


async def fido(client):
    links = fido_cards(await page(client, FIDO_INDEX))
    details = await asyncio.gather(*(page(client, url) for url in links))
    return "fido", [
        job for url, soup in zip(links, details) if (job := parse_fido(soup, url))
    ]


def tasks(client):
    return [
        *(ashby(client, board) for board in ASHBY_BOARDS),
        fido(client),
        mpharma(client),
    ]


def mpharma_cards(soup):
    cards = soup.select('main [name="card"][id][role="button"]')
    count = re.search(r"Showing\s+(\d+)\s+results", soup.get_text(" ", strip=True))
    if not count or int(count[1]) != len(cards) or len(cards) > 100:
        raise ValueError("Employer careers index is incomplete")
    links = []
    for card in cards:
        path = "/" + card["id"].lstrip("/")
        if not re.fullmatch(r"/jobs/[a-z0-9_]+/[a-z0-9-]+", path):
            raise ValueError("Employer vacancy URL changed")
        links.append("https://erp.mpharma.com" + path)
    return links


def parse_mpharma(soup, url):
    from catalogue import make_job

    main = soup.select_one("main")
    title = main.select_one("h1") if main else None
    body = main.select_one(".ql-editor") if main else None
    if not on_host(url, "erp.mpharma.com") or not title or not body:
        raise ValueError("Employer vacancy detail changed")
    facts = {}
    for label in main.select(".text-uppercase"):
        value = label.find_next_sibling("div")
        if value:
            facts[label.get_text(" ", strip=True).lower()] = value.get_text(
                " ", strip=True
            )
    location = facts.get("location", "")
    if not ghana_location(location):
        return None
    apply = {
        urljoin(url, a["href"])
        for a in main.select("a[href]")
        if a.get_text(" ", strip=True) == "Apply Now"
    }
    if len(apply) != 1:
        raise ValueError("Employer application link missing or ambiguous")
    target = apply.pop()
    p = urlparse(target)
    ids = parse_qs(p.query).get("job_title", [])
    if (
        not on_host(target, "erp.mpharma.com")
        or p.path != "/job_application/new"
        or len(ids) != 1
        or not re.fullmatch(r"[A-Za-z0-9-]{1,100}", ids[0])
    ):
        raise ValueError("Employer application destination changed")
    employment = facts.get("employment type", "")
    job = make_job(
        "mpharma",
        url,
        title.get_text(" ", strip=True),
        "mPharma",
        location,
        body.get_text("\n", strip=True),
        target,
        employment="Permanent" if "permanent" in employment.lower() else employment,
        check_url=MPHARMA_INDEX,
        active_confirmed=True,
    )
    if job:
        job.update(source_url=url, source_urls=[url], employment_label=employment)
    return job


async def mpharma(client):
    links = mpharma_cards(await page(client, MPHARMA_INDEX))
    details = await asyncio.gather(*(page(client, u) for u in links))
    return "mpharma", [
        j for u, soup in zip(links, details) if (j := parse_mpharma(soup, u))
    ]


async def recheck(client, job, response):
    """A missing entry in a complete employer index confirms source removal."""
    if job["source_key"].startswith("ashby:"):
        board = job["source_key"].split(":", 1)[1]
        for row in ashby_jobs(response.json()):
            if row.get("id") == job.get("employer_job_id") or row.get(
                "jobUrl"
            ) == job.get("source_url"):
                return parse_ashby(row, board)
        return None
    if job["source_key"] == "fido":
        from bs4 import BeautifulSoup

        links = fido_cards(BeautifulSoup(response.text, "html.parser"))
        url = job.get("source_url")
        if url not in links:
            return None
        return parse_fido(await page(client, url), url)
    if job["source_key"] == "mpharma":
        from bs4 import BeautifulSoup

        links = mpharma_cards(BeautifulSoup(response.text, "html.parser"))
        url = job.get("source_url")
        if url not in links:
            return None
        return parse_mpharma(await page(client, url), url)
    raise ValueError("Unknown employer source")
