# Ghana opportunity coverage expansion, 23 October 2026

The owner's request is more coverage in every main category, including opportunities discovered through Opportunities for Youth. Maintain Ghana eligibility, the existing jobs/early careers/remote/funding separation, truthful missing fields, external application destinations, automatic checks and the $0 operating budget. No matching chatbot or CV assistant is part of this release.

## Production baseline

The last verified production refresh before this release completed at 15:24 UTC: 246 regular jobs, five early-career roles, nine Ghana-eligible remote roles and seven open funding opportunities. All 34 connected readers completed that refresh. Counts measure distinct published catalogue records, not advertised seats, all vacancies in Ghana or all notices on a discovery board.

## New source readers

| Reader | Verified source-check result | Eligibility and scope |
| --- | --- | --- |
| Wikimedia Foundation, public Greenhouse API | 13 remote roles | Ghana must appear in the role's hiring-country list. The US-only software internship is excluded. |
| Canonical, public Greenhouse API | 92 remote roles | Only employer-labelled worldwide home-based roles qualify. Region-specific title/location restrictions override that tag; an EMEA label alone is insufficient. |
| GiveDirectly, public Greenhouse API | Two remote roles | The specific role must name Ghana in its hiring-country statement. A generic remote label or mention of Ghana is insufficient. |
| Marriott International | 29 Ghana roles | All pages of the country-filtered public index are checked and counted. Each individual posting must independently confirm a Ghana work address and matching posting ID. |
| Votex 365 | Six internship roles | The three group cards link to six separately described roles. Individual IDs preserve the role distinction while application links retain their source section. No pay or exact posting date is inferred. |
| University of Ghana careers service | One internship announcement | Named-employer Ghana internship notices published in the last 14 days. Events and internship-letter pages are excluded. No deadline is invented. |
| National Youth Authority | One apprenticeship registration programme | Official eligibility, the published portal link and its public client asset advertising open apprentice registration are checked. Nationwide registration is not a paid-job guarantee or confirmed placement. |

Canonical graduate job titles retain a graduate classification; the remote tab also exposes graduate and apprenticeship filters. Foreign salary examples from Wikimedia/GiveDirectly are not presented as Ghana salary offers. All three new Greenhouse boards receive individual posting and eligibility checks again before Apply.

Application tracking now distinguishes different role titles and companies sharing the same source URL. This allows both individual Votex roles in a source section to be saved, while repeated saves of the same vacancy still return its existing active tracker entry.

Marriott's index has a maximum of 100 postings and a complete-pagination count check. Country filters survive pagination. An unchanged detail URL alone does not establish an active Marriott opening; index membership is rechecked before Apply. Common Marriott employer names are normalized for cross-board duplicate detection. A trainee title alone does not prove an internship or graduate programme.

## Official funding calls

Seven additional provider readers each returned one confirmed open opportunity:

| Provider | Opportunity | Search subsection |
| --- | --- | --- |
| University of Lincoln | Global Leaders Scholarship | Undergraduate and taught master's; partial tuition funding |
| Harvard Graduate School of Design | Loeb Fellowship | Mid-career fellowship, not a degree |
| Oxford Bodleian Libraries | Visiting Fellowships in Special Collections | Research fellowship; postdoctoral and award-specific eligibility |
| Columbia Italian Academy | Research Fellowship Programme | Postdoctoral/research fellowship; PhD required |
| UNESCO | SCRS Research Continuity Grants for Africa | Research grant; the existing master's qualification is not a funded master's degree |
| UCL Institute of Education | HP-UCL AI in Education Fellowship | Funded professional training; travel/visa costs excluded |
| London School of Economics | MPhil/PhD Demography studentship consideration | MPhil/PhD; complete application must meet the funding deadline |

Provider pages are the authority for eligibility and application deadlines. The LSE funding deadline precedes its later admissions deadline; Harvard's recommendation deadline is separate from the application deadline. Exact clocks and time zones are preserved. Lincoln's earlier closed intake does not close its subsequent advertised intake. No programme year is converted into an application deadline. Date-only notices explicitly say the exact closing time is not provided.

