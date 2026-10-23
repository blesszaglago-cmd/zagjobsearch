"""Public academic funding indexes, with Ghana eligibility and honest deadlines.

These are source-linked summaries, not generated scholarship adverts. University
calls can require institutional nomination, a research team or a foreign partner.
"""

import asyncio
import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlparse
from zoneinfo import ZoneInfo

from ghana_sources import on_host, page

DAAD = "https://www.daad-ghana.org/en/find-funding/scholarship-database/"
DAAD_INDEX = DAAD + "?origin=145&target=145&onlydaad=1"
UG = "https://rid.ug.edu.gh"
KNUST = "https://ogr.knust.edu.gh"
PRIMARY_CALLS = {
    KNUST
    + "/funding/african-scholars-research-funding-j-pal-digifi-africa": "https://www.povertyactionlab.org/initiative/digifi-request-proposals",
}
SOURCE_NAMES = ["daad-ghana", "ug-research", "knust-research"]
WINDOWED_SOURCES = {"ug-research"}
SOURCE_INFO = {
    "daad-ghana": (
        "DAAD Ghana funding database",
        DAAD,
        "Scholarships and research",
        "All pages of DAAD-funded programmes with Ghana selected as country of origin. Programme conditions still apply.",
    ),
    "ug-research": (
        "University of Ghana Research and Innovation Directorate",
        UG + "/call-for-applications",
        "University research funding",
        "Recent public research calls and the scholarship directory. Institutional and partner requirements are retained.",
    ),
    "knust-research": (
        "KNUST Office of Grants and Research",
        KNUST + "/funding",
        "University research funding",
        "Public funding calls with explicit Ghana, African or international applicant eligibility. Restricted foreign-only calls are excluded.",
    ),
}
DATE_TOKEN = r"(?:\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4}|[A-Za-z]+\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}|\d{1,2}\.\d{1,2}\.\d{4})"


def academic_date(value):
    """Preserve an explicit closing time/zone; never turn a programme year into a date."""
    from catalogue import date

    raw = re.sub(r"(\d)\s*(?:st|nd|rd|th)\b", r"\1", str(value), flags=re.I)
    match = re.search(DATE_TOKEN, raw, re.I)
    if not match:
        return date(raw) if re.match(r"\d{4}-\d{2}-\d{2}T", raw) else None
    token = match[0]
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", token):
        token = datetime.strptime(token, "%d.%m.%Y").strftime("%Y-%m-%d")
    result = date(token)
    if not result:
        return None
    tail = raw[match.end() :]
    time = re.search(r"\b(\d{1,2}):([0-5]\d)(?:\s*(a\.?m\.?|p\.?m\.?))?", tail, re.I)
    zone = next(
        (
            z
            for pattern, z in [
                (r"CET|CEST|Central European", "Europe/Berlin"),
                (r"\bEDT\b|\bEST\b|Eastern Time", "America/New_York"),
                (r"\bUTC\b|\bGMT\b", "UTC"),
            ]
            if re.search(pattern, tail, re.I)
        ),
        None,
    )
    if time:
        hour = int(time[1])
        if time[3]:
            hour = hour % 12 + (12 if time[3].lower().startswith("p") else 0)
        if hour > 24 or hour == 24 and int(time[2]):
            return None
        result = result.replace(hour=hour % 24, minute=int(time[2]), second=0)
        if hour == 24:
            result += timedelta(days=1)
    if zone:
        result = result.replace(tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)
    return result


def opportunity_kind(title, body=""):
    if re.search(r"re-invitation|research stays", title, re.I):
        return "fellowship"
    if re.search(r"fellowship", title, re.I):
        return "fellowship"
    if re.search(r"scholarship|bursary|doctoral (?:programme|degree)", title, re.I):
        return "scholarship"
    if re.search(r"prize|\baward\b", title, re.I):
        return "research-award"
    if re.search(r"research|grant|fund", title, re.I):
        return "research-grant"
    if re.search(r"summer course|summer school|training|traineeship", title, re.I):
        return "training"
    if re.search(r"research (?:grant|fund|project)|funding opportunity", body, re.I):
        return "research-grant"
    return "other-funding"


