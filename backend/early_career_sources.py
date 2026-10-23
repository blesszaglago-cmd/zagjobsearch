"""Public Ghana internship and apprenticeship sources with bounded checks."""

import asyncio
import re
from datetime import timedelta
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from ghana_sources import on_host, page

VOTEX = "https://careers.votex365.com"
UG = "https://www.ug.edu.gh"
NAP = "https://nap.nya.gov.gh"
NAP_INFO = "https://nya.gov.gh/nap"
SOURCE_NAMES = ["votex365", "ug-careers", "nya-apprenticeship"]
WINDOWED_SOURCES = {"ug-careers"}
SOURCE_INFO = {
    "votex365": (
        "Votex 365",
        VOTEX + "/jobs",
        "Direct employer",
        "Individual Ghana internship roles on the employer's current public careers index. Pay and closing dates remain unknown when not stated.",
    ),
    "ug-careers": (
        "University of Ghana Careers and Counselling Centre",
        UG + "/careers/career-services",
        "University careers service",
        "Recent Ghana internship announcements with named employers. Without a deadline, notices expire from this discovery window after 14 days.",
    ),
    "nya-apprenticeship": (
        "National Youth Authority",
        NAP_INFO,
        "Government apprenticeship programme",
        "National Apprenticeship Programme registration, checked against the Authority's conditions and its public portal. Registration does not guarantee a training place or employment.",
    ),
}


def votex_groups(index):
    root = index.select_one("main")
    if not root:
        raise ValueError("Internship index changed")
    groups = {}
    for card in root.select('a[href^="/internships#"]'):
        parsed = urlparse(card["href"])
        if not re.fullmatch(r"[a-z-]{2,40}", parsed.fragment):
            raise ValueError("Internship group URL changed")
        heading = card.select_one("h2")
        if not heading or not re.search(r"\bGhana\b", card.get_text(" ", strip=True)):
            raise ValueError("Internship location unconfirmed")
        groups[parsed.fragment] = card.get_text(" ", strip=True)
    if not groups and not re.search(
        r"no (?:open|active|current) (?:roles|opportunities|internships)",
        root.get_text(" ", strip=True),
        re.I,
    ):
        raise ValueError("Internship index no longer confirms active roles")
    return groups


def parse_votex(index, detail):
    from catalogue import make_job

    groups = votex_groups(index)
    root = detail.select_one("main")
    if not root or not re.search(r"Now Hiring", root.get_text(" ", strip=True), re.I):
        if groups:
            raise ValueError("Employer internship application window changed")
        return []
    jobs = []
    for group in groups:
        section = root.find(id=group)
        cards = section.select("article") if section else []
        if not cards or len(cards) > 20:
            raise ValueError("Individual internship roles changed")
        for card in cards:
            title = card.select_one("h3")
            if not title or not card.select_one("a[href]"):
                raise ValueError(
                    "Internship requirements or application instructions missing"
                )
            job = make_job(
                "votex365",
                group + ":" + title.get_text(" ", strip=True),
                title.get_text(" ", strip=True),
                "Votex 365",
                "Ghana",
                card.get_text("\n", strip=True)
                + "\nInternship. Applicants should be digitally proficient, comfortable learning collaboration tools and reliable team members. Read the employer's internship page for its current requirements and email application instructions.",
                VOTEX + "/internships#" + group,
                employment="Internship",
                check_url=VOTEX + "/jobs",
                active_confirmed=True,
            )
            if job:
                job["source_urls"] = [job["url"], VOTEX + "/jobs"]
                job["deadline_note"] = (
                    "No closing date stated; current employer index checked."
                )
                jobs.append(job)
    return jobs


async def votex(client):
    index, detail = await asyncio.gather(
        page(client, VOTEX + "/jobs"), page(client, VOTEX + "/internships")
    )
    return "votex365", parse_votex(index, detail)


def ug_cards(index):
    from catalogue import NOW, date

    rows = index.select(".views-row:has(.views-field-created)")
    if not rows:
        raise ValueError("University careers index changed")
    result = []
    for row in rows:
        link = row.select_one('.views-field-title a[href*="/careers/announcements/"]')
        clock = row.select_one("time[datetime]")
        posted = date(clock["datetime"]) if clock else None
        if not link or not posted or not NOW() - timedelta(days=14) <= posted <= NOW():
            continue
        if not re.search(r"intern(?:ship)?", row.get_text(" ", strip=True), re.I):
            continue
        url = urljoin(UG, link["href"])
        if (
            not on_host(url, "www.ug.edu.gh")
            or not re.fullmatch(
                r"/careers/announcements/[a-z0-9-]+", urlparse(url).path
            )
            or urlparse(url).query
        ):
            raise ValueError("University vacancy link changed")
        result.append((url, posted))
    return result


