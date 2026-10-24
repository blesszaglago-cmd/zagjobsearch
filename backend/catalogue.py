"""Ghana-only catalogue. Public reads; bounded, database-leased source refreshes."""

import asyncio, hashlib, html, json, re, logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Header, Depends
from database.supabase_client import supabase
import ghana_sources
import employer_sources
import academic_sources
import jobweb_source
import funding_sources
import early_career_sources
import marriott_source
from listing_quality import enrich, deduplicate, identity
from public_http import PublicSourceClient, source_client, source_url

router = APIRouter()
NOW = lambda: datetime.now(timezone.utc)
REGIONS = {
    "Greater Accra": [
        "accra",
        "tema",
        "ashaiman",
        "madina",
        "adenta",
        "dodowa",
        "haatso",
        "achimota",
        "spintex",
        "tesano",
        "legon",
        "awketeyman",
        "akweteyman",
        "dzorwulu",
        "dansoman",
        "tantra hills",
        "kisseman",
    ],
    "Ashanti": ["kumasi", "obuasi", "ejisu", "konongo"],
    "Western": ["takoradi", "sekondi", "tarkwa", "prestea"],
    "Central": ["cape coast", "winneba", "mankessim", "kasoa"],
    "Eastern": ["koforidua", "akim", "nkawkaw", "akosombo"],
    "Volta": ["ho", "hohoe", "keta", "aflao"],
    "Northern": ["tamale", "yendi"],
    "Upper East": ["bolgatanga", "navrongo", "bawku"],
    "Upper West": ["wa", "lawra", "tumu", "jirapa"],
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
    "alxafrica": "ALX Africa",
    "wikimedia": "Wikimedia Foundation",
    "canonical": "Canonical",
    "givedirectly": "GiveDirectly",
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
    if re.match(r"^graduate\b", t):
        return "graduate"
    for key, pattern in [
        ("internship", r"\bintern(?:ship)?\b"),
        ("apprenticeship", r"apprentice"),
        (
            "graduate",
            r"graduate (?:programme|program|(?:management )?trainee)|national service",
        ),
    ]:
        if re.search(pattern, t + " " + e):
            return key
    if re.search(r"part[ -]?time", e + " " + t):
        return "part-time"
    if re.search(
        r"\bcontract\b|fixed[ -]term|\bftc\b|consultan|freelance|temporary", e + " " + t
    ):
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
        ("senior", r"\bsenior\b|\bsnr\b|\bsr\b|\bprincipal\b|\blead\b"),
        ("management", r"\bmanager\b|\bdirector\b|\bhead\b|\bchief\b"),
        ("junior", r"\bjunior\b|\bjnr\b|entry[ -]level"),
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
    active_confirmed=False,
    structured_salary=None,
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
    if not active_confirmed and not d and p and p < NOW() - timedelta(days=60):
        return None
    if not title or len(body) < 80 or not url.startswith("https://"):
        return None
    if any(
        re.search(r"\b" + str(y) + r"[/–-]" + str(y + 1)[-2:] + r"\b", title)
        for y in range(2019, NOW().year - 1)
    ):
        return None
    kind = classify(title, employment)
    return enrich(
        {
            "id": hashlib.sha256((source + ":" + str(key)).encode()).hexdigest()[:32],
            "source_key": source,
            "title": text(title),
            "company": text(company),
            "location": location,
            "regions": regions_for(location),
            "description": BeautifulSoup(
                html.unescape(str(body)), "html.parser"
            ).get_text("\n", strip=True)[:24000],
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
        },
        title + " \n" + body,
        structured_salary,
    )


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
            active_confirmed=True,
        )

    result = await asyncio.gather(*(one(j) for j in rows), return_exceptions=True)
    if any(isinstance(j, Exception) for j in result):
        raise ValueError("Incomplete employer check")
    return source, [j for j in result if j]


