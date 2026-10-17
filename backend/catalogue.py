"""Ghana-only catalogue. Public reads; bounded, database-leased source refreshes."""

import asyncio, hashlib, html, json, re, logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Request
from database.supabase_client import supabase
import ghana_sources

router = APIRouter()
NOW = lambda: datetime.now(timezone.utc)
REGIONS = {
    "Greater Accra": ["accra", "tema", "ashaiman", "madina", "adenta", "dodowa", "haatso", "achimota", "spintex", "tesano", "legon", "awketeyman", "akweteyman", "dzorwulu", "dansoman", "tantra hills", "kisseman"],
    "Ashanti": ["kumasi", "obuasi", "ejisu", "konongo"],
    "Western": ["takoradi", "sekondi", "tarkwa", "prestea"],
    "Central": ["cape coast", "winneba", "mankessim", "kasoa"],
    "Eastern": ["koforidua", "akim", "nkawkaw", "akosombo"],
    "Volta": ["ho", "hohoe", "keta", "aflao"],
    "Northern": ["tamale", "yendi"],
    "Upper East": ["bolgatanga", "navrongo", "bawku"],
    "Upper West": ["wa", "lawra"],
    "Bono": ["sunyani", "berekum"],
    "Bono East": ["techiman", "kintampo", "atebubu"],
    "Ahafo": ["goaso", "kenyasi"],
    "Western North": ["sefwi", "bibiani"],
    "Oti": ["dambai", "nkwanta"],
    "North East": ["nalerigu", "walewale"],
    "Savannah": ["damongo", "bole"],
}
# Fixed public employer boards, never user-provided URLs.
SMART = [
    "AmaliTech",
    "WACSI",
    "Sumundi",
    "DevelopersInVogue",
    "JobsForHumanity",
    "Deloitte6",
    "SNV",
    "SGS",
    "AccorHotel",
    "BoschGroup",
    "StandardBankGroup",
    "AECOM2",
    "MastercardFoundation",
    "Sanlam",
    "Sandvik",
]
GREENHOUSE = {
    "jumia": "Jumia",
    "scangroup": "Scangroup / Ogilvy",
    "wavemm1": "Wave",
    "flyzipline": "Zipline",
}
HEADERS = {
    "User-Agent": "jobs.ac.ghana/2.0 (+https://zagjobsearch.vercel.app; public vacancy checks)"
}


def text(value):
    return BeautifulSoup(html.unescape(str(value or "")), "html.parser").get_text(
        " ", strip=True
    )


def date(value):
    if not value:
        return None
    value = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", str(value), flags=re.I).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        result = parsedate_to_datetime(value)
        return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    for fmt in [
        "%d %B, %Y",
        "%d %B %Y",
        "%B %d, %Y",
        "%B %d %Y",
        "%d %b %Y",
        "%b %d, %Y",
        "%d %b-%Y",
        "%a %b %d %H:%M:%S UTC %Y",
    ]:
        try:
            result = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return (
                result if "%H" in fmt else result.replace(hour=23, minute=59, second=59)
            )
        except ValueError:
            pass
    return None


def closing(body):
    # Only dates following an explicit deadline label; never guess from programme years.
    found = re.findall(
        r"(?:application deadline|closing date|deadline|applications? close[sd]?)\s*[:\-]?\s*((?:\d{1,2}(?:st|nd|rd|th)?\s+[A-Za-z]+,?\s+\d{4})|(?:[A-Za-z]+\s+\d{1,2},\s+\d{4})|(?:\d{4}-\d{2}-\d{2}))",
        body,
        re.I,
    )
    parsed = [d for x in found if (d := date(x))]
    return min(parsed) if parsed else None


def classify(title, employment=""):
    t = title.lower()
    e = employment.lower()
    for key, pattern in [
        ("internship", r"\bintern(?:ship)?\b"),
        ("apprenticeship", r"apprentice"),
        ("graduate", r"graduate (?:programme|program|trainee)|national service"),
    ]:
        if re.search(pattern, t):
            return key
    if re.search(r"part[ -]?time", e + " " + t):
        return "part-time"
    if re.search(r"contract|fixed[ -]term|consultan|freelance|temporary", e + " " + t):
        return "contract"
    if "permanent" in e:
        return "permanent"
    if re.search(r"full[ -]?time", e + " " + t):
        return "full-time"
    return "unspecified"


