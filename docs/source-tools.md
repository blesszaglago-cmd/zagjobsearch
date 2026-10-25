# Source reliability and offline extraction tools

The production catalogue remains a bounded Python worker on the existing free
infrastructure. Its import rules still require evidence for Ghana eligibility,
application windows and source identity. No scraper can establish those facts
merely by finding text on a page.

## Production changes

- Ghana Current Jobs and Jobweb Ghana save unfinished public detail checks in
  `catalogue_refresh.source_progress`. New discoveries and unfinished checks are
  interleaved. Each board has a 640-URL limit; overflow is reported rather than
  presented as complete coverage.
- Only approved HTTPS board detail paths enter these queues. No query strings,
  credentials, arbitrary destinations, response bodies or applicant records are
  stored. The JSON object has a database limit of 1 MiB. Public catalogue reads
  and source status responses do not select the private queue.
- A completed refresh saves the queue and future publisher retry times. A whole
  worker interruption retains the last saved state, rather than an exact
  checkpoint of every in-flight request. Existing refresh leases prevent overlap.
- HTTP 429 pauses further queued requests for that host for at least 15 minutes
  and honors longer `Retry-After` values. HTTP 503 with a future `Retry-After`
  also pauses the host. Integer seconds and HTTP dates are accepted. Concurrent
  responses cannot shorten an existing longer pause. Already in-flight requests
  may complete. Redirect, DNS, TLS, per-host concurrency and body limits remain.
- Failed checks retain safe counts for budget exhaustion, timeout, connection,
  validation, reader errors and HTTP status. Raw exception messages, bodies and
  URLs are excluded from public diagnostics. The Sources page explains these
  categories without presenting a partial reader as complete.
- A confirmed detail-page 404 or 410 closes only the matching source record.
  An incomplete discovery window or timeout does not close absent records.
  Existing 48-hour freshness rules and deadline filters continue to apply.
- Jobweb feed-only rows must pass a detail check before publication. Exact
  canonical-URL duplicates retain all database IDs and mark secondary records,
  preventing a missing-ID failure during refresh upserts. Distinct employer
  requisitions still remain separate.

Deploy the additive `source_progress_queue` migration before the new backend.
It adds a private column to the existing RLS-protected table and does not grant
browser roles access. Rollback of the application does not require dropping the
column or losing queued work.

## Isolated source lab

`scripts/source_lab.py` compares saved public HTML using BeautifulSoup, Scrapling
and Parsel, the selector engine used by Scrapy. AutoScraper can learn candidate
extraction rules from literal examples. This is a developer tool, not an
automatic route for publishing new sources.

```bash
python -m venv .source-lab-venv
.source-lab-venv/bin/python -m pip install -r scripts/requirements-source-lab.txt
.source-lab-venv/bin/python -m pip check
.source-lab-venv/bin/python scripts/source_lab.py compare \
  --html local-source-evidence/detail.html --profile jobweb-ghana \
  --output local-source-evidence/comparison.json
.source-lab-venv/bin/python scripts/source_lab.py learn \
  --html local-source-evidence/list.html --example 'Field Officer' \
  --output local-source-evidence/candidate-rules.json
```

Use only public source HTML and unused output filenames. HTML and reports are
bounded to 4 MiB. Reports use private file permissions and exclusive creation.
The lab makes no HTTP requests, opens no browser, invokes no model and writes no
database records. Scrapling adaptive persistence and huge-tree mode are disabled.
Selector output is normalized through BeautifulSoup; this compares extraction
results, not end-to-end speed. Agreement on empty fields fails the required-field
check, and every report explicitly remains `publishable: false`.

AutoScraper 1.1.14 encodes absent HTML attributes as empty strings. The local
compatibility subclass preserves absence as `False` for modern BeautifulSoup.
Sibling-leaf matching is enabled for candidate discovery. Tests prove repeated
role headings can be found while an unrelated advert is excluded. These candidate
rules still require developer review and representative source fixtures.

The full Scrapy dependency stack was evaluated separately. Its selected Twisted
release reported six vulnerabilities during the 25 October 2026 audit, so it is
not included in the committed lab lock or production. Parsel provides the needed
selector comparison without that network/server stack. The revised locked lab
dependencies passed the dependency audit. This does not certify all possible
future versions or every code path.

Do not install the lab requirements into the backend environment. CI runs the
lab tests in their own job and audits its complete pinned dependency set. The
production backend dependency files do not add these frameworks.

## Other reviewed repositories

| Repository | Decision |
| --- | --- |
| Scrapy | Use its resumable-work pattern in the existing bounded worker and Parsel in the offline lab. A full reactor-based worker is deferred. |
| Scrapling | Parser-only comparison in the offline lab. No stealth or browser bypass. |
| AutoScraper | Offline candidate rules for reviewed source onboarding. No automatic publication. |
| Crawlee | Alternative if a future reviewed source needs a separate JavaScript worker; no second worker stack added now. |
| Firecrawl | No key or hosted service configured. Full self-hosting adds infrastructure beyond this site's current free setup. |
| Browser Use | No autonomous browser agent in production; unnecessary dependency conflicts and telemetry for this task. |
| ScrapeGraphAI | No model execution, generated code execution or telemetry in the live importer. |

Before replacing any production parser, compare at least 30 saved representative
detail pages from the two pilot boards and review discrepancies manually. The
current change preserves the existing production parsers. Fresh local collection
of that 30-page sample could not complete: direct connections failed and an
ordinary Ghana Current Jobs request returned 403. These are test-environment
observations, not evidence that every production source is down. No access
restriction was bypassed and no production parser replacement is claimed.