def greenhouse_eligibility(board, location, body, title):
    """Require a Ghana work location or a reviewed employer's hiring statement."""
    if re.search(r"\bGhana\b", location, re.I):
        return "Ghana work location stated by the employer"
    if board == "canonical" and re.search(r"Home based - Worldwide", location, re.I):
        # Some worldwide-tagged cards still name an exclusive regional role.
        if re.search(
            r"\b(?:Americas|APAC|USA|United States|Canada|London|Taiwan|Singapore)\b|\bUS[- ]only\b",
            title,
            re.I,
        ):
            return None
        restrictions = re.findall(
            r"(?:Location\s*:|(?:candidates|applicants) must be based in)(.{0,240})",
            body,
            re.I,
        )
        if any(
            re.search(
                r"\b(?:Americas|APAC|United States|USA|Canada|Europe only|UK only)\b",
                part,
                re.I,
            )
            and not re.search(
                r"Africa|all regions|worldwide|global|every (?:region|time zone)|all time zones",
                part,
                re.I,
            )
            for part in restrictions
        ):
            return None
        return "The employer advertises this home-based role worldwide. Role-specific experience, travel and working-hour requirements apply."
    if location.strip().casefold() != "remote":
        return None
    if re.search(
        r"Location:\s*Remote\s*\(US\)|(?:candidates|applicants) must (?:be based|reside) in (?:the )?(?:US|USA|United States|UK|Canada)\b",
        body,
        re.I,
    ):
        return None
    pattern = {
        "wikimedia": r"Countries:\s*([^.;]{0,900})",
        "givedirectly": r"prioritizing hiring in the countries below.{0,240}?:\s*([^.;]{0,900})",
    }.get(board)
    match = re.search(pattern, body, re.I) if pattern else None
    if match and re.search(r"\bGhana\b", match[1], re.I):
        return "Ghana appears in this role's stated hiring-country list. Local work authorization and the role's other conditions apply."
    return None


def parse_greenhouse(j, board):
    if not isinstance(j, dict):
        raise ValueError("Employer vacancy identity changed")
    loc = j.get("location", {}).get("name", "")
    body = text(j.get("content"))
    eligibility = greenhouse_eligibility(board, loc, body, j.get("title", ""))
    if not eligibility:
        return None
    if not isinstance(j.get("id"), int):
        raise ValueError("Employer vacancy identity changed")
    target = j.get("absolute_url", "")
    parsed = urlparse(target)
    if board in {"canonical", "wikimedia", "givedirectly"} and (
        parsed.scheme != "https"
        or parsed.hostname != "job-boards.greenhouse.io"
        or parsed.port not in (None, 443)
        or parsed.path != f'/{board}/jobs/{j["id"]}'
        or parsed.query
        or parsed.username
    ):
        raise ValueError("Employer application URL changed")
    remote = bool(
        re.search(r"\bremote\b|Home based - Worldwide", loc, re.I)
        or board == "wavemm1"
        and re.search(
            r"work remotely|remote position|remote role|remote-first", body, re.I
        )
    )
    job = make_job(
        "greenhouse:" + board,
        j["id"],
        j["title"],
        GREENHOUSE[board],
        (
            loc
            if re.search(r"\bGhana\b", loc, re.I)
            else "Remote from Ghana (" + loc + ")"
        ),
        body,
        target,
        j.get("updated_at"),
        employment=" ".join(
            str(m.get("value") or "")
            for m in (j.get("metadata") or [])
            if re.search("employment|contract", m.get("name", ""), re.I)
        ),
        remote=remote,
        check_url=f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{j["id"]}',
        active_confirmed=True,
    )
    if job:
        job["date_kind"] = "source_updated"
        job["eligibility_note"] = eligibility
        job["source_location_label"] = loc
        if board in {"wikimedia", "givedirectly"}:
            # Their standard pay examples apply to the US, UK or Kenya. Do not
            # display those figures as the salary offered to a Ghana applicant.
            for key in ["salary_min", "salary_max", "salary_currency", "salary_period"]:
                job[key] = None
    return job


async def greenhouse(client, board):
    d = await json_get(
        client, f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
    )
    if not isinstance(d.get("jobs"), list):
        raise ValueError("Employer feed format changed")
    return "greenhouse:" + board, [
        job for row in d["jobs"] if (job := parse_greenhouse(row, board))
    ]


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
    return (
        "open"
        if deadline or job.get("application_window") == "rolling"
        else "unconfirmed"
    )


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
        "check_url": url,
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