def level(title, provided=""):
    t = (title + " " + provided).lower()
    for key, pattern in [
        ("no-experience", r"no experience"),
        ("senior", r"\bsenior\b|\bsnr\b|\bprincipal\b|\blead\b"),
        ("management", r"\bmanager\b|\bdirector\b|\bhead\b|\bchief\b"),
        ("junior", r"\bjunior\b|entry[ -]level"),
        ("mid", r"mid[ -]level|intermediate"),
    ]:
        if re.search(pattern, t):
            return key
    return "unspecified"


def regions_for(location):
    t = location.lower()
    return [
        r
        for r, cities in REGIONS.items()
        if re.search(
            r"\b"
            + re.escape(r.lower())
            + (r"(?! north)" if r == "Western" else r"(?! east)" if r == "Bono" else "")
            + r"\b",
            t,
        )
        or any(re.search(r"\b" + re.escape(c) + r"\b", t) for c in cities)
    ]


def make_job(
    source,
    key,
    title,
    company,
    location,
    body,
    url,
    posted=None,
    deadline=None,
    employment="",
    remote=False,
    experience="",
    industry="",
    check_url=None,
):
    d = date(deadline) or closing(body)
    p = date(posted)
    if d and d < NOW():
        return None
    if re.search(
        r"(?:this (?:job|position|vacancy) (?:is|has been) (?:closed|filled)|no longer accepting applications|applications (?:are|have) closed)",
        body,
        re.I,
    ):
        return None
    # An active feed is evidence of publication, not evidence that old recruitment is current.
    if not d and p and p < NOW() - timedelta(days=60):
        return None
    if not title or len(body) < 80 or not url.startswith("https://"):
        return None
    if any(
        re.search(r"\b" + str(y) + r"[/–-]" + str(y + 1)[-2:] + r"\b", title)
        for y in range(2019, NOW().year - 1)
    ):
        return None
    kind = classify(title, employment)
    return {
        "id": hashlib.sha256((source + ":" + str(key)).encode()).hexdigest()[:32],
        "source_key": source,
        "title": text(title),
        "company": text(company),
        "location": location,
        "regions": regions_for(location),
        "description": text(body)[:24000],
        "url": url,
        "source_url": url,
        "source": company,
        "created": p.isoformat() if p else None,
        "date_kind": "published" if p else "not_provided",
        "deadline": d.isoformat() if d else None,
        "job_type": kind,
        "employment_label": employment,
        "experience": level(title, experience),
        "industry": industry,
        "remote": remote,
        "category": (
            "remote"
            if remote
            else (
                "early"
                if kind in ["internship", "graduate", "apprenticeship"]
                else "jobs"
            )
        ),
        "checked_at": NOW().isoformat(),
        "check_url": check_url,
        "verification": "Listed on source at last check",
    }


async def json_get(client, url):
    r = await client.get(url)
    r.raise_for_status()
    return r.json()


async def smart(client, board):
    source = "smart:" + board
    data = await json_get(
        client,
        f"https://api.smartrecruiters.com/v1/companies/{board}/postings?limit=100&country=gh",
    )
    rows = data.get("content")
    if not isinstance(rows, list) or "totalFound" not in data:
        raise ValueError("Employer feed format changed")
    if data.get("totalFound", 0) > 100:
        raise ValueError(
            "Source requires pagination; withheld to avoid incomplete closure checks"
        )

    async def one(j):
        loc = j.get("location", {})
        if loc.get("country", "").lower() != "gh":
            return None
        if date(j.get("releasedDate")) and date(j["releasedDate"]) < NOW() - timedelta(
            days=60
        ):
            return None
        u = f'https://api.smartrecruiters.com/v1/companies/{board}/postings/{j["id"]}'
        d = await json_get(client, u)
        body = "\n\n".join(
            text(v.get("text")) for v in d.get("jobAd", {}).get("sections", {}).values()
        )
        city = ", ".join(filter(None, [loc.get("city"), loc.get("region"), "Ghana"]))
        return make_job(
            source,
            j["id"],
            j["name"],
            d.get("company", {}).get("name") or board,
            city,
            body,
            d.get("applyUrl") or f'https://jobs.smartrecruiters.com/{board}/{j["id"]}',
            j.get("releasedDate"),
            employment=d.get("typeOfEmployment", {}).get("label", ""),
            remote=loc.get("remote", False),
            experience=d.get("experienceLevel", {}).get("label", ""),
            industry=d.get("industry", {}).get("label", ""),
            check_url=u,
        )

    result = await asyncio.gather(*(one(j) for j in rows), return_exceptions=True)
    if any(isinstance(j, Exception) for j in result):
        raise ValueError("Incomplete employer check")
    return source, [j for j in result if j]