Calls found through Opportunities for Youth retain the discovery article alongside the original provider link, with visible attribution. The site also lists Opportunities for Youth and Opportunities for Africans as discovery destinations. Their full feeds are not represented as connected imports. Opportunities for Youth's automated feed returned a browser challenge (403); it was not bypassed. LJMU's robots rules exclude this site's crawler, so that automated provider reader was not added. No foreign-only, expired or unverifiable example is inserted to fill a filter.

These are reviewed programme adapters, not an autonomous system for trusting every new worldwide article. The existing schedule monitors their provider pages; additional providers still need an eligibility/parser review. Source-format failures remain visible and never prove that every opportunity from a provider closed.

## Wider local-board discovery and navigation

Jobweb Ghana now checks 12 recent index pages, plus its published internship, part-time, temporary and freelance categories. The source preflight returned 36 accepted current adverts, compared with 32 in the production baseline. This remains a bounded window, with current detail checks and exact stated deadlines or a recent explicit rolling window. Template salaries/locations do not override readable adverts. An older vacancy falling out of discovery does not establish closure.

Regional pages now separate regular jobs, early-career programmes and mapped remote roles, matching what the regional coverage totals count. Nationwide apprenticeship registration is visible in the regions it serves. Regions with no regular jobs remain excluded from search indexing, avoiding pages promoted solely because the same nationwide programme appears in each region.

## Verification and operation

- Backend regressions cover Ghana/foreign/ambiguous eligibility, US-only internships, salary context, precise application deadlines, provider closures, redirected/substituted URLs, complete country-filtered employer pagination, duplicate identities, internship expiry and government registration semantics.
- Production frontend build, lint, route/security tests and live source preflights validate the integration. Public search/detail/Apply and source health are checked after the matching frontend/backend production deployments.
- One existing Ghana Current Jobs check timed out in the initial 47-reader preflight; a targeted retry returned 98 accepted adverts in 55.5 seconds. Existing recently checked records remain available on a failed source check. The expanded full preflight and production refresh establish the final release health separately.
- Bulk windowed-board checks now preserve successfully verified individual records when another advert fails or their 100-second work budget expires. Incomplete refreshes explicitly report `partial` with a failed-check count and trigger the existing retry schedule. They cannot close missing records, reuse feed-only facts after a failed detail check, or advance the timestamps of unverified records. The public sources page shows this distinction. This fixes the all-or-nothing board failures reproduced in preflight without describing a partial scan as healthy.
- The expanded registry shares at most 24 requests across providers while retaining the existing limit of three requests per host. This reduces queue contention without increasing concurrency against an individual publisher. Source budgets and tracked-page checks remain bounded inside the existing maintenance request window.
- The final full-load preflight completed in 86.1 seconds: 47 readers completed all checks, while Jobweb returned 34 verified current adverts and explicitly flagged nine unsuccessful checks. Ghana Current Jobs returned 98 records without failures. All 14 new readers passed. Preflight inventory before cross-source duplicate handling was 291 regular jobs, 13 early-career opportunities, 116 Ghana-eligible remote roles and 14 open funding opportunities. Do not present that pre-deduplication regular-job figure as the final public total.
- Local verification passed 158 backend tests with five environment-dependent database tests skipped, 15 frontend route/security tests, a full production build, zero-warning lint, Bandit's medium-severity scan and compiled-page checks for new filters and regional categories. CI also runs the disposable database suite and dependency audits.
- The release adds 14 readers to the previous 34, using the existing six-hour refresh schedule, automatic failure retries, source monitoring and 48-hour freshness ceiling. No new paid service, secret or database migration is required.

Source-check counts above are preflight measurements. The pull request records the final production refresh and deduplicated public inventory after deployment; future totals change as providers open and close calls.