def source_failure(error):
    """Retain an actionable category, never provider bodies or exception text."""
    if isinstance(error, httpx.HTTPStatusError):
        return {"kind": "http", "status": error.response.status_code}
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return {"kind": "timeout"}
    if isinstance(error, httpx.TransportError):
        return {"kind": "connection"}
    if isinstance(error, ValueError):
        return {"kind": "validation"}
    return {"kind": "reader"}


class CollectedSources(list):
    def __init__(self, rows=(), *, failures=None):
        super().__init__(rows)
        self.failures = failures or {}


async def collect(archive_page=9, tracked=None):
    async with source_client(HEADERS) as http_client:
        client = PublicSourceClient(http_client)
        tasks = [
            *(smart(client, b) for b in SMART),
            *(greenhouse(client, b) for b in GREENHOUSE),
            scholarships(client),
            mining(client),
            *ghana_sources.tasks(client, archive_page),
            *employer_sources.tasks(client),
            *academic_sources.tasks(client),
            *funding_sources.tasks(client),
            *early_career_sources.tasks(client),
            marriott_source.collect(client),
            jobweb_source.collect(client),
        ]
        names = [
            *["smart:" + b for b in SMART],
            *["greenhouse:" + b for b in GREENHOUSE],
            "scholarships-authority",
            "anglogold",
            *ghana_sources.SOURCE_NAMES,
            *employer_sources.SOURCE_NAMES,
            *academic_sources.SOURCE_NAMES,
            *funding_sources.SOURCE_NAMES,
            *early_career_sources.SOURCE_NAMES,
            *marriott_source.SOURCE_NAMES,
            *jobweb_source.SOURCE_NAMES,
        ]
        result = await asyncio.gather(
            *(asyncio.wait_for(task, 130) for task in tasks), return_exceptions=True
        )
        for name, outcome in zip(names, result):
            if isinstance(outcome, Exception):
                logging.warning(
                    "Catalogue source unavailable: %s (%s)",
                    name,
                    type(outcome).__name__,
                )
        collected = CollectedSources(
            [
                (names[i], None if isinstance(r, Exception) else r[1])
                for i, r in enumerate(result)
            ],
            failures={
                names[i]: source_failure(r)
                for i, r in enumerate(result)
                if isinstance(r, Exception)
            },
        )
        if tracked:
            present = {j["id"] for _, jobs in collected for j in (jobs or [])}
            try:
                extra = await asyncio.wait_for(
                    ghana_sources.recheck_tracked(client, tracked, present), 25
                )
                for name, jobs in collected:
                    if jobs is not None:
                        jobs.extend(j for j in extra if j["source_key"] == name)
            except (TimeoutError, httpx.HTTPError):
                logging.warning("Tracked vacancy recheck deferred")
        return collected


