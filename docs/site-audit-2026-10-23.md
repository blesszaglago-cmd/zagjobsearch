# Site audit, 23 October 2026

Scope: the live frontend and backend, public search and details, account request boundaries, application tracking, scheduled maintenance health, database privileges and dependency/source scans. The baseline was production commit `ae273716b0effc9e07f09f823382721fd3bb86e9`.

## Findings and repairs

| Reproduced problem | Repair |
| --- | --- |
| Negative or reversed salary ranges, invalid pages and unknown categories returned an unavailable-service response through the frontend. | Preserve the backend's actionable HTTP 400 validation message. Keep real upstream failures generic and return 503. Failed responses cannot be cached. |
| Selecting a pay period without an amount returned every job, including jobs with no stated pay period. | Apply the period and currency constraint independently of numeric salary bounds. Retain the default unfiltered search when no pay criterion is selected. Add a daily option and reject invalid period values. |
| Whitespace-only application titles, company names, account names and saved-search names passed minimum-length checks. | Trim the relevant fields before validating their lengths. Preserve free-text notes. |
| Infinite tracker salary values passed model validation. | Reject all nonfinite salary numbers before database access. Retain salary-range ordering checks. |
| Tracker validation errors became a generic failure message. | Display the actual validation messages. Non-JSON service failures receive a usable error message. |
| Malformed private record IDs could reach UUID database comparisons. | Validate application and saved-search IDs at the API boundary. |
| A stale application editor could update a soft-deleted row, and history reads still included deleted records. | Require an active, owned record for edits and history. The existing explicit restore route remains available. |
| Apply error responses lacked an explicit no-store policy. | Apply no-store to closed and unavailable responses as well as successful external redirects. |
| Guest Apply clicks attempted an unnecessary private save request. | Save automatically only after account state confirms a signed-in visitor. Avoid repeat saves while a request is pending. |
| The explicit `Sr.` seniority abbreviation remained unspecified. | Recognise the abbreviation in the parser and correct only matching active public records whose experience level was unspecified. Preserve source-check timestamps. |
| A rejected sign-out network request had no handled UI state. | Handle the failure, show a retry message and prevent repeated clicks during sign-out. |
| Five framework lint warnings covered internal account navigation. | Use client routing for account transitions and native GET form navigation for the OAuth route handler. |

The additive migration `20261023145423_standalone_pay_period_filter.sql` replaces the search function while preserving source filters, academic status counts, security-invoker mode, an empty search path and service-role-only execution. It also applies the narrow public seniority correction. It does not alter private account or application records.

## Verification

- The initial live HTTP pass covered 27 public pages, API routes and guest account boundaries. Public pages rendered, private API reads returned 401, account responses used no-store and empty regional pages used noindex.
- Live browser checks covered the homepage search, opportunity tabs and page state. Browser-extension errors were distinguished from application errors.
- Backend regression suite: 129 tests, with five tests requiring disposable PostgreSQL skipped locally. The CI PostgreSQL job exercises the migration, academic states, pay-period and currency combinations, seniority repair and function execution privileges.
- Frontend security/request regressions: 15 passing tests after the Apply-page follow-up. Coverage includes private cookies, CSRF origin checks, protected routes, search validation, upstream error redaction, Apply caching and browser error navigation.
- Frontend production build passed. ESLint completed with zero errors and zero warnings.
- Full npm dependency audit reported zero known vulnerabilities. Both backend and optional restore dependency audits reported no known vulnerabilities. Bandit source checks passed at medium severity and confidence.
- Database inspection confirmed RLS on all application tables, no table grants to anon/authenticated and no execution grants to those roles on the reviewed application RPCs. The catalogue refresh and existing maintenance schedules were healthy.
- Failed email queue entries inspected in aggregate were expired historical account links. This audit did not send test emails or submit external applications.

The pull request records the exact CI results, production commit and final deployed HTTP checks.

During the live Apply spot check, Fido no longer listed the Account Assistant national-service role in its complete Ghana careers index. The existing source recheck correctly closed that catalogue record and blocked the redirect. The follow-up gives browser visitors a themed explanation page for closed or temporarily unconfirmed application links. JSON clients retain HTTP 410/503, successful applications still redirect directly to the external source, and error responses remain non-cacheable and excluded from indexing.

## Remaining verification limits

- Vercel runtime-log access returned 403. No authenticated CLI installation was available as a fallback. This is an observability access gap, not evidence of a clean runtime log or an application outage.
- Supabase retains the existing `pg_net` extension-in-public placement warning. Moving this extension requires a separate maintenance plan for the active scheduled HTTP work. No extension was dropped. Performance advisories were informational unused-index findings on the small dataset, not a reason to remove indexes needed as usage grows.
- No fresh owner credential entry, mailbox delivery test, independent penetration test or current mobile performance measurement forms part of this audit. Prior successful owner signup, verification and login remain separate evidence.
- Source checks and expiry rules reduce stale listings. They do not establish complete Ghana coverage or guarantee that every publisher reflects every closure immediately.