async def greenhouse(client, board):
    source = "greenhouse:" + board
    d = await json_get(
        client, f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    )
    jobs = []
    if not isinstance(d.get("jobs"), list):
        raise ValueError("Employer feed format changed")
    for j in d.get("jobs", []):
        loc = j.get("location", {}).get("name", "")
        if not re.search(r"\bGhana\b", loc, re.I):
            continue
        body = text(j.get("content"))
        remote = bool(
            re.search(r"\bremote\b", loc, re.I)
            or board == "wavemm1"
            and re.search(
                r"work remotely|remote position|remote role|remote-first", body, re.I
            )
        )
        # Updated timestamp is explicitly labelled as source updated, never as date posted.
        job = make_job(
            source,
            j["id"],
            j["title"],
            GREENHOUSE[board],
            loc,
            body,
            j["absolute_url"],
            j.get("updated_at"),
            employment=" ".join(
                str(m.get("value") or "")
                for m in (j.get("metadata") or [])
                if re.search("employment|contract", m.get("name", ""), re.I)
            ),
            remote=remote,
            check_url=f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{j["id"]}',
        )
        if job:
            job["date_kind"] = "source_updated"
            jobs.append(job)
    return source, jobs


async def html_get(client, url):
    # Only allowlisted URLs are passed by source adapters.
    r = await client.get(url)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def scholarship_deadline(meta, body):
    explicit = date(meta.get("deadline"))
    if explicit:
        return explicit
    body = re.sub(r"(\d)\s*(?:st|nd|rd|th)\b", r"\1", body, flags=re.I)
    body = re.sub(r"\s+,", ",", body)
    token = r"(?:\d{1,2}\s+[A-Za-z]+,?\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})"
    contexts = re.findall(
        r"(?:deadline|closing date|not later than|no later than|on or before|latest by|application before).{0,180}",
        body,
        re.I,
    )
    # Explicit opening-to-closing window in the local tertiary notice.
    contexts += re.findall(r"opening date.{0,160}?\bto\b(.{0,80})", body, re.I)
    dates = [
        parsed
        for context in contexts
        for value in re.findall(token, context)
        if (parsed := date(value))
    ]
    return min(dates) if dates else None


def scholarship_state(job):
    deadline = date(job.get("deadline"))
    if (
        job.get("source_status", "").lower() == "closed"
        or deadline
        and deadline < NOW()
    ):
        return "closed"
    return "open" if deadline else "unconfirmed"


