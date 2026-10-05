# ZagJobSearch preview and release setup

This draft replaces the previous interface with white, lavender, mint and charcoal surfaces, a polished ZB monogram with ZagJobSearch beneath, faint local photographs in every homepage section, and smooth hover transitions with reduced-motion support. Search, application tracking and CV assistance have equal prominence. Production has not been published.

## What is implemented

- Public search across 249 ISO countries and territories, default Ghana. Tabs cover permanent, part-time, internships, graduate roles, apprenticeships, contracts and scholarships. Keyword, country, remote, experience, industry and supplied salary filters are included.
- Full role details on ZagJobSearch. Apply opens the original source in another tab for everyone. Signed-in users save the role as Started, then confirm Applied after submitting externally.
- Private application CRUD with all core fields, six statuses, date ordering, status filters, notes, activity history and reminders two days before supplied deadlines. Unknown deadlines need a user-selected reminder date. Daily email delivery is opt-in and requires SMTP configuration.
- CV upload from PDF, Word or text, editable fact confirmation, source-preserving tailoring, recognised-skill gaps, cover letter scaffold, and PDF/Word exports. Uploads are processed in memory and discarded. Only an explicitly opted-in verified profile is persisted. Documents are held in browser state. This $0 release uses deterministic formatting and matching, not a paid or free LLM. It does not invent experience or estimate hiring probability. It cannot evaluate every profession's requirements automatically.
- Signed 12-hour sessions in HttpOnly cookies, same-origin mutation checks, and owner filters on all private records. Google sign-in uses Supabase PKCE when enabled. Existing email accounts first register using their email/password so age and terms confirmation are retained; Google can then sign in using that email.
- Homepage metadata, canonical URL, WebSite schema, social image, robots and sitemap, with Search Console verification support. Private pages and syndicated job details are noindex.

## Sources and limits

Himalayas and optional Adzuna are handled by FastAPI. Next adds cached Jobicy and Remotive public feeds, Arbeitnow for Germany/UK, public SmartRecruiters company boards, and Opportunity Desk's public RSS excerpts. Default company boards include AmaliTech, WACSI, Sumundi, DevelopersInVogue and JobsForHumanity. Additional public boards can be configured through PUBLIC_SMARTRECRUITERS_BOARDS. Sources fail independently. Public provider/source links are retained. Remotive listings and descriptions are not gated behind signup; syndicated listings are not submitted to Google Jobs.

Coverage depends on those providers. It is not every posting worldwide. Fuzu's old endpoint is blocked and no verified replacement API credential was supplied, so it is not connected. No login-only LinkedIn, WhatsApp, or restricted pages are scraped. Opportunity Desk supplies excerpts with regional categories; users must check exact eligibility and the provider's application instructions at source. Adzuna does not cover Ghana, so Ghana local roles rely on public company boards plus regional opportunities. Feed windows and page limits are finite. Unknown salaries are excluded from salary filters; currency and period must match.

The supplied FreeLLMAPI project routes model requests and supplies no jobs. The reviewed ai-job-search and career-ops repositories informed source adapters and career workflows; they are not universal scraping APIs. No third-party repository code has been copied.

## Setup required before live feature verification