def catalogue_rows(columns, fresh=False):
    """PostgREST caps a response at 1,000 rows; explicitly page larger catalogues."""
    result, offset = [], 0
    while True:
        query = supabase.table("job_catalogue").select(columns).eq("status", "active")
        if fresh:
            query = query.gte(
                "last_checked_at", (NOW() - timedelta(hours=48)).isoformat()
            )
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
    try:
        state = refresh_state()
        archive_page = int(state.get("archive_page") or 9)
        tracked = catalogue_rows("payload")
        results = await collect(archive_page, tracked)
    except Exception:
        supabase.table("catalogue_refresh").update(
            {
                "next_refresh_at": (NOW() + timedelta(minutes=30)).isoformat(),
                "last_error": "Catalogue collection failed; automatic retry is due in 30 minutes",
            }
        ).eq("id", 1).execute()
        raise
    summary = []
    records = []
    successful = set()
    ids = set()
    for source, jobs in results:
        if jobs is None:
            summary.append(
                {
                    "source": source,
                    "state": "unavailable",
                    "accepted": 0,
                    "failure": getattr(results, "failures", {}).get(source),
                }
            )
            continue
        failed_checks = getattr(jobs, "failed_checks", 0)
        if not failed_checks:
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
        summary.append(
            {
                "source": source,
                "state": "partial" if failed_checks else "ok",
                "accepted": len(jobs),
                "failed_checks": failed_checks,
            }
        )
    if records:
        merged = {j["id"]: j for j in deduplicate([r["payload"] for r in records])}
        for record in records:
            record["payload"] = merged[record["id"]]
            record["deadline"] = record["payload"].get("deadline")
        for offset in range(0, len(records), 200):
            supabase.table("job_catalogue").upsert(
                records[offset : offset + 200], on_conflict="id"
            ).execute()
    old = catalogue_rows("id,source_key")
    closed = [
        r["id"]
        for r in old
        if r["source_key"]
        in successful
        - ghana_sources.WINDOWED_SOURCES
        - academic_sources.WINDOWED_SOURCES
        - early_career_sources.WINDOWED_SOURCES
        - {"jobweb-ghana"}
        and r["id"] not in ids
    ]
    for offset in range(0, len(closed), 200):
        supabase.table("job_catalogue").update({"status": "closed"}).in_(
            "id", closed[offset : offset + 200]
        ).execute()
    supabase.table("catalogue_refresh").update(
        {
            "completed_at": NOW().isoformat(),
            "summary": summary,
            "next_refresh_at": (
                NOW() + timedelta(hours=6)
                if all(x["state"] == "ok" for x in summary)
                else NOW() + timedelta(minutes=30)
            ).isoformat(),
            "last_error": (
                None
                if all(x["state"] == "ok" for x in summary)
                else "Some sources need another check"
            ),
            "archive_page": 9 if archive_page >= 29 else archive_page + 4,
        }
    ).eq("id", 1).execute()
    return {"refreshed": True, "sources": summary}


@router.get("/catalogue/refresh")
async def refresh_route(authorization: str = Header(default="")):
    from security import require_cron

    require_cron(authorization)
    try:
        return await refresh()
    except Exception:
        supabase.table("catalogue_refresh").update(
            {
                "next_refresh_at": (NOW() + timedelta(minutes=30)).isoformat(),
                "last_error": "Catalogue refresh failed; another attempt is due in 30 minutes",
            }
        ).eq("id", 1).execute()
        raise HTTPException(
            503,
            "The catalogue refresh could not finish. Existing recently checked listings remain available.",
        )


def active_rows():
    return catalogue_rows("payload,first_seen_at,deadline", fresh=True)


def job_identity(job):
    return identity(job)


@router.get("/catalogue/sources")
def catalogue_sources():
    rows = (
        supabase.table("catalogue_refresh")
        .select("completed_at,summary")
        .eq("id", 1)
        .execute()
        .data
    )
    state = rows[0] if rows else {}
    health = {x["source"]: x for x in state.get("summary", [])}
    registry = dict(ghana_sources.SOURCE_INFO)
    registry.update(employer_sources.SOURCE_INFO)
    registry.update(academic_sources.SOURCE_INFO)
    registry.update(funding_sources.SOURCE_INFO)
    registry.update(early_career_sources.SOURCE_INFO)
    registry.update(marriott_source.SOURCE_INFO)
    registry.update(jobweb_source.SOURCE_INFO)
    for board in SMART:
        registry["smart:" + board] = (
            board.replace("Deloitte6", "Deloitte")
            .replace("AccorHotel", "Accor")
            .replace("AECOM2", "AECOM")
            .replace("StandardBankGroup", "Standard Bank")
            .replace("MastercardFoundation", "Mastercard Foundation"),
            f"https://careers.smartrecruiters.com/{board}",
            "Direct employer",
            "Public employer board. Only explicit Ghana locations qualify.",
        )
    for board, name in GREENHOUSE.items():
        registry["greenhouse:" + board] = (
            name,
            f"https://job-boards.greenhouse.io/{board}",
            "Direct employer",
            "Public employer board. Remote roles must explicitly accept applicants in Ghana.",
        )
    registry["anglogold"] = (
        "AngloGold Ashanti",
        "https://careers.anglogoldashanti.com/",
        "Direct employer",
        "Public employer board, checked for Ghana location and closing dates.",
    )
    registry["scholarships-authority"] = (
        "Ghana Scholarships Authority",
        "https://scholarships.gov.gh/opportunities",
        "Scholarships",
        "Official notices. Open, unconfirmed and archived notices have separate views.",
    )
    checked = date(state.get("completed_at"))
    current = bool(checked and checked >= NOW() - timedelta(hours=48))
    imported = []
    for key, (name, url, kind, note) in registry.items():
        status = health.get(key, {})
        imported.append(
            {
                "key": key,
                "name": name,
                "url": url,
                "kind": kind,
                "note": note,
                "state": (
                    status.get("state", "not_checked")
                    if current
                    else "awaiting_refresh"
                ),
                "accepted": status.get("accepted", 0) if current else 0,
                "failed_checks": status.get("failed_checks", 0) if current else 0,
                "failure": status.get("failure") if current else None,
            }
        )
    external = [
        {"name": name, "url": url, "kind": kind, "note": note}
        for name, url, kind, note in ghana_sources.EXTERNAL_SOURCES
    ]
    return {
        "updated_at": state.get("completed_at"),
        "imported": imported,
        "external": external,
    }