def parse_scholarship(soup, url):
    main = soup.select_one("main") or soup
    title_node = main.find("h1")
    article = main.select_one(".opportunity-article-body")
    if not title_node or not article:
        raise ValueError("Scholarship detail format changed")
    title = title_node.get_text(" ", strip=True)
    body = article.get_text(" ", strip=True)
    meta = {}
    for card in main.select(".opportunity-meta-card"):
        label, value = card.find("span"), card.find("strong")
        if label and value:
            meta[label.get_text(" ", strip=True).lower()] = value.get_text(
                " ", strip=True
            )
    deadline = scholarship_deadline(meta, body)
    published = date(meta.get("published"))
    combined = title + " " + body
    local = bool(
        re.search(
            r"local tertiary|local scholarship|institutions in Ghana|universities in Ghana|Ghanaian universities|tenable in Ghana|Fanaka|PWASI",
            combined,
            re.I,
        )
    )
    abroad = bool(
        re.search(
            r"Saudi Arabia|Algeria|Serbia|Hungary|China|Chinese|Japan|Turkey|United Kingdom|London|Geneva|United States|Germany|France|Canada|Australia|Australian|Spain|Spanish|South Korea|India|Morocco|Russia|Mauritius|Thai|overseas|abroad",
            combined,
            re.I,
        )
    )
    # Prefer the award's stated level, excluding sentences about prior qualifications.
    parts = [p.get_text(" ", strip=True) for p in article.select("p,li,h2,h3,h4,td")]
    offered = (
        title
        + " "
        + " ".join(
            p
            for p in parts
            if not re.search(
                r"must (?:have|hold|possess)|hold at least|should (?:have|hold)|minimum admission|Bachelor or a Master degree",
                p,
                re.I,
            )
        )
    )
    levels = [
        key
        for key, pattern in [
            ("undergraduate", r"undergraduate|bachelor.{0,20}program"),
            ("masters", r"master(?! of philosophy)"),
            ("mphil", r"m\.?phil|master of philosophy"),
            ("phd", r"ph\.?d|doctorate|doctoral"),
        ]
        if re.search(pattern, offered, re.I)
    ]
    job = {
        "id": hashlib.sha256(("scholarships-authority:" + url).encode()).hexdigest()[
            :32
        ],
        "source_key": "scholarships-authority",
        "title": title,
        "company": "Ghana Scholarships Authority (Scholsec)",
        "source": "Ghana Scholarships Authority",
        "location": (
            "Study in Ghana"
            if local
            else "Study abroad" if abroad else "See official notice"
        ),
        "regions": [],
        "description": body[:24000],
        "url": url,
        "source_url": url,
        "created": published.isoformat() if published else None,
        "date_kind": "published" if published else "not_provided",
        "deadline": deadline.isoformat() if deadline else None,
        "source_status": meta.get("status", ""),
        "job_type": "scholarship",
        "experience": "unspecified",
        "industry": "",
        "remote": False,
        "category": "scholarships",
        "checked_at": NOW().isoformat(),
        "check_url": None,
        "study_levels": levels,
        "study_destination": (
            "ghana" if local else "abroad" if abroad else "unspecified"
        ),
        "funding": (
            "full"
            if re.search(r"fully funded|full scholarship", body, re.I)
            else (
                "partial"
                if re.search(r"partial scholarship|partially funded", body, re.I)
                else "unspecified"
            )
        ),
        "eligibility_note": (
            "Ghanaian applicants mentioned in the notice"
            if re.search(r"Ghanaian|citizens of Ghana|nationals of Ghana", body, re.I)
            else "Check the notice for nationality and admission requirements"
        ),
        "verification": "Official Scholsec notice checked",
    }
    job["listing_status"] = scholarship_state(job)
    job["can_apply"] = job["listing_status"] == "open"
    return job


async def scholarships(client):
    base = "https://scholarships.gov.gh"
    pending = [base + "/opportunities"]
    visited, links = set(), set()
    expected = None
    while pending:
        page = pending.pop(0)
        if page in visited:
            continue
        if len(visited) >= 50:
            raise ValueError(
                "Scholarship pagination limit reached; incomplete refresh withheld"
            )
        visited.add(page)
        soup = await html_get(client, page)
        if expected is None:
            match = re.search(
                r"(\d+)\s+Total notices", soup.get_text(" ", strip=True), re.I
            )
            expected = int(match[1]) if match else None
        for anchor in soup.select("a[href]"):
            url = urljoin(base, anchor["href"])
            parsed = urlparse(url)
            if parsed.hostname != "scholarships.gov.gh":
                continue
            if parsed.path.startswith("/opportunities/"):
                links.add(url.split("?")[0].split("#")[0])
            elif (
                parsed.path == "/opportunities"
                and re.fullmatch(r"page=\d+", parsed.query)
                and url not in visited
            ):
                pending.append(url)
    if not links or expected is not None and len(links) != expected:
        raise ValueError("Scholarship index is incomplete")

    async def one(url):
        return parse_scholarship(await html_get(client, url), url)

    results = await asyncio.gather(
        *(one(url) for url in sorted(links)), return_exceptions=True
    )
    if any(isinstance(result, Exception) for result in results):
        raise ValueError("Incomplete scholarship source check")
    return "scholarships-authority", results


