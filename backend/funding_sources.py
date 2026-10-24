"""Reviewed Ghana-eligible calls, refreshed against the original providers.

Opportunities for Youth supplies discovery leads, not permission to import an
unfiltered worldwide feed. Each adapter requires current provider evidence of
eligibility and extracts the application deadline, rather than a programme year,
admission deadline or recommendation deadline. Unknown providers need review.
"""

import re
from datetime import timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from academic_sources import academic_date, make_academic
from ghana_sources import page

OFY = "https://opportunitiesforyouth.org"
CALLS = {
    "lincoln-global-leaders": {
        "provider": "University of Lincoln",
        "url": "https://www.lincoln.ac.uk/studywithus/scholarshipsandbursaries/thelincolngloballeadersscholarship/",
        "title": "Global Leaders Scholarship",
        "kind": "scholarship",
        "levels": ["undergraduate", "masters"],
        "funding": "partial",
        "location": "Lincoln, United Kingdom",
        "zone": "Europe/London",
        "evidence": [
            r"available to international students",
            r"50% of tuition fees",
            r"undergraduate or postgraduate taught programme",
            r"must already have an offer",
        ],
        "eligibility": "International applicants, including Ghanaians, need an offer for an eligible undergraduate or taught postgraduate course and the required grades. Competitive award; 50% of tuition for one year, rather than living costs or a full degree.",
        "lead": OFY
        + "/2026/10/23/university-of-lincoln-global-leaders-scholarship-2027-2028-50-tuition-fee-scholarship-for-international-students-in-the-uk/",
    },
    "harvard-loeb": {
        "provider": "Harvard Graduate School of Design",
        "url": "https://loebfellowship.gsd.harvard.edu/apply-nominate/",
        "title": "Loeb Fellowship",
        "kind": "fellowship",
        "levels": [],
        "location": "Cambridge, Massachusetts, United States",
        "zone": "America/New_York",
        "evidence": [
            r"international candidates are encouraged to apply",
            r"minimum of 8 years",
            r"Applications for the .*?Fellowship year are now open",
        ],
        "eligibility": "International practitioners, including Ghanaians, with at least eight years of relevant experience improving the built or natural environment. This is a mid-career fellowship, not a degree or student scholarship. Selected international fellows must meet visa requirements.",
        "lead": OFY
        + "/2026/10/02/harvard-loeb-fellowship-2027-28-fully-detailed-guide-to-eligibility-application-process-deadline-and-what-applicants-need-to-know/",
    },
    "bodleian-visiting": {
        "provider": "University of Oxford, Bodleian Libraries",
        "url": "https://www.bodleian.ox.ac.uk/csb/fellowships/bodleian-visiting-fellowships",
        "title": "Bodleian Visiting Fellowships in Special Collections",
        "kind": "fellowship",
        "levels": ["postdoc"],
        "location": "Oxford, United Kingdom",
        "zone": "Europe/London",
        "evidence": [
            r"Applications are open for Visiting Fellowships",
            r"Applications are welcome from both academically affiliated and independent scholars",
            r"Sub-Saharan Africa",
            r"up to £2,200 per month",
        ],
        "eligibility": "Researchers outside Oxford need a project using the Bodleian special collections. Postdoctoral scholars can apply; doctoral applicants must meet the thesis-submission rules. The African Studies fellowship accepts scholars affiliated with universities in Sub-Saharan Africa, including Ghana. Named awards have additional conditions.",
        "lead": OFY
        + "/2026/10/22/bodleian-visiting-fellowships-2027-2028-at-the-university-of-oxford-funding-of-up-to-2200-per-month-for-international-researchers/",
    },
    "columbia-italian-academy": {
        "provider": "Columbia University, Italian Academy",
        "url": "https://italianacademy.columbia.edu/content/fellowship-program",
        "title": "Italian Academy Research Fellowship Programme",
        "kind": "fellowship",
        "levels": ["postdoc"],
        "location": "New York, United States",
        "zone": "America/New_York",
        "evidence": [
            r"Candidates of any nationality are invited to apply",
            r"copy of the PhD degree",
            r"Fellows receive a full-time salary",
        ],
        "eligibility": "Applicants of any nationality, including Ghanaians, must have a PhD and a suitable research proposal. Postdoctoral, mid-career and senior researchers can apply. Former Academy fellows and Columbia professors are excluded. The provider offers a salary and health benefits; residence in New York is required.",
        "lead": OFY
        + "/2026/10/23/columbia-university-italian-academy-fellowship-program-2027-2028-fully-funded-research-fellowship-in-the-united-states/",
    },
    "unesco-research-continuity": {
        "provider": "UNESCO",
        "url": "https://www.unesco.org/en/articles/call-applications-science-crisis-response-and-solutions-research-continuity-grants-africa",
        "title": "SCRS Research Continuity Grants for Africa",
        "kind": "research-grant",
        "levels": [],
        "location": "Recognized universities and research institutes in Africa",
        "destination": "unspecified",
        "zone": "Europe/Paris",
        "evidence": [
            r"Applications are now open for the SCRS Research Continuity Grants",
            r"African nationals based at a recognized university",
            r"Applications are welcome from all African countries",
            r"interrupted by an armed conflict or natural or biological hazard",
        ],
        "eligibility": "African nationals at recognized African research institutions, including those in Ghana, need at least a master's-level research qualification and evidence of crisis-interrupted natural-science research. Institutional support and a six-month work plan are required. Up to US$2,000 supports eligible research costs, not personal salary or relocation.",
        "lead": OFY
        + "/2026/10/21/unesco-science-for-crisis-response-and-solutions-research-continuity-grants-for-africa-2026-apply-for-up-to-us2000-in-research-funding/",
    },
    "ucl-hp-ai-education": {
        "provider": "UCL Institute of Education",
        "url": "https://www.ucl.ac.uk/ioe/hp-ucl-ioe-fellowship-ai-education",
        "title": "HP-UCL IOE Fellowship: AI in Education Leadership Training",
        "kind": "training",
        "levels": [],
        "location": "Online and a residential week in London, United Kingdom",
        "zone": "Europe/London",
        "funding": "partial",
        "evidence": [
            r"Geographies: Europe, Asia and Africa",
            r"senior education policymakers",
            r"Application deadline:",
            r"excluding airfares and visas",
        ],
        "eligibility": "Senior education policymakers and organizational leaders in the eligible geographies, including Africa. Ghana-based applicants must meet the leadership and participation requirements. Programme costs are covered, but travel, visas and some meals remain the participant's responsibility. This is professional training, not a master's or PhD award.",
        "lead": OFY
        + "/2026/10/20/hp-ucl-ioe-fellowship-in-ai-in-education-2027-programme-details-application-requirements-and-deadline/",
    },
    "lse-demography-funding": {
        "provider": "London School of Economics",
        "url": "https://www.lse.ac.uk/study-at-lse/graduate/mphilphd-demography-social-formal",
        "title": "MPhil/PhD Demography: research studentship consideration",
        "kind": "scholarship",
        "levels": ["mphil", "phd"],
        "location": "London, United Kingdom",
        "zone": "Europe/London",
        "evidence": [
            r"Overseas full-time.*?Open",
            r"scholarships to help both home and overseas students",
            r"Deadline for the LSE PhD Studentships and ESRC funding",
        ],
        "eligibility": "Ghanaian applicants can apply through the overseas research-student route, subject to academic and English-language requirements. A complete MPhil/PhD application must meet the funding deadline. Studentship selection is competitive and funding is not guaranteed. Specific ESRC conditions can differ from the LSE studentship conditions.",
    },
}
SOURCE_NAMES = list(CALLS)
SOURCE_INFO = {
    key: (
        spec["provider"],
        spec["url"],
        "Official funding provider",
        "Reviewed Ghana-eligible call. Its original provider page is rechecked automatically; funding and qualification conditions apply.",
    )
    for key, spec in CALLS.items()
}
CHECK_HOSTS = {urlparse(spec["url"]).hostname for spec in CALLS.values()}
DATE = r"(?:\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{1,2},?\s+\d{4})"


