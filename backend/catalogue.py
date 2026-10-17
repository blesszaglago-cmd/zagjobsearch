"""Ghana-only catalogue. Public reads; bounded, database-leased source refreshes."""

import asyncio, hashlib, html, json, re, logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException, Request
from database.supabase_client import supabase

router = APIRouter()
NOW = lambda: datetime.now(timezone.utc)
REGIONS = {
    "Greater Accra": ["accra", "tema", "ashaiman", "madina", "adenta", "dodowa"],
    "Ashanti": ["kumasi", "obuasi", "ejisu", "konongo"],
    "Western": ["takoradi", "sekondi", "tarkwa", "prestea"],
    "Central": ["cape coast", "winneba", "mankessim", "kasoa"],
    "Eastern": ["koforidua", "akim", "nkawkaw", "akosombo"],
    "Volta": ["ho", "hohoe", "keta", "aflao"],
    "Northern": ["tamale", "yendi"],
    "Upper East": ["bolgatanga", "navrongo", "bawku"],
    "Upper West": ["wa", "lawra"],
    "Bono": ["sunyani", "berekum"],
    "Bono East": ["techiman", "kintampo"],
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
    "User-Agent": "ZagJobSearch/2.0 (+https://zagjobsearch.vercel.app; public vacancy checks)"
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
    for fmt in [
        "%d %B, %Y",
        "%d %B %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%b %d, %Y",
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
    d = deadline or closing(body)
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


async def scholarships(client):
    base = "https://scholarships.gov.gh"
    soup = await html_get(client, base + "/opportunities")
    links = list(
        dict.fromkeys(
            urljoin(base, a["href"])
            for a in soup.select("a[href]")
            if "/opportunities/" in a["href"]
        )
    )
    if not links or len(links) > 50:
        raise ValueError("Scholarship index needs a new adapter")

    async def one(u):
        s = await html_get(client, u)
        main = s.select_one("main") or s
        for el in main.select("script,style,nav,footer,header"):
            el.decompose()
        heading = main.find("h1")
        title = heading.get_text(" ", strip=True) if heading else ""
        article = main.select_one("#opportunity-details")
        meta = main.select_one(".opportunity-meta-grid")
        body = (
            (meta.get_text(" ", strip=True) if meta else "")
            + " "
            + (article.get_text(" ", strip=True) if article else "")
        )
        body = body.split("Before applying")[0].split("Latest notices")[0].strip()
        deadline = closing(body)
        # Government notices can contain old openings. Require a current explicit deadline.
        if (
            not deadline
            or deadline < NOW()
            or not re.search(
                r"Ghanaian|citizens of Ghana|nationals of Ghana", body, re.I
            )
        ):
            return None
        job = make_job(
            "scholarships-authority",
            u,
            title,
            "Ghana Scholarships Authority",
            "See official notice",
            body,
            u,
            deadline=deadline,
        )
        if not job:
            return None
        job.update(
            category="scholarships",
            job_type="scholarship",
            study_levels=[
                key
                for key, pat in [
                    ("undergraduate", r"undergraduate|bachelor"),
                    ("masters", r"master(?! of philosophy)"),
                    ("mphil", r"m\.?phil|master of philosophy"),
                    ("phd", r"ph\.?d|doctorate|doctoral"),
                ]
                if re.search(pat, body, re.I)
            ],
            study_destination=(
                "ghana"
                if re.search(
                    r"(?:institutions|universities|study|studies) in Ghana|local tertiary",
                    title + " " + body,
                    re.I,
                )
                else (
                    "abroad"
                    if re.search(
                        r"Saudi Arabia|Algeria|Serbia|Hungary|China|Japan|Turkey|United Kingdom|United States|Germany|France|Canada|Australia|South Korea|India|Morocco|Russia|overseas|abroad",
                        title + " " + body,
                        re.I,
                    )
                    else "unspecified"
                )
            ),
            funding=(
                "full"
                if re.search("fully funded|full scholarship", body, re.I)
                else "unspecified"
            ),
        )
        return job

    out = await asyncio.gather(*(one(u) for u in links), return_exceptions=True)
    if any(isinstance(x, Exception) for x in out):
        raise ValueError("Incomplete scholarship source check")
    return "scholarships-authority", [x for x in out if x]


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


async def collect():
    async with httpx.AsyncClient(
        timeout=12,
        follow_redirects=True,
        headers=HEADERS,
        limits=httpx.Limits(max_connections=12),
    ) as client:
        tasks = [
            *(smart(client, b) for b in SMART),
            *(greenhouse(client, b) for b in GREENHOUSE),
            scholarships(client),
            mining(client),
        ]
        names = [
            *["smart:" + b for b in SMART],
            *["greenhouse:" + b for b in GREENHOUSE],
            "scholarships-authority",
            "anglogold",
        ]
        result = await asyncio.gather(*tasks, return_exceptions=True)
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
        supabase.table("job_catalogue").upsert(records, on_conflict="id").execute()
    old = (
        supabase.table("job_catalogue")
        .select("id,source_key")
        .eq("status", "active")
        .execute()
        .data
    )
    closed = [
        r["id"] for r in old if r["source_key"] in successful and r["id"] not in ids
    ]
    if closed:
        supabase.table("job_catalogue").update({"status": "closed"}).in_(
            "id", closed
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
    cutoff = (NOW() - timedelta(hours=48)).isoformat()
    return (
        supabase.table("job_catalogue")
        .select("payload,first_seen_at,deadline")
        .eq("status", "active")
        .gte("last_checked_at", cutoff)
        .order("last_checked_at", desc=True)
        .limit(1000)
        .execute()
        .data
    )


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
    jobs = []
    seen = set()
    for row in rows:
        j = row["payload"]
        j["first_seen_at"] = row["first_seen_at"]
        if row["deadline"] and date(row["deadline"]) < NOW():
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
        identity = re.sub(
            r"\W", "", j["company"] + " " + j["title"] + " " + j["location"]
        ).lower()
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
    if row["status"] != "active" or row["deadline"] and date(row["deadline"]) < NOW():
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
            if host == "careers.anglogoldashanti.com":
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
        except httpx.HTTPError:
            raise HTTPException(
                503,
                "The source could not confirm this opportunity. Please try again later.",
            )
    j.pop("check_url", None)
    return j
