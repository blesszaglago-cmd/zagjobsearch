"""Factual summaries from Jobweb Ghana's public feed and recent public pages.

Readable advert facts take precedence over contradictory template JSON-LD.
This is a bounded discovery window, never a complete vacancy inventory.
"""

import asyncio
import hashlib
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from defusedxml import ElementTree as ET

from ghana_sources import (
    factual_summary,
    ghana_location,
    on_host,
    page,
    CheckedListings,
    checked_batch,
    removed,
)

BASE = "https://jobwebghana.com"
SOURCE_NAMES = ["jobweb-ghana"]
SOURCE_INFO = {
    "jobweb-ghana": (
        "Jobweb Ghana",
        BASE + "/",
        "Job board",
        "Public RSS, recent vacancy pages and the internship index. Factual summaries use the readable advert, not conflicting template salaries or locations.",
    )
}


def vacancy_url(url):
    parsed = urlparse(urljoin(BASE, url))
    if (
        not on_host(parsed.geturl(), "jobwebghana.com")
        or not re.fullmatch(r"/jobs/[a-z0-9-]+/", parsed.path)
        or parsed.query
    ):
        raise ValueError("Job board detail URL changed")
    return parsed.geturl().split("#")[0]


def from_body(title, body, url, posted=None, employment=""):
    from catalogue import NOW, closing, date, make_job
    from datetime import timedelta

    vacancy_url(url)
    name = re.fullmatch(r"(.+?)\s+at\s+(.+)", title, re.I)
    if not name:
        return None
    # The board's card label 'Anywhere' and JSON-LD's default Accra are not work locations.
    locations = [
        p.get_text(" ", strip=True)
        for p in body.select("p,li")
        if re.match(r"^\s*(?:Work )?Location\s*:", p.get_text(" ", strip=True), re.I)
    ]
    location = next(
        (re.sub(r"^(?:Work )?Location\s*:\s*", "", p, flags=re.I) for p in locations),
        "",
    )
    if not location or len(location) > 180 or not ghana_location(location):
        return None
    text = body.get_text("\n", strip=True)
    deadline = closing(body.get_text(" ", strip=True))
    published = date(posted)
    rolling = re.search(
        r"applications (?:are |will be )?(?:accepted|reviewed|considered|received).{0,60}rolling basis|rolling basis until (?:the )?(?:position|role) is filled",
        text,
        re.I,
    )
    if not deadline and not (
        rolling and published and published >= NOW() - timedelta(days=14)
    ):
        return None
    job = make_job(
        "jobweb-ghana",
        url,
        name[1].strip(),
        name[2].strip(),
        location,
        text,
        url,
        posted=posted,
        deadline=deadline,
        employment=employment,
        check_url=url,
    )
    if job:
        if rolling and not deadline:
            job["deadline_note"] = (
                "Rolling applications; recent source advert rechecked"
            )
        return factual_summary(job, "Jobweb Ghana")
    return None


def parse_detail(soup, url):
    title = soup.select_one("h1.title")
    article = soup.select_one(".section.single .section_content > font")
    posted = soup.select_one(".section_header .date strong")
    employment = soup.select_one(".section.single .section_content .jtype")
    if not title or not article or not posted or len(article.get_text()) < 80:
        raise ValueError("Job board vacancy detail changed")
    return from_body(
        title.get_text(" ", strip=True),
        article,
        url,
        posted.get_text(" ", strip=True),
        employment.get_text(" ", strip=True) if employment else "",
    )


def feed_jobs(response):
    if (
        not on_host(str(response.url), "jobwebghana.com")
        or len(response.content) > 2_000_000
    ):
        raise ValueError("Job board feed redirected or exceeded its bound")
    root = ET.fromstring(response.content, forbid_dtd=True)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("Job board feed format changed")
    out = {}
    for row in root.findall("./channel/item"):
        url = vacancy_url(row.findtext("link", ""))
        body = BeautifulSoup(
            row.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", ""),
            "html.parser",
        )
        job = from_body(row.findtext("title", ""), body, url, row.findtext("pubDate"))
        if job:
            out[url] = job
    return out


