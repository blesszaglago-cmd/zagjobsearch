"""Bounded, private progress for public source checks. No response bodies or secrets."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlsplit

MAX_PENDING = 640
BOARD_PATHS = {
    "ghana-current-jobs": (
        "www.ghanacurrentjobs.com",
        r"/job-vacancy-for-[a-z0-9-]+/?",
    ),
    "jobweb-ghana": ("jobwebghana.com", r"/jobs/[a-z0-9-]+/"),
}


class SourceBudgetExceeded(TimeoutError):
    """A local collection window ended, rather than a publisher timing out."""


def board_url(source, value):
    if source not in BOARD_PATHS or not isinstance(value, str) or len(value) > 512:
        return None
    if any(ord(c) < 33 for c in value) or "\\" in value:
        return None
    try:
        url = urlsplit(value)
        host, path = BOARD_PATHS[source]
        if (
            url.scheme == "https"
            and url.hostname == host
            and url.port in (None, 443)
            and not url.username
            and not url.password
            and not url.query
            and not url.fragment
            and re.fullmatch(path, url.path)
        ):
            return value
    except ValueError:
        pass
    return None


def failure_kind(error):
    import httpx

    if isinstance(error, SourceBudgetExceeded):
        return "budget"
    if isinstance(error, httpx.HTTPStatusError):
        return f"http_{error.response.status_code}"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "connection"
    return "validation" if isinstance(error, ValueError) else "reader"


def failure_counts(results):
    return dict(Counter(failure_kind(r) for r in results if isinstance(r, Exception)))


def future_time(value, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo and parsed > now else None
    except (ValueError, TypeError, OverflowError):
        return None


def retry_after_time(value, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        if value.strip().isdigit():
            if len(value.strip()) > 12:
                return datetime.max.replace(tzinfo=timezone.utc)
            try:
                return now + timedelta(seconds=int(value.strip()))
            except OverflowError:
                return datetime.max.replace(tzinfo=timezone.utc)
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo and parsed > now:
            return parsed
    except (ValueError, TypeError, OverflowError):
        pass
    return None


class SourceProgress:
    def __init__(self, saved=None):
        saved = saved if isinstance(saved, dict) and saved.get("version") == 1 else {}
        pending = saved.get("pending", {})
        self.pending = {}
        for source in BOARD_PATHS:
            urls = pending.get(source, []) if isinstance(pending, dict) else []
            self.pending[source] = list(
                dict.fromkeys(
                    url
                    for value in (urls[:MAX_PENDING] if isinstance(urls, list) else [])
                    if (url := board_url(source, value))
                )
            )
        hosts = saved.get("hosts", {})
        self.hosts = dict(list(hosts.items())[:100]) if isinstance(hosts, dict) else {}

    def order(self, source, discovered):
        old = self.pending.get(source, [])
        fresh = sorted(
            {url for value in discovered if (url := board_url(source, value))}
            - set(old)
        )
        ordered = []
        for i in range(max(len(fresh), len(old))):
            if i < len(fresh):
                ordered.append(fresh[i])
            if i < len(old):
                ordered.append(old[i])
        return ordered[:MAX_PENDING], max(0, len(ordered) - MAX_PENDING)

    def finish(self, source, urls, outcomes):
        if len(urls) != len(outcomes):
            raise ValueError("Mismatched source progress")
        self.pending[source] = [
            url
            for url, result in zip(urls, outcomes)
            if isinstance(result, Exception)
            and failure_kind(result) not in {"http_404", "http_410"}
            and board_url(source, url)
        ][:MAX_PENDING]

    def snapshot(self, hosts):
        return {"version": 1, "pending": self.pending, "hosts": hosts}