def study_levels(title, offered):
    # Prior qualifications are not the qualification being funded.
    text = (
        title
        + " "
        + " ".join(
            part
            for part in re.split(r"[\n.!?]", offered)
            if not re.search(
                r"must (?:hold|have)|hold a|already completed|first degree|PhD holders|postdoctoral level or above",
                part,
                re.I,
            )
        )
    )
    return [
        key
        for key, pattern in [
            ("undergraduate", r"undergraduate|bachelor.{0,25}(?:course|degree|stud)"),
            (
                "masters",
                r"master(?! of philosophy).{0,25}(?:degree|course|stud|programme)|master[’']?s",
            ),
            ("mphil", r"\bm\.?phil\b|master of philosophy"),
            (
                "phd",
                r"\bph\.?d\b|doctoral (?:degree|programme|student|candidate)|doctorate",
            ),
            ("postdoc", r"post[ -]?doc(?:toral)?(?: phase| research| fellowship|s)?\b"),
        ]
        if re.search(pattern, text, re.I)
    ]


def make_academic(
    source,
    url,
    title,
    summary,
    *,
    deadline=None,
    posted=None,
    kind=None,
    levels=None,
    destination="unspecified",
    eligibility="",
    rolling=False,
    deadline_note="",
    study_location=None,
    source_info=None,
):
    from catalogue import NOW, scholarship_state

    job = {
        "id": hashlib.sha256((source + ":" + url).encode()).hexdigest()[:32],
        "source_key": source,
        "source": (source_info or SOURCE_INFO)[source][0],
        "title": title,
        "company": (source_info or SOURCE_INFO)[source][0],
        "location": study_location
        or {
            "ghana": "Study / research in Ghana",
            "abroad": "Study / research abroad",
        }.get(destination, "See official funding call"),
        "regions": [],
        "description": summary[:6000],
        "description_kind": "source_summary",
        "url": url,
        "source_url": url,
        "source_urls": [url],
        "created": posted.isoformat() if posted else None,
        "date_kind": "published" if posted else "not_provided",
        "deadline": deadline.isoformat() if deadline else None,
        "deadline_note": deadline_note,
        "application_window": (
            "rolling" if rolling else "deadline" if deadline else "not_provided"
        ),
        "job_type": kind or opportunity_kind(title),
        "category": "scholarships",
        "experience": "unspecified",
        "industry": "",
        "remote": False,
        "study_levels": levels or [],
        "study_destination": destination,
        "funding": "unspecified",
        "eligibility_note": eligibility,
        "checked_at": NOW().isoformat(),
        "check_url": url,
        "verification": "Official academic source checked; programme conditions apply",
    }
    job["listing_status"] = scholarship_state(job)
    job["can_apply"] = job["listing_status"] == "open"
    return job


def daad_url(url, *, detail=False):
    parsed = urlparse(urljoin(DAAD, url))
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        not on_host(parsed.geturl(), "www.daad-ghana.org")
        or parsed.path != urlparse(DAAD).path
    ):
        raise ValueError("Funding database URL changed")
    # Repeated parameters in the public pagination links use the last value.
    values = {k: v[-1] for k, v in query.items()}
    if values.get("origin") != "145" or values.get("target") != "145":
        raise ValueError("Funding database lost the Ghana selection")
    identity = values.get("detail_to_show", "0")
    if detail and not re.fullmatch(r"[1-9]\d{7}", identity):
        raise ValueError("Funding programme identity changed")
    if not re.fullmatch(r"\d{1,3}", values.get("pg", "1")):
        raise ValueError("Funding pagination changed")
    # Canonical identity survives source pagination and filter-order changes.
    clean = {
        "origin": "145",
        "target": "145",
        "status": "0",
        "type": "a",
        "onlydaad": "1",
    }
    if detail:
        clean["detail_to_show"] = identity
    else:
        clean["pg"] = values.get("pg", "1")
    return DAAD + "?" + urlencode(clean)