def clean_body(soup):
    # Some provider pages put their content outside the first, empty <main>.
    for tag in soup.select("script,style,nav,footer,header"):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def deadline_text(key, body):
    if key == "columbia-italian-academy":
        heading = re.search(
            r"DEADLINE:\s*(?:[A-Za-z]+,\s*)?(" + DATE + r")", body, re.I
        )
        precise = re.search(
            r"The application deadline is\s*(?:[A-Za-z]+,\s*)?("
            + DATE
            + r")\s*\(\s*(\d{1,2}:[0-5]\d\s*[ap]m),?\s*New York time\s*\)",
            body,
            re.I,
        )
        if precise:
            if heading and academic_date(heading[1]) != academic_date(precise[1]):
                raise ValueError("Provider application deadlines conflict")
            return [f"{precise[1]} {precise[2]} New York time"]
        return [heading[1]] if heading else []
    if key == "lincoln-global-leaders":
        return re.findall(
            r"For a programme of study commencing in [A-Za-z]+ \d{4}:\s*(?:[A-Za-z]+\s+)?("
            + DATE
            + r")",
            body,
            re.I,
        )
    patterns = {
        "harvard-loeb": r"Loeb Fellowship,\s*due\s+("
        + DATE
        + r"\s+at\s+\d{1,2}:\d{2}\s*[AP]M\s+ET)",
        "bodleian-visiting": r"The deadline is\s+("
        + DATE
        + r",\s*\d{1,2}(?::\d{2})?\s*[ap]m\s*\(GMT\))",
        "unesco-research-continuity": r"Application deadline:\s*("
        + DATE
        + r",\s*\d{1,2}:\d{2}\s+Paris time)",
        "ucl-hp-ai-education": r"Application deadline:\s*(" + DATE + r")",
        "lse-demography-funding": r"Deadline for the LSE PhD Studentships and ESRC funding:\s*("
        + DATE
        + r")",
    }
    match = re.search(patterns[key], body, re.I)
    return [match[1]] if match else []