async def collect(client, progress=None):
    from source_progress import SourceProgress, failure_counts

    progress = progress or SourceProgress()
    started = asyncio.get_running_loop().time()
    response = await client.get(BASE + "/feed/")
    response.raise_for_status()
    jobs = feed_jobs(response)
    indexes = await checked_batch(
        (
            page(client, u)
            for u in [
                BASE + "/jobs/",
                BASE + "/job-type/internship/",
                BASE + "/job-type/part-time/",
                BASE + "/job-type/temporary/",
                BASE + "/job-type/freelance/",
                *[BASE + f"/jobs/page/{n}/" for n in range(2, 13)],
            ]
        ),
        timeout=35,
    )
    links = set()
    failures, valid_indexes = 0, 0
    for index, soup in enumerate(indexes):
        if isinstance(soup, httpx.HTTPStatusError) and soup.response.status_code in (
            404,
            410,
        ):
            continue  # An optional category or page beyond the end is empty.
        if isinstance(soup, Exception):
            failures += 1
            continue
        lists = soup.select("ol.jobs")
        if not lists:
            failures += 1
            indexes[index] = ValueError("Job board index changed")
            continue
        valid_indexes += 1
        for listing in lists:
            for a in listing.select("a[href]"):
                parsed = urlparse(urljoin(BASE, a["href"]))
                if parsed.hostname == "jobwebghana.com" and re.fullmatch(
                    r"/jobs/[a-z0-9-]+/", parsed.path
                ):
                    links.add(vacancy_url(parsed.geturl()))
    if not valid_indexes or not links or len(links) > 220:
        raise ValueError("Job board discovery window changed")
    # Details establish the current application window and explicit job type.
    pending, overflow = progress.order("jobweb-ghana", links | jobs.keys())
    # A feed-only row must not publish without a successful detail check.
    jobs = {}
    details = await checked_batch(
        (page(client, u) for u in pending),
        timeout=max(1, 100 - (asyncio.get_running_loop().time() - started)),
    )
    signatures = {}
    for index, (url, soup) in enumerate(zip(pending, details)):
        if isinstance(soup, httpx.HTTPStatusError) and soup.response.status_code in (
            404,
            410,
        ):
            jobs.pop(url, None)
            continue
        if isinstance(soup, Exception):
            failures += 1
            jobs.pop(url, None)  # Never use feed-only data after a failed detail check.
            continue
        try:
            job = parse_detail(soup, url)
        except (ValueError, KeyError, TypeError):
            failures += 1
            details[index] = ValueError("Job board vacancy detail changed")
            jobs.pop(url, None)
            continue
        if job:
            body = soup.select_one(".section.single .section_content > font")
            fingerprint = hashlib.sha256(
                re.sub(r"\s+", " ", body.get_text(" ", strip=True)).encode()
            ).hexdigest()
            key = (
                job["title"].casefold(),
                job["company"].casefold(),
                job["location"].casefold(),
                fingerprint,
            )
            if key in signatures:
                primary = signatures[key]
                primary["source_urls"] = list(
                    dict.fromkeys([*primary["source_urls"], url])
                )
                jobs.pop(url, None)
                continue
            signatures[key] = job
            jobs[url] = job
        else:
            jobs.pop(url, None)
    progress.finish("jobweb-ghana", pending, details)
    diagnostics = failure_counts([x for x in [*indexes, *details] if not removed(x)])
    if overflow:
        diagnostics["queue_limit"] = overflow
    return "jobweb-ghana", CheckedListings(
        jobs.values(),
        failed_checks=failures + overflow,
        diagnostics=diagnostics,
        queued_checks=len(progress.pending["jobweb-ghana"]),
        removed_urls=[u for u, value in zip(pending, details) if removed(value)],
    )