def refresh_state():
    rows = (
        supabase.table("catalogue_refresh")
        .select("completed_at,next_refresh_at,summary,last_error,archive_page")
        .eq("id", 1)
        .execute()
        .data
    )
    return rows[0] if rows else {}


def query_catalogue(params):
    p = {str(k): str(v)[:200] for k, v in params.items()}
    if p.get("category", "jobs") not in ["jobs", "early", "remote", "scholarships"]:
        raise HTTPException(400, "Choose a listing category.")
    if p.get("availability", "open") not in ["all", "open", "unconfirmed", "closed"]:
        raise HTTPException(400, "Choose a scholarship status.")
    if p.get("salary_period", "") not in ["", "hour", "day", "week", "month", "year"]:
        raise HTTPException(400, "Choose a valid pay period.")
    try:
        p["page"] = str(max(1, min(1000000, int(p.get("page", "1")))))
        for key in ["salary_min", "salary_max"]:
            if p.get(key) and (not float(p[key]) >= 0 or float(p[key]) > 1e12):
                raise ValueError()
        if (
            p.get("salary_min")
            and p.get("salary_max")
            and float(p["salary_min"]) > float(p["salary_max"])
        ):
            raise ValueError()
    except ValueError:
        raise HTTPException(400, "Enter a valid page and salary range.")
    result = supabase.rpc("search_ghana_catalogue", {"filters": p}).execute().data
    return result


@router.get("/catalogue")
def search_catalogue(request: Request, background_tasks: BackgroundTasks = None):
    result = query_catalogue(dict(request.query_params))
    state = refresh_state()
    # The protected database schedule owns refreshes. Public reads must not wait
    # for a multi-source background task in a serverless ASGI invocation.
    return {
        **result,
        "updated_at": state.get("completed_at"),
        "source_status": state.get("summary", []),
        "errors": [],
    }


@router.get("/catalogue/coverage")
def catalogue_coverage():
    counts = {"jobs": 0, "early": 0, "remote": 0, "scholarships": 0}
    regions = {name: 0 for name in REGIONS}
    missing = {"deadline": 0, "experience": 0, "salary": 0}
    for row in active_rows():
        j = row["payload"]
        if j.get("duplicate_of"):
            continue
        if j.get("category") == "scholarships":
            if scholarship_state(j) != "open":
                continue
        elif row.get("deadline") and date(row["deadline"]) < NOW():
            continue
        counts[j["category"]] += 1
        if j.get("category") != "scholarships":
            for region in j.get("regions", []):
                if region in regions:
                    regions[region] += 1
            missing["deadline"] += not bool(j.get("deadline"))
            missing["experience"] += j.get("experience") == "unspecified"
            missing["salary"] += (
                j.get("salary_min") is None and j.get("salary_max") is None
            )
    state = refresh_state()
    checked = date(state.get("completed_at"))
    return {
        "categories": counts,
        "regions": regions,
        "missing_fields": missing,
        "updated_at": state.get("completed_at"),
        "healthy": bool(checked and checked > NOW() - timedelta(hours=48)),
        "last_error": state.get("last_error"),
        "sources_with_listings": sum(
            s.get("accepted", 0) > 0 for s in state.get("summary", [])
        ),
    }


