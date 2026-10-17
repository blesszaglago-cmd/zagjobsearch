# Ghana catalogue

Search uses a persisted Ghana catalogue instead of the retired global feeds. Browsing and external applications remain public; application tracking requires an account. CV assistance is retired and `/cv` redirects to the tracker. Existing account/application records are preserved.

## Supported sources

Public SmartRecruiters boards: AmaliTech, Deloitte, SNV, SGS, Accor, Bosch, Standard Bank, AECOM, Mastercard Foundation, Sanlam, Sandvik, WACSI, Sumundi, Developers in Vogue and Jobs for Humanity. Country must explicitly be `gh`. Public Greenhouse boards: Jumia, Scangroup/Ogilvy, Wave and Zipline. Location must explicitly name Ghana. Remote requires an explicit remote designation; Africa/worldwide alone does not qualify.

AngloGold Ashanti's Ghana career pages require Ghana metadata and a recognised Ghana town/region, excluding foreign vacancies mistakenly placed on the Ghana board. Ghana Scholarships Authority notices require Ghanaian eligibility and an explicit future deadline. Levels are extracted from the notice; unknown details remain unspecified.

Supported sources do not mean complete national/industry coverage. Empty boards contribute zero results. Internships, graduate programmes and apprenticeships enter Early careers when eligible current postings exist. Empty tabs are never populated with invented opportunities. Jobberman is excluded: its terms require written approval for automated extraction (https://www.jobberman.com.gh/terms).

## Automation and freshness

`frontend/vercel.json` calls `/api/catalogue/refresh` daily at 05:00 UTC/Ghana time. An atomic service-only database lease prevents overlapping downloads within ten hours, including public refresh requests. Only fixed supported source URLs are fetched. No paid provider is added.

Explicit expiry, removal/closure at the source, or disappearance from a completely successful refresh removes a posting from search. Failed or unrecognisable feeds do not falsely close records; records without a successful check for 48 hours are hidden. Undeadlined jobs with source timestamps older than 60 days are withheld. Employer posting endpoints are checked again on details views, including known closure signals. A source check is evidence of publication at that time, not a hiring guarantee.

All 16 regions are searchable; Accra has prominent shortcuts. Scholarships use Undergraduate, Master's, MPhil and PhD filters. Jobs/early careers use employment/programme and experience filters.

## Database and deployment

Apply `supabase/migrations/20261017005155_ghana_catalogue.sql` once. Both new tables use RLS and revoke anon/authenticated access; only the backend service role reads/writes them or claims a refresh. Public endpoints strip internal check URLs. This service-only design intentionally produces informational "RLS enabled, no policies" advisor entries: https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy.

Deploy backend and frontend from the same commit, retaining existing Supabase server credentials and frontend BACKEND_API_URL. Never expose the service key. Invoke `/api/catalogue/refresh` once if due, then check category/region filters, stable detail URLs and external Apply. Google/Bing verification and opt-in analytics remain configured.

Tests cover expired/stale eligibility, closure, category semantics, Ghana-only remote eligibility, region mapping, deadline parsing, missing source details, session integrity and account isolation. Browser verification covers mobile/desktop, all regions, category-specific filters, MPhil/internships, external Apply, tracker sign-in gating, CV removal/redirect, analytics consent and browser errors. Source counts vary at each refresh.