def parse_daad_index(soup):
    from catalogue import NOW

    selected = soup.select_one('select[name="origin"] option[selected]')
    cards = soup.select(".c-scholarship-list__item")
    if not selected or selected.get("value") != "145" or not cards:
        raise ValueError("Funding database Ghana index changed")
    jobs = []
    for card in cards:
        title = card.select_one("h3 a[href]")
        teaser = card.select_one("p")
        if not title or not teaser:
            raise ValueError("Funding programme summary changed")
        url = daad_url(title["href"], detail=True)
        facts = {}
        for label in card.select("dt"):
            value = label.find_next_sibling("dd")
            if value:
                facts[label.get_text(" ", strip=True).strip(": ").lower()] = (
                    value.get_text(" ", strip=True)
                )
        raw = facts.get("application deadline", "")
        # Only deadline tokens, not selection dates or programme starting years.
        dates = [
            academic_date(m[0]) for m in re.finditer(r"\d{1,2}\.\d{1,2}\.\d{4}", raw)
        ]
        annual = re.search(r"(\d{1,2}\s+[A-Za-z]+) of each year", raw, re.I)
        opening = re.search(
            r"(?:possible|open) from\s+(\d{1,2}\s+[A-Za-z]+) each year", raw, re.I
        )
        if annual and opening:
            opening_date = academic_date(opening[1] + " " + str(NOW().year))
            if opening_date:
                opening_date = opening_date.replace(hour=0, minute=0, second=0)
            year = (
                NOW().year if opening_date and opening_date <= NOW() else NOW().year - 1
            )
            ending = re.search(r"\b\d{1,2}:\d{2}.*?(?:\)|\.|$)", raw)
            dates.append(
                academic_date(
                    annual[1] + " " + str(year) + " " + (ending[0] if ending else "")
                )
            )
        dates = [d for d in dates if d]
        deadline = min(
            (d for d in dates if d >= NOW()), default=max(dates, default=None)
        )
        # Recurring deadlines without a year remain unconfirmed. Never invent the next cycle.
        rolling = bool(
            re.search(
                r"applications? (?:can be submitted|accepted|possible) (?:at any time|throughout the year)|no (?:fixed )?deadline|rolling (?:applications|submissions)",
                raw,
                re.I,
            )
        )
        name = title.get_text(" ", strip=True)
        offered = teaser.get_text(" ", strip=True)
        status = facts.get("status", "")
        levels = study_levels(name, offered)
        if "Postdoctoral researchers" in status and "postdoc" not in levels:
            levels.append("postdoc")
        summary = f"{name}. {offered}\nApplicant categories listed by DAAD: {status or 'See programme requirements'}.\nDeadline information from DAAD: {raw or 'Not provided'}.\nRead the original programme for funding amounts, required documents and the application procedure."
        jobs.append(
            make_academic(
                "daad-ghana",
                url,
                name,
                summary,
                deadline=deadline,
                rolling=rolling,
                levels=levels,
                destination=(
                    "abroad"
                    if re.search(
                        r"in Germany|German universit", name + " " + offered, re.I
                    )
                    else "unspecified"
                ),
                study_location="See DAAD programme for study / research location",
                eligibility="Listed in DAAD's Ghana-origin selection. Nationality, residence, academic and programme-specific requirements still apply.",
                deadline_note=raw,
            )
        )
    return jobs


async def daad(client):
    first = await page(client, DAAD_INDEX)
    rows = parse_daad_index(first)
    match = re.search(
        r"([\d,]+)\s+Scholarship Options", first.get_text(" ", strip=True), re.I
    )
    if not match:
        raise ValueError("Funding database total missing")
    expected = int(match[1].replace(",", ""))
    pages = {
        daad_url(o["value"])
        for o in first.select("select option[value]")
        if "pg=" in o["value"]
    }
    if len(pages) > 25 or expected > 125:
        raise ValueError("Funding database requires a larger complete crawl")
    pages.discard(daad_url("?origin=145&target=145&pg=1"))
    for soup in await asyncio.gather(*(page(client, u) for u in sorted(pages))):
        rows.extend(parse_daad_index(soup))
    unique = {j["id"]: j for j in rows}
    if len(unique) != expected:
        raise ValueError("Funding database pagination incomplete")
    return "daad-ghana", list(unique.values())


def university_url(url, source):
    base = UG if source == "ug-research" else KNUST
    url = urljoin(base, url).split("#")[0]
    parsed = urlparse(url)
    valid_path = (
        re.fullmatch(r"/(?:index.php/)?node/\d+", parsed.path)
        if source == "ug-research"
        else re.fullmatch(r"/funding/[a-z0-9-]+", parsed.path)
    )
    if not on_host(url, urlparse(base).hostname) or not valid_path or parsed.query:
        raise ValueError("University funding detail URL changed")
    return url.replace("/index.php/node/", "/node/")


