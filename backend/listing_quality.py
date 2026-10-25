"""Extract source facts conservatively; unknown values remain unknown."""

import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

SKILLS = [
    "Python",
    "JavaScript",
    "TypeScript",
    "React",
    "Next.js",
    "Django",
    "FastAPI",
    "Java",
    "C++",
    "C#",
    "SQL",
    "PostgreSQL",
    "Excel",
    "Power BI",
    "Tableau",
    "SAP",
    "Tally",
    "QuickBooks",
    "AutoCAD",
    "Revit",
    "ArcGIS",
    "GIS",
    "Word",
    "PowerPoint",
    "AWS",
    "Azure",
    "Linux",
    "Docker",
    "Kubernetes",
    "accounting",
    "auditing",
    "procurement",
    "supply chain",
    "marketing",
    "sales",
    "nursing",
    "teaching",
    "engineering",
    "customer service",
    "project management",
    "civil engineering",
    "electrical engineering",
    "mechanical engineering",
    "data analysis",
    "networking",
    "French",
    "English",
    "bachelor",
    "master",
    "diploma",
    "HND",
    "WASSCE",
    "SSSCE",
    "SHS",
    "PhD",
    "ACCA",
    "ICAG",
    "CIMA",
]


def canonical_url(url):
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            urlencode(
                [
                    (k, v)
                    for k, v in parse_qsl(parsed.query)
                    if not k.lower().startswith(("utm_", "ref", "source"))
                ]
            ),
            "",
        )
    )


def salary_facts(body, structured=None):
    if isinstance(structured, dict):
        value = structured.get("value", {})
        if isinstance(value, dict):
            low, high = value.get("minValue", value.get("value")), value.get("maxValue")
            if isinstance(low, (int, float)) or isinstance(high, (int, float)):
                return {
                    "salary_min": low,
                    "salary_max": high,
                    "salary_currency": structured.get("currency", ""),
                    "salary_period": str(value.get("unitText", "")).lower(),
                }
    # Require an explicit currency. Location alone never establishes salary currency.
    pattern = r"(?P<currency>GHS|GH₵|GH¢|USD|US\$|GBP|£|EUR|€)\s*(?P<low>\d[\d,]*(?:\.\d+)?)\s*(?:(?:-|–|—|to)\s*(?:(?:GHS|GH₵|GH¢|USD|US\$|GBP|£|EUR|€)\s*)?(?P<high>\d[\d,]*(?:\.\d+)?))?"
    match = re.search(pattern, body, re.I)
    if not match:
        return {}
    low = float(match["low"].replace(",", ""))
    high = float(match["high"].replace(",", "")) if match["high"] else None
    if low < 1 or high is not None and high < low:
        return {}
    currency = match["currency"].upper()
    currency = {"GH₵": "GHS", "GH¢": "GHS", "US$": "USD", "£": "GBP", "€": "EUR"}.get(
        currency, currency
    )
    context = body[max(0, match.start() - 20) : match.end() + 45]
    period = next(
        (
            key
            for key, pat in [
                ("month", r"per month|monthly|/\s*month|p\.?m\.?\b"),
                ("year", r"per annum|annually|annual|per year"),
                ("hour", r"per hour|hourly"),
                ("week", r"per week|weekly"),
            ]
            if re.search(pat, context, re.I)
        ),
        "",
    )
    return {
        "salary_min": low,
        "salary_max": high,
        "salary_currency": currency,
        "salary_period": period,
    }


def clean_description(value):
    """Remove image placeholders while retaining ordinary source links and facts."""
    value = re.sub(r"!\[([^\]]*)\]\(https?://[^\s)]+\)", r"\1", str(value or ""))
    value = re.sub(
        r"\[https?://[^\s\]]+\.(?:png|jpe?g|gif|webp|avif|svg)(?:\?[^\s\]]*)?\]",
        "",
        value,
        flags=re.I,
    )
    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", value).strip()