def parse_ug(soup, url, posted):
    from catalogue import make_job

    body = soup.select_one("main .field--name-body")
    if not body:
        raise ValueError("University vacancy detail changed")
    text = re.sub(r"\s+", " ", body.get_text(" ", strip=True))
    # A careers event or a general internship-letter page is not a vacancy.
    match = next(
        (
            m
            for paragraph in body.select("p")
            if (
                m := re.fullmatch(
                    r"(.+?) is hiring ([^.!?]+?\bInterns?) in (Accra, Ghana)\.?",
                    re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)),
                    re.I,
                )
            )
        ),
        None,
    )
    if not match:
        return None
    job = make_job(
        "ug-careers",
        url,
        match[2],
        match[1].strip(),
        match[3],
        text,
        url,
        posted=posted.isoformat(),
        employment="Internship",
        check_url=url,
    )
    if job:
        job["source"] = SOURCE_INFO["ug-careers"][0]
        job["deadline_note"] = (
            "Closing date not published. A recent university announcement is evidence of publication, not a guarantee of an unfilled role."
        )
    return job


async def ug_careers(client):
    cards = ug_cards(await page(client, SOURCE_INFO["ug-careers"][1]))
    details = await asyncio.gather(*(page(client, url) for url, _ in cards))
    return "ug-careers", [
        job
        for (url, posted), detail in zip(cards, details)
        if (job := parse_ug(detail, url, posted))
    ]


def parse_nap(overview, landing, asset):
    from catalogue import make_job, REGIONS

    body = overview.get_text(" ", strip=True)
    conditions = [
        r"Must be a Ghanaian citizen",
        r"between 15 and 40 years",
        r"no minimum academic qualification",
        r"resident in the community, district, or region",
    ]
    if not all(re.search(p, body, re.I) for p in conditions):
        raise ValueError("Apprenticeship eligibility changed")
    official_link = any(
        urlparse(a["href"]).hostname in {"nap.nya.gov.gh", "www.nap.nya.gov.gh"}
        for a in overview.select("a[href]")
    )
    if not official_link or not landing.select_one('script[src^="/assets/index-"]'):
        raise ValueError("Official apprenticeship portal changed")
    # The portal is a public client-rendered page. Read its published marketing
    # asset as text; never execute it or submit an applicant's form.
    if (
        not re.search(r'kicker:\s*["\']Applications are open["\']', asset)
        or '"/apply/apprentice"' not in asset
    ):
        raise ValueError("Apprenticeship registration window unconfirmed")
    job = make_job(
        "nya-apprenticeship",
        "national-apprenticeship-programme",
        "National Apprenticeship Programme: apprentice registration",
        "National Youth Authority",
        "Ghana, all regions",
        "Free technical and vocational apprenticeship training across Ghana. Applicants must be Ghanaian, aged 15 to 40 and resident where the training takes place. No minimum academic qualification is required. Unemployed, underemployed and skills-certification applicants can apply. Training spans several trades and includes workplace learning. Registration does not guarantee selection, a placement or paid employment. Read the Authority's conditions and apply through its official portal.",
        NAP + "/apply/apprentice",
        employment="Apprenticeship",
        check_url=NAP_INFO,
        active_confirmed=True,
    )
    job["source_url"] = NAP_INFO
    job["regions"] = list(REGIONS)
    sectors = [
        label
        for label in [
            "Agriculture",
            "Manufacturing",
            "ICT",
            "Fashion",
            "Construction",
            "Renewable Energy",
            "Hospitality",
            "Mechanical",
            "Electrical",
        ]
        if re.search(r"\b" + re.escape(label) + r"\b", body, re.I)
    ]
    job["search_terms"] = list(dict.fromkeys([*job.get("search_terms", []), *sectors]))
    job["industry"] = ", ".join(sectors)
    job["source_urls"] = [NAP_INFO, NAP + "/"]
    job["deadline_note"] = (
        "The public portal advertises open registration without a closing date. Training allocation and selection conditions apply."
    )
    job["verification"] = (
        "Official programme conditions and public registration portal checked"
    )
    return job


async def nap(client):
    overview, landing = await asyncio.gather(
        page(client, NAP_INFO), page(client, NAP + "/")
    )
    assets = [
        s["src"]
        for s in landing.select("script[src]")
        if re.fullmatch(r"/assets/index-[A-Za-z0-9_-]+\.js", s["src"])
    ]
    if len(assets) != 1:
        raise ValueError("Public apprenticeship application changed")
    response = await client.get(NAP + assets[0])
    response.raise_for_status()
    if (
        not on_host(str(response.url), "nap.nya.gov.gh")
        or len(response.content) > 4_000_000
    ):
        raise ValueError("Public apprenticeship asset redirected or exceeded its bound")
    return "nya-apprenticeship", [parse_nap(overview, landing, response.text)]


def tasks(client):
    return [votex(client), ug_careers(client), nap(client)]


async def recheck(client, job):
    reader = {"votex365": votex, "ug-careers": ug_careers, "nya-apprenticeship": nap}[
        job["source_key"]
    ]
    _, rows = await reader(client)
    return next((row for row in rows if row["id"] == job["id"]), None)
