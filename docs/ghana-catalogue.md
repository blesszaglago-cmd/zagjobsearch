# Ghana catalogue

Search uses a persisted Ghana catalogue instead of the retired global feeds. Browsing and external applications remain public; application tracking requires an account. CV assistance is retired and `/cv` redirects to the tracker. Existing account/application records are preserved.

## Supported sources

Public SmartRecruiters boards: AmaliTech, Deloitte, SNV, SGS, Accor, Bosch, Standard Bank, AECOM, Mastercard Foundation, Sanlam, Sandvik, WACSI, Sumundi, Developers in Vogue and Jobs for Humanity. Country must explicitly be `gh`. Public Greenhouse boards: Jumia, Scangroup/Ogilvy, Wave and Zipline. Location must explicitly name Ghana. Remote requires an explicit remote designation; Africa/worldwide alone does not qualify.

AngloGold Ashanti's Ghana career pages require Ghana metadata and a recognised Ghana town/region, excluding foreign vacancies mistakenly placed on the Ghana board. Scholsec collection follows every public opportunity-index page and checks the published total against collected notice URLs. All published notices remain available, with separate Open, Deadline unconfirmed, Closed archive and All views. Open is the default. An explicit future deadline is required to show Apply; expired and unconfirmed notices provide a Read official notice link. Dates inside the notice are checked when summary metadata is missing. Study levels exclude known prior-qualification sentences; unknown details remain unspecified. Each notice retains its distinct source URL, including repeated programme names across years.

Supported sources do not mean complete national/industry coverage. Empty boards contribute zero results. Internships, graduate programmes and apprenticeships enter Early careers when eligible current postings exist. Empty tabs are never populated with invented opportunities. Jobberman is excluded: its terms require written approval for automated extraction (https://www.jobberman.com.gh/terms).

### Direct employer expansion, 22 October 2026

`backend/employer_sources.py` adds M-KOPA's published Ashby feed and Fido's official careers index. They use the existing protected refresh, per-host concurrency bounds, deduplication, source-status endpoint and external Apply flow. No paid API, credential or schema change is needed. See the [coverage plan](listing-coverage-plan.md) for the measured baseline and next source priorities.

M-KOPA eligibility checks the primary and secondary work addresses. An explicitly listed Ghana location qualifies even when another country's address is primary. Unlisted postings are excluded. Towns explicitly supplied in a role-title suffix, such as Hohoe-Dambai, can supply work locations when the feed otherwise names only Ghana; employer headquarters are never used as a substitute. Hybrid roles stay outside the fully remote category. Fixed-term `FTC` titles classify as contracts. Ashby's last-published timestamp is labelled as a source update rather than an original publication date.

Fido vacancies must appear in the current official index and name Ghana in their work locations. Each detail page must supply role text and an individual application link on Fido's own recruitment host. National-service roles enter Early careers. Unpublished dates, closing dates and salaries remain unknown.

Apply rechecks each employer's current index. A complete index confirming removal closes the record; an unavailable, malformed or redirected feed remains a failed check, not proof of closure. Fido also reloads the individual detail to obtain the current application URL. Both readers participate in automatic refreshes and source-health monitoring.

### Ghana source expansion

`backend/ghana_sources.py` adds five public readers, without paid APIs or credentials:

- Ghana Current Jobs: eight recent public index pages plus four rotating older index pages per refresh, explicit closing dates, Ghana locations, factual metadata summaries, attribution and original application instructions.
- HIREghana: two public RSS pages, original publication dates and Ghana towns. Anonymous clients remain explicitly undisclosed.
- GLMIS: eight recent public index pages, all 16 advertised region-filter pages, internship/part-time filters and detail pages. An Accra recruitment agency address does not qualify a UAE/Bulgaria or other overseas placement. Relative posting ages are checked without inventing an exact publication timestamp.
- Newmont: public search-page data followed by the matching employer JobPosting and open posting status. A hidden closed-job UI template is not treated as a real closure.
- Telecel: the published vacancies embedded in the official Zoho career page. Country, publication state, employer job ID and an explicitly open publication state are checked. Apply links lead to the individual official vacancy.

The public `/catalogue/sources` endpoint and frontend `/sources` page distinguish checked integrations from external destinations. LinkedIn, Jobberman, JobsInGhana and SokoJob are external search links until suitable permission/integrations exist. Ghanajob.com, Jobwebghana and JobHouse were not reliably accessible to the importer; no blocks are bypassed. Job Linq has no connected public vacancy feed. The Petroleum Commission link is a candidate-registration pool, not an imported vacancy feed. MTN notices found through Ghana Current Jobs are attributed to that board, not claimed as a direct MTN integration.

Collection uses at most three concurrent requests per host, twelve globally and a 130-second source limit. A failed source does not stop other sources. Recent-window readers cannot infer closure from absence; omitted records instead disappear after 48 hours without a successful check. Database reads explicitly page beyond PostgREST's response cap, and writes use batches of 200. Duplicate board records yield to direct employer records when company, role and town match; a trailing Ghana country label does not create a duplicate.

## Automation and freshness

Supabase pg_cron checks for a due refresh every 15 minutes. Successful collection is normally due after six hours, partial failures after 30 minutes. An atomic service-only 10-minute lease prevents overlapping downloads. Public refresh routes require maintenance authorisation. See `docs/operations.md`. Only fixed supported source URLs are fetched. No paid provider is added.

Explicit expiry, removal/closure at the source, or disappearance from a completely successful refresh removes a posting from search. Failed or unrecognisable feeds do not falsely close records; records without a successful check for 48 hours are hidden. Job-board records without deadlines and with publication timestamps older than 60 days are withheld. Explicitly published official employer feeds may retain older open roles. Employer posting endpoints are checked again before external Apply, including known closure signals. A source check is evidence of publication at that time, not a hiring guarantee.

All 16 regions are searchable; Accra has prominent shortcuts. Scholarships use Undergraduate, Master's, MPhil and PhD filters. Jobs/early careers use employment/programme and experience filters.

## Database and deployment

Apply `supabase/migrations/20261017005155_ghana_catalogue.sql` once. Both new tables use RLS and revoke anon/authenticated access; only the backend service role reads/writes them or claims a refresh. Public endpoints strip internal check URLs. Explicit service-role-only policies document backend ownership; public client roles have no private table privileges.

Deploy backend and frontend from the same commit, retaining existing Supabase server credentials and frontend BACKEND_API_URL. Never expose the service key. Invoke `/api/catalogue/refresh` once if due, then check category/region filters, stable detail URLs and external Apply. Google/Bing verification and opt-in analytics remain configured.

Tests cover expired/stale eligibility, closure, category semantics, Ghana-only remote eligibility, region mapping, deadline parsing, missing source details, session integrity and account isolation. Previous browser verification covered mobile/desktop, all regions, category-specific filters, MPhil/internships, external Apply, tracker sign-in gating, CV removal/redirect, analytics consent and browser errors. The reliability release adds 45 regression checks, SQL token/outbox lease checks, a production build and live HTTP checks; this managed session did not provide interactive browser automation. Source counts vary at each refresh.

The global theme uses the owner-supplied Ghana flag and kente artwork, with red, gold, green, black and white reading surfaces. The kente WebP is lossless and pixel-identical to the uploaded PNG. Header/footer, home, search, details, authentication, tracker and policy pages share this theme.