def parse_university(soup, url, source):
    from catalogue import date, scholarship_deadline

    university_url(url, source)
    if source == "ug-research":
        content = soup.select_one("#block-mainpagecontent article")
        title_node = content.select_one("h3") if content else None
        article = content.select_one(".page-image") if content else None
        if content and not article:
            article = content.select_one(".node__content")
            title_node = soup.select_one("title")
        published = content.select_one(".date-social p") if content else None
        deadline_value = None
        for box in content.select(".deadline-details h6") if content else []:
            if box.get_text(" ", strip=True).lower() == "deadline":
                deadline_value = box.find_next_sibling("p")
        raw = deadline_value.get_text(" ", strip=True) if deadline_value else ""
    else:
        content = soup.select_one("main")
        title_node = content.select_one("h1") if content else None
        article = content.select_one(".event-discription") if content else None
        published = None
        time = content.select_one(".event-time time[datetime]") if content else None
        raw = time["datetime"] if time else ""
    if not title_node or not article or len(article.get_text(" ", strip=True)) < 80:
        raise ValueError(
            "University funding detail format changed: " + urlparse(url).path
        )
    title = title_node.get_text(" ", strip=True).split(" | ")[0].strip()
    body = article.get_text(" ", strip=True)
    if re.search(
        r"evidence of sufficient funds|institutional fee payable", body, re.I
    ) and not re.search(r"scholarship|fellowship", title, re.I):
        return None
    if source == "knust-research":
        # Primary DAAD data is connected; university reposts can carry conflicting dates.
        if re.search(r"\bDAAD\b|German Academic Exchange", title + " " + body, re.I):
            return None
        # A Ghana university mentioning a call is not sufficient nationality proof.
        eligible = bool(
            re.search(
                r"(?:Ghanaian|African) (?:nationals|citizens|scholars|researchers|institutions)|sub-Saharan African institutions|all countries|any nationality|no geographic(?:al)? (?:limitations|restrictions)|international students|researchers (?:from|in) (?:Africa|developing countries)",
                body,
                re.I,
            )
        )
        if not eligible:
            return None
    elif not re.search(
        r"University community|University of Ghana|UG (?:staff|researchers)|Ghanaian",
        body,
        re.I,
    ):
        return None
    # Exclude clearly foreign-only eligibility, even when the university advertises it.
    if re.search(
        r"(?:only|exclusively) (?:for |to )?(?:UK|US|British|American|German) (?:citizens|nationals|residents)|applicants must be (?:UK|US|British|American|German) citizens",
        body,
        re.I,
    ):
        return None
    rolling = bool(
        re.search(
            r"no fixed deadline|rolling (?:applications|submissions)|applications? (?:accepted|can be submitted) (?:at any time|throughout the year)",
            body,
            re.I,
        )
    )
    body_deadline = scholarship_deadline({}, body)
    # Narrative rolling windows take precedence over year-end placeholder metadata.
    deadline = None if rolling else academic_date(raw) or body_deadline
    if source == "knust-research" and body_deadline:
        deadline = body_deadline if not deadline else min(deadline, body_deadline)
    kind = opportunity_kind(title, body)
    paragraphs = [p.get_text(" ", strip=True) for p in article.select("p,li")]
    eligibility = next(
        (
            p
            for p in paragraphs
            if re.search(
                r"eligib|applicants must|who can apply|both applicants|only three|African Scholars",
                p,
                re.I,
            )
        ),
        "",
    )
    note = f"Published for {('University of Ghana' if source == 'ug-research' else 'KNUST')} applicants. {eligibility[:650]} Institutional affiliation, nomination and collaborator requirements may apply."
    heading = next(
        (
            i
            for i, p in enumerate(paragraphs)
            if re.fullmatch(r"eligibility(?: criteria)?\s*:?", p, re.I)
        ),
        None,
    )
    if heading is not None:
        eligibility = " ".join(paragraphs[heading + 1 : heading + 4])[:900]
        note = f"Published for {('University of Ghana' if source == 'ug-research' else 'KNUST')} applicants. {eligibility[:650]} Institutional affiliation, nomination and collaborator requirements may apply."
    # Do not label a grant requiring an existing PhD as a PhD degree scholarship.
    levels = (
        study_levels(title, "")
        or study_levels(
            title,
            " ".join(paragraphs[:heading] if heading is not None else paragraphs[:3]),
        )
        if kind in {"scholarship", "fellowship", "training"}
        else []
    )
    offered = paragraphs[0][:650] if paragraphs else title
    summary = f"{title}.\n{offered}\nEligibility and application conditions: {note}\nRead the official call for the complete criteria, funding terms and submission instructions."
    return make_academic(
        source,
        url,
        title,
        summary,
        deadline=deadline,
        rolling=rolling,
        kind=kind,
        levels=levels,
        posted=date(published.get_text(" ", strip=True)) if published else None,
        eligibility=note,
        deadline_note="Rolling applications; see source conditions" if rolling else raw,
    )