async def mining(client):
    base = "https://careers.anglogoldashanti.com"
    s = await html_get(client, base + "/go/Ghana-%28en_GB%29/9006201/")
    links = list(
        dict.fromkeys(
            urljoin(base, a["href"])
            for a in s.select("a[href]")
            if a["href"].startswith("/job/")
        )
    )
    if not links or len(links) > 50:
        raise ValueError("Employer index needs a new adapter")

    async def one(u):
        page = await html_get(client, u)
        for script in page.select('script[type="application/ld+json"]'):
            try:
                d = json.loads(script.string or script.get_text())
            except ValueError:
                continue
            if d.get("@type") != "JobPosting":
                continue
            locations = d.get("jobLocation", [])
            locations = locations if isinstance(locations, list) else [locations]
            addresses = [loc.get("address", {}) for loc in locations]
            ghana = [
                a
                for a in addresses
                if str(a.get("addressCountry", "")).lower() in ["gh", "ghana"]
            ]
            if not ghana:
                return None
            loc = (
                ", ".join(
                    dict.fromkeys(
                        str(
                            a.get("addressLocality")
                            or a.get("addressRegion")
                            or "Ghana"
                        )
                        for a in ghana
                    )
                )
                + ", Ghana"
            )
            return make_job(
                "anglogold",
                u,
                d.get("title"),
                "AngloGold Ashanti",
                loc,
                text(d.get("description")),
                u,
                d.get("datePosted"),
                date(d.get("validThrough")),
                str(d.get("employmentType", "")),
                check_url=u,
            )
        title = page.select_one("[itemprop=title]")
        loc = page.select_one(".jobGeoLocation")
        body = page.select_one(".jobdescription")
        posted = page.select_one("[itemprop=datePosted]")
        expiry = page.select_one("[itemprop=validThrough]")
        if not all([title, loc, body]) or not re.search(
            r"\bGH\b|\bGhana\b", loc.get_text(), re.I
        ):
            return None
        if not regions_for(loc.get_text()):
            return None
        return make_job(
            "anglogold",
            u,
            title.get_text(" ", strip=True),
            "AngloGold Ashanti",
            loc.get_text(" ", strip=True),
            body.get_text(" ", strip=True),
            u,
            posted.get("content") if posted else None,
            date(expiry.get("content")) if expiry else None,
            check_url=u,
        )

    out = await asyncio.gather(*(one(u) for u in links), return_exceptions=True)
    if any(isinstance(x, Exception) for x in out):
        raise ValueError("Incomplete employer source check")
    return "anglogold", [x for x in out if x]


class PublicSourceClient:
    """Bound concurrency per host as well as across the complete source refresh."""

    def __init__(self, client):
        self.client = client
        self.slots = asyncio.Semaphore(12)
        self.hosts = {}

    async def get(self, url, **kwargs):
        host = urlparse(url).hostname
        limit = self.hosts.setdefault(host, asyncio.Semaphore(3))
        async with limit, self.slots:
            return await self.client.get(url, **kwargs)


async def collect():
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=True,
        headers=HEADERS,
        limits=httpx.Limits(max_connections=12),
    ) as http_client:
        client = PublicSourceClient(http_client)
        tasks = [
            *(smart(client, b) for b in SMART),
            *(greenhouse(client, b) for b in GREENHOUSE),
            scholarships(client),
            mining(client),
            *ghana_sources.tasks(client),
        ]
        names = [
            *["smart:" + b for b in SMART],
            *["greenhouse:" + b for b in GREENHOUSE],
            "scholarships-authority",
            "anglogold",
            *ghana_sources.SOURCE_NAMES,
        ]
        result = await asyncio.gather(*(asyncio.wait_for(task, 130) for task in tasks), return_exceptions=True)
        for name, outcome in zip(names, result):
            if isinstance(outcome, Exception):
                logging.warning(
                    "Catalogue source unavailable: %s (%s)",
                    name,
                    type(outcome).__name__,
                )
        return [
            (names[i], None if isinstance(r, Exception) else r[1])
            for i, r in enumerate(result)
        ]