def enrich(job, body, structured_salary=None):
    job["description"] = clean_description(job.get("description", body))
    job.update(salary_facts(body, structured_salary))
    job["search_terms"] = [
        skill
        for skill in SKILLS
        if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", body, re.I)
    ]
    experience = re.search(
        r"(?:minimum(?: of)?|at least|requires?|experience(?: of|:)?|have)\s*(\d{1,2})(?:\s*[-–to]+\s*(\d{1,2}))?\s*(?:years?|yrs?)(?:.{0,35}?experience)?",
        body,
        re.I,
    )
    if not experience:
        experience = re.search(
            r"(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s*(?:years?|yrs?)[\s\w-]{0,25}\bexperience\b",
            body,
            re.I,
        )
    if experience and (
        re.search("experience", experience[0], re.I)
        or re.match(r"experience", experience[0], re.I)
    ):
        job["experience_years_min"] = int(experience[1])
        job["experience_years_max"] = int(experience[2]) if experience[2] else None
    if job.get("experience") == "unspecified":
        from catalogue import level

        evidence = re.search(
            r"(?:experience level|seniority|career level|entry.level|junior role|senior role|no experience required)[^.!?\n]{0,55}",
            body,
            re.I,
        )
        if evidence:
            job["experience"] = level(job["title"], evidence[0])
    job["source_urls"] = list(dict.fromkeys([job.get("source_url") or job["url"]]))
    return job


def identity(job):
    name = re.sub(r"\W", "", job["company"]).casefold()
    name = {"newmontghana": "newmont", "newmontminingcorporation": "newmont"}.get(
        name, name
    )
    name = {
        "marriott": "marriottinternational",
        "accramarriotthotel": "marriottinternational",
    }.get(name, name)
    place = re.sub(r"\bghana\b", "", job["location"], flags=re.I)
    return (
        name,
        re.sub(r"\W", "", job["title"]).casefold(),
        re.sub(r"\W", "", place).casefold(),
        job.get("category", "jobs"),
    )


def deduplicate(jobs):
    """Merge cross-source copies; keep distinct requisitions within one employer feed."""
    groups = {}
    for original in jobs:
        job = dict(original)
        job.pop("duplicate_of", None)
        groups.setdefault(identity(job), []).append(job)
    out = []
    for group in groups.values():
        direct = [j for j in group if j.get("description_kind") != "source_summary"]
        providers = [j.get("source_key", j.get("source")) for j in group]
        # Two direct requisitions or multiple posts on the same board are ambiguous.
        if len(direct) > 1 or len(providers) != len(set(providers)):
            urls = {}
            for j in group:
                u = canonical_url(j["url"])
                if u in urls:
                    j["duplicate_of"] = urls[u]
                else:
                    urls[u] = j["id"]
                out.append(j)
            continue
        group.sort(key=lambda j: j.get("description_kind") == "source_summary")
        primary = group[0]
        for secondary in group[1:]:
            for key in [
                "deadline",
                "salary_min",
                "salary_max",
                "salary_currency",
                "salary_period",
                "experience_years_min",
                "experience_years_max",
                "industry",
            ]:
                if primary.get(key) in [None, ""] and secondary.get(key) not in [
                    None,
                    "",
                ]:
                    primary[key] = secondary[key]
                    primary.setdefault("field_sources", {})[key] = secondary.get(
                        "source_url", secondary["url"]
                    )
            if primary.get("experience") == "unspecified" and secondary.get(
                "experience"
            ) not in [None, "unspecified"]:
                primary["experience"] = secondary["experience"]
            primary["search_terms"] = list(
                dict.fromkeys(
                    primary.get("search_terms", []) + secondary.get("search_terms", [])
                )
            )
            primary["source_urls"] = list(
                dict.fromkeys(
                    primary.get("source_urls", [primary["url"]])
                    + secondary.get("source_urls", [secondary["url"]])
                )
            )
            secondary["duplicate_of"] = primary["id"]
        out.extend(group)
    return out