async def university(client, source):
    base, path, selector, limit = (
        (UG, "/call-for-applications", "#block-views-block-applications-block-1", 12)
        if source == "ug-research"
        else (KNUST, "/funding", "main", 10)
    )
    pending, visited, links = [base + path], set(), set()
    while pending:
        url = pending.pop(0)
        if url in visited:
            continue
        if len(visited) >= limit:
            if source in WINDOWED_SOURCES:
                break
            raise ValueError("University pagination incomplete")
        visited.add(url)
        soup = await page(client, url)
        root = soup.select_one(selector)
        cards = (
            root.select(
                ".publication-content h4 a[href]"
                if source == "ug-research"
                else ".views-row a[href]"
            )
            if root
            else []
        )
        if not cards:
            raise ValueError("University funding index changed")
        for a in cards:
            links.add(university_url(a["href"], source))
        for a in root.select('a[rel="next"],.pager__item--next a[href]'):
            next_url = urljoin(base + path, a["href"])
            p = urlparse(next_url)
            if (
                on_host(next_url, urlparse(base).hostname)
                and p.path.replace("/index.php/", "/") == path
                and re.fullmatch(r"page=\d+", p.query)
            ):
                pending.append(base + path + "?" + p.query)
    if source == "ug-research":
        directory = await page(client, UG + "/node/319")
        root = directory.select_one("#block-orid-scholarships")
        if not root:
            raise ValueError("University scholarship directory changed")
        links.update(
            university_url(a["href"], source) for a in root.select('a[href*="/node/"]')
        )
    details = await asyncio.gather(*(page(client, u) for u in sorted(links)))
    rows = [
        j
        for u, soup in zip(sorted(links), details)
        if (j := parse_university(soup, u, source))
    ]
    rows = await asyncio.gather(*(confirm_primary(client, j) for j in rows))
    return source, merge_notices(rows)


def merge_notices(rows):
    """Merge reposts of the same named funding round, preserving both notice links."""
    grouped = {}
    for row in sorted(
        rows, key=lambda j: (j.get("created") or "", j["id"]), reverse=True
    ):
        key = (
            row["source_key"],
            re.sub(r"\W", "", row["title"]).casefold(),
            row.get("deadline") or row["id"],
        )
        if key not in grouped:
            grouped[key] = row
        else:
            primary = grouped[key]
            primary["source_urls"] = list(
                dict.fromkeys(primary["source_urls"] + row["source_urls"])
            )
    return list(grouped.values())


async def confirm_primary(client, job):
    """A rolling university repost also needs the funder's current acceptance signal."""
    from catalogue import scholarship_state

    target = PRIMARY_CALLS.get(job["source_url"])
    if not target:
        return job
    primary = await page(client, target)
    heading = primary.select_one("h1")
    body = primary.get_text(" ", strip=True)
    if not heading or "DigiFI Request for Proposals" not in heading.get_text(
        " ", strip=True
    ):
        raise ValueError("Primary research call changed")
    if re.search(
        r"DigiFI is (?:not|no longer) accepting proposals|applications (?:are |have )?closed",
        body,
        re.I,
    ):
        job["source_status"] = "closed"
    elif not re.search(
        r"DigiFI is (?:currently )?accepting proposals", body, re.I
    ) or not re.search(r"open to.{0,150}African scholars", body, re.I):
        raise ValueError(
            "Primary research call eligibility or availability unconfirmed"
        )
    job.update(
        url=target, source_urls=list(dict.fromkeys([target, *job["source_urls"]]))
    )
    job["listing_status"] = scholarship_state(job)
    job["can_apply"] = job["listing_status"] == "open"
    return job


def tasks(client):
    return [
        daad(client),
        university(client, "ug-research"),
        university(client, "knust-research"),
    ]


async def recheck(client, job, response):
    from bs4 import BeautifulSoup
    from catalogue import NOW, scholarship_state

    soup = BeautifulSoup(response.text, "html.parser")
    source = job["source_key"]
    if source == "scholarships-authority":
        from catalogue import parse_scholarship

        return parse_scholarship(soup, job["source_url"])
    if source != "daad-ghana":
        fresh = parse_university(soup, job["source_url"], source)
        return await confirm_primary(client, fresh) if fresh else None
    # The original programme must still exist and offer Ghana in its applicant selector.
    daad_url(job["source_url"], detail=True)
    overview = soup.select_one("#overview")
    title = soup.select_one("main h2")
    origins = soup.select('select option[value="145"]')
    if not overview or not title or not origins:
        raise ValueError(
            "Funding programme or Ghana eligibility could not be confirmed"
        )
    fresh = dict(job)
    fresh["checked_at"] = NOW().isoformat()
    fresh["listing_status"] = scholarship_state(fresh)
    fresh["can_apply"] = fresh["listing_status"] == "open"
    return fresh