def catalogue_rows(columns, fresh=False):
    """PostgREST caps a response at 1,000 rows; explicitly page larger catalogues."""
    result, offset = [], 0
    while True:
        query = supabase.table("job_catalogue").select(columns).eq("status", "active")
        if fresh:
            query = query.gte("last_checked_at", (NOW() - timedelta(hours=48)).isoformat())
        rows = query.order("id").range(offset, offset + 499).execute().data
        result.extend(rows)
        if len(rows) < 500:
            return result
        offset += 500


async def refresh():
    # Atomic database lease prevents overlapping invocations and public refresh abuse.
    claimed = supabase.rpc("claim_catalogue_refresh").execute().data
    if not claimed:
        return {"refreshed": False, "reason": "Not due"}
    checked = NOW().isoformat()
    results = await collect()
    summary = []
    records = []
    successful = set()
    ids = set()
    for source, jobs in results:
        if jobs is None:
            summary.append({"source": source, "state": "unavailable", "accepted": 0})
            continue
        successful.add(source)
        for job in jobs:
            ids.add(job["id"])
            records.append(
                {
                    "id": job["id"],
                    "source_key": source,
                    "payload": job,
                    "status": "active",
                    "last_checked_at": checked,
                    "deadline": job.get("deadline"),
                }
            )
        summary.append({"source": source, "state": "ok", "accepted": len(jobs)})
    if records:
        for offset in range(0, len(records), 200):
            supabase.table("job_catalogue").upsert(records[offset:offset + 200], on_conflict="id").execute()
    old = catalogue_rows("id,source_key")
    closed = [
        r["id"] for r in old
        if r["source_key"] in successful - ghana_sources.WINDOWED_SOURCES and r["id"] not in ids
    ]
    for offset in range(0, len(closed), 200):
        supabase.table("job_catalogue").update({"status": "closed"}).in_(
            "id", closed[offset:offset + 200]
        ).execute()
    supabase.table("catalogue_refresh").update(
        {"completed_at": NOW().isoformat(), "summary": summary}
    ).eq("id", 1).execute()
    return {"refreshed": True, "sources": summary}


@router.get("/catalogue/refresh")
async def refresh_route():
    try:
        return await refresh()
    except Exception:
        raise HTTPException(
            503,
            "The catalogue refresh could not finish. Existing recently checked listings remain available.",
        )


def active_rows():
    return catalogue_rows("payload,first_seen_at,deadline", fresh=True)


def job_identity(job):
    company = re.sub(r"\W", "", job["company"]).lower()
    title = re.sub(r"\W", "", job["title"]).lower()
    location = re.sub(r"\bghana\b", "", job["location"], flags=re.I)
    return company, title, re.sub(r"\W", "", location).lower()


@router.get("/catalogue/sources")
def catalogue_sources():
    rows = supabase.table("catalogue_refresh").select("completed_at,summary").eq("id", 1).execute().data
    state = rows[0] if rows else {}
    health = {x["source"]: x for x in state.get("summary", [])}
    registry = dict(ghana_sources.SOURCE_INFO)
    for board in SMART:
        registry["smart:" + board] = (board.replace("Deloitte6", "Deloitte").replace("AccorHotel", "Accor").replace("AECOM2", "AECOM").replace("StandardBankGroup", "Standard Bank").replace("MastercardFoundation", "Mastercard Foundation"), f"https://careers.smartrecruiters.com/{board}", "Direct employer", "Public employer board. Only explicit Ghana locations qualify.")
    for board, name in GREENHOUSE.items():
        registry["greenhouse:" + board] = (name, f"https://job-boards.greenhouse.io/{board}", "Direct employer", "Public employer board. Remote roles must explicitly accept applicants in Ghana.")
    registry["anglogold"] = ("AngloGold Ashanti", "https://careers.anglogoldashanti.com/", "Direct employer", "Public employer board, checked for Ghana location and closing dates.")
    registry["scholarships-authority"] = ("Ghana Scholarships Authority", "https://scholarships.gov.gh/opportunities", "Scholarships", "Official notices. Open, unconfirmed and archived notices have separate views.")
    checked = date(state.get("completed_at"))
    current = bool(checked and checked >= NOW() - timedelta(hours=48))
    imported = []
    for key, (name, url, kind, note) in registry.items():
        status = health.get(key, {})
        imported.append({"key": key, "name": name, "url": url, "kind": kind, "note": note, "state": status.get("state", "not_checked") if current else "awaiting_refresh", "accepted": status.get("accepted", 0) if current else 0})
    external = [{"name": name, "url": url, "kind": kind, "note": note} for name, url, kind, note in ghana_sources.EXTERNAL_SOURCES]
    return {"updated_at": state.get("completed_at"), "imported": imported, "external": external}


