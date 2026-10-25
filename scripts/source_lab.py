"""Offline public-HTML parser comparisons and candidate AutoScraper rules.

Run in the separate requirements-source-lab environment. This tool never fetches
URLs, runs browsers or code from a page, or publishes records to the catalogue.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

MAX_BYTES = 4 * 1024 * 1024
PROFILES = {
    "ghana-current-jobs": {
        "title": "h3.special:not(.cat)",
        "body": ".content.text-justify",
        "summary": ".summary .row",
    },
    "jobweb-ghana": {
        "title": "h1.title",
        "body": ".section.single .section_content > font",
        "posted": ".section_header .date strong",
    },
}


def read_html(path):
    with Path(path).open("rb") as stream:
        content = stream.read(MAX_BYTES + 1)
    if not content or len(content) > MAX_BYTES:
        raise ValueError("HTML must be nonempty and at most 4 MiB")
    return content.decode("utf-8", errors="replace")


def compare(html, profile):
    from bs4 import BeautifulSoup
    from parsel import Selector as ParselSelector
    from scrapling.parser import Selector as ScraplingSelector

    if profile not in PROFILES or not html or len(html.encode()) > MAX_BYTES:
        raise ValueError("Invalid comparison input")
    soup = BeautifulSoup(html, "html.parser")
    parsel = ParselSelector(text=html, type="html")
    scrapling = ScraplingSelector(content=html, adaptive=False, huge_tree=False)

    def texts(fragments):
        return [
            BeautifulSoup(fragment, "html.parser").get_text(" ", strip=True)
            for fragment in fragments
        ]

    fields = {}
    for name, selector in PROFILES[profile].items():
        fields[name] = {
            "beautifulsoup": texts(str(node) for node in soup.select(selector)),
            "parsel": texts(parsel.css(selector).getall()),
            "scrapling": texts(scrapling.css(selector).getall()),
        }
    return {
        "version": 1,
        "profile": profile,
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
        "agreement": all(
            values["beautifulsoup"] == values["parsel"] == values["scrapling"]
            for values in fields.values()
        ),
        "required_selectors_found": all(
            all(value.strip() for value in values["beautifulsoup"])
            and bool(values["beautifulsoup"])
            for values in fields.values()
        ),
        "fields": fields,
        "publishable": False,
    }


def learn(html, examples):
    from autoscraper import AutoScraper

    if (
        not html
        or len(html.encode()) > MAX_BYTES
        or not isinstance(examples, list)
        or not 1 <= len(examples) <= 20
        or any(
            not isinstance(x, str) or not x.strip() or len(x) > 2000 for x in examples
        )
    ):
        raise ValueError("Provide 1 to 20 literal example strings")

    class CompatibleAutoScraper(AutoScraper):
        @staticmethod
        def _get_valid_attrs(item):
            # AutoScraper 1.1.14 uses empty strings for absent attributes.
            # Modern BeautifulSoup distinguishes absence from an empty attribute.
            return {
                key: value if key in item.attrs else False
                for key, value in AutoScraper._get_valid_attrs(item).items()
            }

    scraper = CompatibleAutoScraper()
    scraper.build(html=html, wanted_list=examples)
    return {
        "version": 1,
        "sha256": hashlib.sha256(html.encode()).hexdigest(),
        "rules": scraper.stack_list,
        "matches": scraper.get_result_similar(html=html, contain_sibling_leaves=True),
        "publishable": False,
    }


def write_report(path, report):
    content = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    if len(content) > MAX_BYTES:
        raise ValueError("Report exceeds 4 MiB")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["compare", "learn"])
    parser.add_argument("--html", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--profile", choices=list(PROFILES))
    parser.add_argument("--example", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        html = read_html(args.html)
        report = (
            compare(html, args.profile)
            if args.mode == "compare"
            else learn(html, args.example)
        )
        write_report(args.output, report)
    except (ValueError, OSError, ImportError):
        print(
            "Source lab could not process the input. Check the local HTML, profile, isolated dependencies and unused output path.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