@router.get("/catalogue/sitemap")
def sitemap_listings(offset: int = 0):
    rows = (
        supabase.table("job_catalogue")
        .select("id,payload,first_seen_at,last_checked_at,deadline")
        .eq("status", "active")
        .gte("last_checked_at", (NOW() - timedelta(hours=48)).isoformat())
        .order("id")
        .range(max(0, offset), max(0, offset) + 999)
        .execute()
        .data
    )
    jobs = []
    for row in rows:
        j = row["payload"]
        if j.get("duplicate_of"):
            continue
        if j.get("category") == "scholarships" and scholarship_state(j) != "open":
            continue
        if (
            j.get("category") != "scholarships"
            and row.get("deadline")
            and date(row["deadline"]) < NOW()
        ):
            continue
        jobs.append(
            {"id": row["id"], "updated_at": j.get("created") or row["first_seen_at"]}
        )
    return {"jobs": jobs, "has_more": len(rows) == 1000, "next_offset": offset + 1000}


async def require_apply_account(request: Request, verify: bool = False):
    # Public details stay readable. Live Apply checks require a current account,
    # including when a caller skips the frontend and contacts this API directly.
    if verify:
        from sessions import bearer, current_user

        current_user(await bearer(request), request)


@router.get("/catalogue/{job_id}", dependencies=[Depends(require_apply_account)])
async def catalogue_details(job_id: str, verify: bool = False, request: Request = None):
    if not re.fullmatch("[a-f0-9]{32}", job_id):
        raise HTTPException(404, "This listing is no longer in the Ghana catalogue.")
    if verify and request is not None:
        from security import rate_limit

        rate_limit(request, "apply-source-check", limit=30, seconds=60)
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
    j = dict(row["payload"])
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
    check_hosts = [
        "api.smartrecruiters.com",
        "boards-api.greenhouse.io",
        "careers.anglogoldashanti.com",
        "www.ghanacurrentjobs.com",
        "hiregh.com",
        "www.glmis.gov.gh",
        "jobs.newmont.com",
        "telecel.zohorecruit.com",
        "api.ashbyhq.com",
        "gh.fido.money",
        "erp.mpharma.com",
        "scholarships.gov.gh",
        "www.daad-ghana.org",
        "rid.ug.edu.gh",
        "ogr.knust.edu.gh",
        "jobwebghana.com",
        "careers.votex365.com",
        "www.ug.edu.gh",
        "nya.gov.gh",
        "careers.marriott.com",
        *funding_sources.CHECK_HOSTS,
    ]
    if verify:
        if not check or host not in check_hosts:
            raise HTTPException(
                503, "This opportunity needs an approved source check before applying."
            )
        try:
            source_url(check)
            async with source_client(HEADERS, timeout=10) as http_client:
                client = PublicSourceClient(http_client)
                r = await client.get(check)
                if j.get("source_key") == "marriott-ghana" and r.status_code == 200:
                    fresh = await marriott_source.recheck(client, j, r)
                    if fresh is None:
                        supabase.table("job_catalogue").update({"status": "closed"}).eq(
                            "id", job_id
                        ).execute()
                        raise HTTPException(
                            410,
                            "The employer no longer lists this Ghana opportunity as open.",
                        )
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
                if (
                    j.get("source_key") in funding_sources.SOURCE_NAMES
                    and r.status_code == 200
                ):
                    fresh = funding_sources.recheck(j, r)
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
                if (
                    j.get("source_key") in early_career_sources.SOURCE_NAMES
                    and r.status_code == 200
                ):
                    fresh = await early_career_sources.recheck(client, j)
                    if fresh is None:
                        supabase.table("job_catalogue").update({"status": "closed"}).eq(
                            "id", job_id
                        ).execute()
                        raise HTTPException(
                            410,
                            "The source no longer confirms a current Ghana application window for this opportunity.",
                        )
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
                if host == "boards-api.greenhouse.io" and r.status_code == 200:
                    endpoint = re.fullmatch(
                        r"/v1/boards/([a-z0-9]+)/jobs/(\d+)", urlparse(check).path
                    )
                    if (
                        not endpoint
                        or endpoint[1] not in GREENHOUSE
                        or j.get("source_key") != "greenhouse:" + endpoint[1]
                    ):
                        raise ValueError("Employer verification endpoint changed")
                    data = r.json()
                    if not isinstance(data, dict) or str(data.get("id")) != endpoint[2]:
                        raise ValueError("Employer vacancy identity changed")
                    fresh = parse_greenhouse(data, endpoint[1])
                    if fresh is None:
                        supabase.table("job_catalogue").update({"status": "closed"}).eq(
                            "id", job_id
                        ).execute()
                        raise HTTPException(
                            410,
                            "The employer no longer confirms this role as open to Ghana applicants.",
                        )
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
                if host in ["api.ashbyhq.com", "gh.fido.money", "erp.mpharma.com"]:
                    if r.status_code != 200:
                        raise HTTPException(
                            503,
                            "The employer could not confirm this opportunity. Please try again later.",
                        )
                    fresh = await employer_sources.recheck(client, j, r)
                    if fresh is None:
                        supabase.table("job_catalogue").update({"status": "closed"}).eq(
                            "id", job_id
                        ).execute()
                        raise HTTPException(
                            410,
                            "The employer no longer lists this Ghana opportunity as open.",
                        )
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
                if host in [
                    "scholarships.gov.gh",
                    "www.daad-ghana.org",
                    "rid.ug.edu.gh",
                    "ogr.knust.edu.gh",
                ]:
                    if r.status_code != 200:
                        raise HTTPException(
                            503,
                            "The academic source could not confirm this notice. Please try again later.",
                        )
                    fresh = await academic_sources.recheck(client, j, r)
                    if not fresh:
                        raise HTTPException(
                            503,
                            "Ghana eligibility for this funding call needs another check.",
                        )
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
                if host == "jobwebghana.com" and r.status_code == 200:
                    fresh = jobweb_source.parse_detail(
                        BeautifulSoup(r.text, "html.parser"), check
                    )
                    if not fresh:
                        raise HTTPException(
                            410,
                            "The board could not confirm a current Ghana application window for this vacancy.",
                        )
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
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
            if host in [
                "careers.anglogoldashanti.com",
                "www.ghanacurrentjobs.com",
                "hiregh.com",
                "www.glmis.gov.gh",
            ]:
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
                    parser = (
                        ghana_sources.parse_current_jobs
                        if host == "www.ghanacurrentjobs.com"
                        else ghana_sources.parse_glmis
                    )
                    fresh = parser(soup, check)
                    if not fresh:
                        raise HTTPException(
                            503,
                            "The original posting needs a fresh eligibility check. Please try another current opportunity.",
                        )
                    j.update(
                        {
                            k: v
                            for k, v in fresh.items()
                            if k not in ["id", "first_seen_at"]
                        }
                    )
            if host == "jobs.newmont.com":
                fresh = ghana_sources.parse_newmont(
                    BeautifulSoup(r.text, "html.parser"), check
                )
                if not fresh:
                    supabase.table("job_catalogue").update({"status": "closed"}).eq(
                        "id", job_id
                    ).execute()
                    raise HTTPException(
                        410,
                        "The employer no longer lists this Ghana opportunity as open.",
                    )
            if host == "telecel.zohorecruit.com":
                rows = ghana_sources.telecel_rows(BeautifulSoup(r.text, "html.parser"))
                fresh = next(
                    (
                        ghana_sources.parse_telecel(row)
                        for row in rows
                        if str(row.get("id")) == j.get("employer_job_id")
                    ),
                    None,
                )
                if not fresh:
                    supabase.table("job_catalogue").update({"status": "closed"}).eq(
                        "id", job_id
                    ).execute()
                    raise HTTPException(
                        410,
                        "The employer no longer lists this Ghana opportunity as open.",
                    )
        except httpx.HTTPError:
            raise HTTPException(
                503,
                "The source could not confirm this opportunity. Please try again later.",
            )
        except (ValueError, KeyError, TypeError):
            raise HTTPException(
                503,
                "The source format changed and this posting could not be confirmed.",
            )
    j.pop("check_url", None)
    return j