1. Open the correct Supabase project, SQL Editor, and run **backend/migrations/001_jobseeker_workspace.sql**. This creates applications, events and opt-in career_profiles, preserving profiles. Private tables have RLS and no browser anon/authenticated table grants. Only the service role is granted access through FastAPI's authenticated ownership checks. The existing project's applications and career_profiles tables were absent during read-only inspection; this migration has not been applied by Codex.
2. Backend Vercel environment: retain SUPABASE_URL and SUPABASE_SECRET_KEY; add a unique random SESSION_SECRET. Keep existing Adzuna keys. Redeploy the backend preview. Never prefix these private values with NEXT_PUBLIC.
3. Frontend Preview environment: point BACKEND_API_URL (or existing NEXT_PUBLIC_API_URL) at the **updated backend deployment**, not the old production API. If backend preview protection blocks server-to-server calls, configure the appropriate Vercel deployment protection bypass for this integration through the owning team's dashboard. Do not make account tables publicly readable. Reconnect the Vercel app to **bless-mawumenyo-zaglago** to let Codex inspect/configure the correct projects; current access returned team-scope 403.
4. Enable Google in Supabase Auth Providers using your Google OAuth client. Set the Supabase callback shown in the provider dashboard in Google Cloud. Add the production and preview app callback URLs to Supabase's allowed redirect list, including the callback's state query. Backend: SUPABASE_PUBLISHABLE_KEY and GOOGLE_AUTH_ENABLED=true. Supabase PKCE handles token exchange; this release signs in only after an email account exists. See https://supabase.com/docs/guides/auth/social-login/auth-google.
5. To enable requested email reminders: backend SMTP_HOST, SMTP_PORT (465), SMTP_USER, SMTP_PASSWORD, SMTP_FROM, FRONTEND_URL. Use your authorised SMTP account within its free quota. Set the same strong CRON_SECRET on frontend and backend. frontend/vercel.json runs once daily at 06:00 UTC in production. This is a daily date-based reminder, not exact-hour delivery; missed dates are caught up before expiry. The first release sends at most five reminders per invocation. Larger volumes need a scheduler/queue and provider quota review before making delivery promises. The cron will not send from a preview deployment. https://vercel.com/docs/cron-jobs/usage-and-pricing.
6. Review the frontend preview. Test real signup/login, create/edit/delete records, two accounts' privacy, upload/export, external Apply, and a test reminder after setup. Only then approve publishing both frontend and backend. Local tests use fixtures and do not prove deployed database/Google/SMTP configuration.

## Get the brand into Google

After the reviewed production deployment is public:

1. Open https://search.google.com/search-console and add the URL-prefix property **https://zagjobsearch.vercel.app/**. Use URL-prefix because you do not own vercel.app DNS.
2. Choose HTML tag verification. Copy only its content token into frontend Vercel's **GOOGLE_SITE_VERIFICATION** environment variable, set NEXT_PUBLIC_SITE_URL=https://zagjobsearch.vercel.app, and redeploy after approval.
3. Verify ownership in Search Console. Submit **https://zagjobsearch.vercel.app/sitemap.xml** in Sitemaps. Inspect the homepage URL, test the live URL, and request indexing.
4. Monitor indexing reports and search performance. Keep the exact ZagJobSearch name and homepage link on your public profile/posts. Google controls indexing and rankings; submitting a request does not guarantee appearance or a deadline.

Official guidance: https://support.google.com/webmasters/answer/9008080 and https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl.

## Validation

- Frontend production build and TypeScript, ESLint.
- `cd frontend && node --test tests/*.test.cjs`: country eligibility, malformed URLs, expired roles, salary units, listing types, source failure and pagination.
- `cd backend && python -m unittest discover -s tests -v`: Himalayas normalization; invalid/expired sessions; cross-account ownership filters; Started/Applied confirmation; two-day reminders; confirmed CV evidence; upload disposal; actual PDF/Word exports.
- Chromium checks use isolated fixture requests, with no live account creation or email delivery. They cover public details/Apply, account gate, tracker create/status/date, CV download and responsive layouts.
- Database migration, deployed account workflows, Google OAuth and SMTP still require setup and live verification. Logouts clear the browser cookie; there is no server token revocation before the 12-hour expiry in this release.

## Images

The original transparent ZB artwork was generated for this project from the approved reference direction. Photographs are downloaded Unsplash images, hosted locally:

- teamwork.jpg: https://images.unsplash.com/photo-1521737711867-e3b97375f902
- career-desk.jpg: https://images.unsplash.com/photo-1454165804606-c3d57bc86b40
- workplace.jpg: https://images.unsplash.com/photo-1497366754035-f200968a6e72

Font for Unicode PDF output: bundled DejaVu Sans, with license in backend/assets/FONT-LICENSE.txt. The font supports many scripts, but PDF shaping for all world languages is not guaranteed; Word exports preserve Unicode text.