@router.get("/catalogue")
def search_catalogue(request: Request):
    p = request.query_params
    category = p.get("category", "jobs")
    q = p.get("q", "").strip().lower()[:200]
    if category not in ["jobs", "early", "remote", "scholarships"]:
        raise HTTPException(400, "Choose a listing category.")
    try:
        page = max(1, min(50, int(p.get("page", "1"))))
    except ValueError:
        page = 1
    rows = active_rows()
    # When a board repeats an employer's posting, show the employer record first.
    rows.sort(key=lambda row: row["payload"].get("description_kind") == "source_summary")
    jobs = []
    seen = set()
    for row in rows:
        j = row["payload"]
        j["first_seen_at"] = row["first_seen_at"]
        if category == "scholarships":
            j["listing_status"] = scholarship_state(j)
            j["can_apply"] = j["listing_status"] == "open"
            availability = p.get("availability", "open")
            if availability not in ["all", "open", "unconfirmed", "closed"]:
                raise HTTPException(400, "Choose a scholarship status.")
            if availability != "all" and j["listing_status"] != availability:
                continue
        elif row["deadline"] and date(row["deadline"]) < NOW():
            continue
        if j.get("category") != category:
            continue
        if any(
            word
            not in (j["title"] + " " + j["company"] + " " + j["description"]).lower()
            for word in q.split()
        ):
            continue
        if p.get("region") and p["region"] not in j.get("regions", []):
            continue
        if p.get("town") and p["town"].lower() not in j.get("location", "").lower():
            continue
        if (
            p.get("job_type")
            and p["job_type"] != "all"
            and p["job_type"] != j.get("job_type")
        ):
            continue
        if p.get("experience") and p["experience"] != j.get("experience"):
            continue
        if p.get("study_level") and p["study_level"] not in j.get("study_levels", []):
            continue
        if p.get("destination") and p["destination"] != j.get("study_destination"):
            continue
        if p.get("funding") and p["funding"] != j.get("funding"):
            continue
        if (
            p.get("industry")
            and p["industry"].lower()
            not in (
                j.get("industry", "") + " " + j["title"] + " " + j["description"]
            ).lower()
        ):
            continue
        identity = (
            j["id"]
            if category == "scholarships"
            else job_identity(j)
        )
        if identity in seen:
            continue
        seen.add(identity)
        j.pop("check_url", None)
        jobs.append(j)
    jobs.sort(
        key=lambda j: j.get("created") or j.get("first_seen_at", ""), reverse=True
    )
    state = (
        supabase.table("catalogue_refresh")
        .select("completed_at,summary")
        .eq("id", 1)
        .execute()
        .data
    )
    return {
        "jobs": jobs[(page - 1) * 20 : page * 20],
        "total": len(jobs),
        "page": page,
        "has_more": page * 20 < len(jobs),
        "updated_at": state[0].get("completed_at") if state else None,
        "source_status": state[0].get("summary", []) if state else [],
        "errors": [],
    }