def parse_call(soup, key):
    from catalogue import NOW, scholarship_state

    spec = CALLS[key]
    body = clean_body(soup)
    body = re.sub(r",(?=\d{4}\b)", ", ", body)
    closed = key != "lincoln-global-leaders" and bool(
        re.search(
            r"applications (?:are (?:now )?|have )(?:closed|no longer being accepted)",
            body,
            re.I,
        )
    )
    open_signals = {
        r"Applications for the .*?Fellowship year are now open",
        r"Applications are open for Visiting Fellowships",
        r"Applications are now open for the SCRS Research Continuity Grants",
    }
    if not all(
        re.search(p, body, re.I) or closed and p in open_signals
        for p in spec["evidence"]
    ):
        raise ValueError("Funding eligibility or current call format changed")
    if re.search(
        r"\b(?:Ghana|Ghanaian applicants).{0,30}(?:not eligible|ineligible|excluded)|not (?:open|available) to international",
        body,
        re.I,
    ):
        raise ValueError("Ghana eligibility is contradicted by the provider")
    raw_dates = deadline_text(key, body)
    deadlines = []
    for raw in raw_dates:
        normalized = re.sub(
            r"(?<![\d:])\b(\d{1,2})([ap]m)\b", r"\1:00\2", raw, flags=re.I
        )
        parsed = academic_date(normalized.replace("Paris time", ""))
        if not parsed:
            raise ValueError("Provider application deadline could not be parsed")
        # Interpret provider-local clocks, including daylight-saving transitions.
        has_time = bool(re.search(r"\d:\d|\d\s*[ap]m", raw, re.I))
        if has_time and not re.search(r"\b(?:GMT|CET|UTC)\b", raw, re.I):
            parsed = parsed.replace(tzinfo=ZoneInfo(spec["zone"])).astimezone(
                timezone.utc
            )
        deadlines.append((parsed, raw))
    if not deadlines and not closed:
        raise ValueError("Provider application window unconfirmed")
    future = [pair for pair in deadlines if pair[0] >= NOW()]
    deadline, raw = (
        min(future)
        if future
        else (
            max(deadlines)
            if deadlines
            else (None, "Applications closed on provider page")
        )
    )
    note = f"Provider application deadline: {raw}."
    if not re.search(r"\d:\d|\d\s*[ap]m", raw, re.I):
        note += " The provider states a closing date without an exact time."
    summary = (
        f"{spec['title']} at {spec['provider']}.\n{spec['eligibility']}\n"
        "Read the provider's complete call for award terms, required documents and submission instructions."
    )
    if spec.get("lead"):
        summary += "\nDiscovered through Opportunities for Youth; the original provider controls current eligibility and deadlines."
    job = make_academic(
        key,
        spec["url"],
        spec["title"],
        summary,
        deadline=deadline,
        kind=spec["kind"],
        levels=spec["levels"],
        destination=spec.get("destination", "abroad"),
        study_location=spec["location"],
        eligibility=spec["eligibility"],
        deadline_note=note,
        source_info=SOURCE_INFO,
    )
    job["funding"] = spec.get("funding", "unspecified")
    if spec.get("lead"):
        job["source_urls"].append(spec["lead"])
    # An explicit current closure overrides even a future date. The Lincoln page
    # also describes an older, closed intake; that is not the next open round.
    if closed:
        job["source_status"] = "closed"
    job["listing_status"] = scholarship_state(job)
    job["can_apply"] = job["listing_status"] == "open"
    return job


async def collect(client, key):
    return key, [parse_call(await page(client, CALLS[key]["url"]), key)]


def tasks(client):
    return [collect(client, key) for key in SOURCE_NAMES]


def recheck(job, response):
    key = job["source_key"]
    if (
        key not in CALLS
        or job["check_url"] != CALLS[key]["url"]
        or str(response.url).split("#")[0] != CALLS[key]["url"]
    ):
        raise ValueError("Funding provider URL changed")
    from bs4 import BeautifulSoup

    return parse_call(BeautifulSoup(response.text, "html.parser"), key)