@router.get("/catalogue/{job_id}")
async def catalogue_details(job_id: str):
    if not re.fullmatch("[a-f0-9]{32}", job_id):
        raise HTTPException(404, "This listing is no longer in the Ghana catalogue.")
    rows = (
        supabase.table("job_catalogue")
        .select("*")
        .eq("id", job_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(404, "Opportunity not found.")
    row = rows[0]
    j = row["payload"]
    j["first_seen_at"] = row["first_seen_at"]
    is_scholarship = j.get("category") == "scholarships"
    if is_scholarship:
        j["listing_status"] = scholarship_state(j)
        j["can_apply"] = j["listing_status"] == "open"
    if (
        row["status"] != "active"
        or not is_scholarship
        and row["deadline"]
        and date(row["deadline"]) < NOW()
    ):
        raise HTTPException(
            410,
            "Applications for this opportunity have closed. Your saved application history is unchanged.",
        )
    if date(row["last_checked_at"]) < NOW() - timedelta(hours=48):
        raise HTTPException(
            503, "This opportunity needs a fresh source check before it can be shown."
        )
    # Recheck the allowlisted source endpoint on detail views, never arbitrary stored links.
    check = j.get("check_url")
    host = urlparse(check or "").hostname
    if check and host in [
        "api.smartrecruiters.com",
        "boards-api.greenhouse.io",
        "careers.anglogoldashanti.com",
        "www.ghanacurrentjobs.com",
        "hiregh.com",
        "www.glmis.gov.gh",
        "jobs.newmont.com",
        "telecel.zohorecruit.com",
    ]:
        try:
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=True, headers=HEADERS
            ) as client:
                r = await client.get(check)
            if r.status_code in [404, 410]:
                supabase.table("job_catalogue").update({"status": "closed"}).eq(
                    "id", job_id
                ).execute()
                raise HTTPException(410, "The source removed this opportunity.")
            if r.status_code != 200:
                raise HTTPException(
                    503,
                    "The source could not confirm this opportunity. Please try again later.",
                )
            if host in ["careers.anglogoldashanti.com", "www.ghanacurrentjobs.com", "hiregh.com", "www.glmis.gov.gh"]:
                body = text(r.text)
                soup = BeautifulSoup(r.text, "html.parser")
                expiry = soup.select_one("[itemprop=validThrough]")
                closed = bool(
                    re.search(
                        r"this (?:job|position|vacancy) (?:is|has been) (?:closed|filled)|no longer accepting applications|job you are trying to apply for has been filled",
                        body,
                        re.I,
                    )
                )
                expiry_date = date(expiry.get("content")) if expiry else closing(body)
                if closed or expiry_date and expiry_date < NOW():
                    supabase.table("job_catalogue").update({"status": "closed"}).eq(
                        "id", job_id
                    ).execute()
                    raise HTTPException(410, "The source closed this opportunity.")
                if host in ["www.ghanacurrentjobs.com", "www.glmis.gov.gh"]:
                    parser = ghana_sources.parse_current_jobs if host == "www.ghanacurrentjobs.com" else ghana_sources.parse_glmis
                    fresh = parser(soup, check)
                    if not fresh:
                        raise HTTPException(503, "The original posting needs a fresh eligibility check. Please try another current opportunity.")
                    j.update({k: v for k, v in fresh.items() if k not in ["id", "first_seen_at"]})
            if host == "jobs.newmont.com":
                fresh = ghana_sources.parse_newmont(BeautifulSoup(r.text, "html.parser"), check)
                if not fresh:
                    supabase.table("job_catalogue").update({"status": "closed"}).eq("id", job_id).execute()
                    raise HTTPException(410, "The employer no longer lists this Ghana opportunity as open.")
            if host == "telecel.zohorecruit.com":
                rows = ghana_sources.telecel_rows(BeautifulSoup(r.text, "html.parser"))
                fresh = next((ghana_sources.parse_telecel(row) for row in rows if str(row.get("id")) == j.get("employer_job_id")), None)
                if not fresh:
                    supabase.table("job_catalogue").update({"status": "closed"}).eq("id", job_id).execute()
                    raise HTTPException(410, "The employer no longer lists this Ghana opportunity as open.")
        except httpx.HTTPError:
            raise HTTPException(
                503,
                "The source could not confirm this opportunity. Please try again later.",
            )
        except (ValueError, KeyError, TypeError):
            raise HTTPException(503, "The source format changed and this posting could not be confirmed.")
    j.pop("check_url", None)
    return j
