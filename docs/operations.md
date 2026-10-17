# Operating jobs.ac.ghana

Updated 17 October 2026. The public address is https://zagjobsearch.vercel.app; jobs.ac.ghana is the product name, not a claimed registered domain. No subscription, paid API, plan upgrade or payment processing is introduced by this release.

## Release and verification

The frontend and backend deploy from the same GitHub main commit to their existing Vercel projects. Run `python -m unittest discover -s backend/tests -v` with `PYTHONPATH=backend`, then frontend ESLint and `npm run build`. Runtime Python dependencies are pinned in `backend/requirements.lock`. CI uses exact action commit SHAs, read-only repository permissions and no production secrets for pull requests.

Migrations are additive. Apply `20261017171133_production_reliability_accounts.sql` and `20261017173851_invalidate_account_links.sql` before the new API. Deploy the new API, then apply `20261017172815_automatic_maintenance_schedule.sql`. That schedule is intentionally enabled only after its protected endpoints exist. Rolling back application code does not require removing new columns or user data.

Supabase pg_cron runs the catalogue due check every 15 minutes. Successful collection becomes due after six hours; a partial or failed check retries after 30 minutes. A 10-minute atomic lease prevents overlapping refreshes. Source readers have per-host/global concurrency limits, one retry for transient connection/502/503/504 errors, a 130-second collection bound and a 25-second bounded recheck of previously tracked windowed-source records. Forbidden and rate-limited responses are not bypassed.

The optional email worker runs every 15 minutes. It reconciles verified, opted-in reminders and saved searches, then leases up to 100 queued messages. SMTP success precedes the sent marker. Stale leases retry; expired links and cancelled/deleted reminders are excluded. SMTP cannot provide mathematically exactly-once delivery if a process dies after provider acceptance but before the database acknowledgement; a stable Message-ID and dedupe key reduce duplicates.

The private maintenance secret is generated inside the database. It is not committed or placed in public JavaScript. Routine status checks may be dispatched with `select app_private.dispatch_maintenance('check');`; inspect only status and response content in `net._http_response`, never the request-header queue. Only postgres can dispatch these fixed destinations; verification is service-role-only. Do not expose cron, outbox or token tables publicly.

Cleanup runs daily at 03:30 UTC: expired rate/token records, email queue records over seven days and applications explicitly deleted over 30 days. Existing profiles and active application history are preserved.

## Live checks and failure handling

`python scripts/healthcheck.py` checks fresh catalogue data, server-rendered job content, the sitemap and robots.txt. `.github/workflows/health.yml` runs it every six hours and can be run manually. GitHub displays failed runs; enable repository workflow-failure notifications in your own account if you want email alerts. GitHub schedules can be delayed and are not an uptime SLA.

The public Sources page distinguishes successful, unavailable and external-only sources. Unknown salary, experience or deadline values stay unknown. An empty region or programme tab is valid when no eligible source records exist. Job boards may reject automated use or change their page formats. LinkedIn/Jobberman and other external-only destinations do not become importer APIs simply because they have public web pages.

Problem reports go to the private `job_reports` table in the connected Supabase project. Review open reports in the Table Editor, inspect the attributed original posting and close confirmed invalid catalogue records. Anonymous reports do not automatically hide a listing, since that would allow abuse. Source presence is not an employer background check or a guarantee of hiring.

## Email delivery: owner setup still required

The app's existing password accounts use its own hashed-password table. Therefore setting Supabase Auth SMTP alone does **not** configure these application emails. Configure the following **backend Vercel production environment variables**, using the provider's credential fields rather than sending secrets in chat:

- `SMTP_HOST`, `SMTP_PORT` (the worker currently supports implicit TLS, normally 465)
- `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (a sender the provider permits)
- `FRONTEND_URL=https://zagjobsearch.vercel.app`

Use an existing provider/account that permits your intended sending volume without charges. There is no promise that a free provider can send unlimited email. Redeploy the backend after adding variables. `/auth/config` exposes only capability flags and the existing public Supabase key, never SMTP credentials. Test delivery with an owner-controlled account, verify the sender and spam placement, then test a recovery link once and confirm replay fails. New registrations require verification only when email is configured; existing accounts can continue to log in. Verified email and explicit opt-in are required for reminder/alert delivery.

Until delivery is configured and tested, recovery/reminders are implemented but not operational; the UI says so. In-app tracking, deadline dates and exports remain usable.

## Google sign-in: owner setup still required

Google was disabled in the Supabase project's public Auth settings during this audit. Create or reuse an owner-controlled Google Cloud OAuth web client and configure the Supabase Google provider with its client ID and secret. Use these addresses:

- Google authorised JavaScript origin: `https://zagjobsearch.vercel.app`
- Google authorised redirect URI: `https://yjrmvnmjaujnjmvcwmfc.supabase.co/auth/v1/callback`
- Supabase Site URL: `https://zagjobsearch.vercel.app`
- Supabase redirect allow-list entry: `https://zagjobsearch.vercel.app/api/account/google/callback**` (the app adds a random state query parameter; keep the origin/path fixed)

Review the consent screen and testing/production publication settings. Set backend `GOOGLE_AUTH_ENABLED=true` only after the provider and redirect configuration work, then redeploy. The app validates Supabase's verified Google identity on the server and uses PKCE/state cookies. New Google users complete age/terms onboarding before saving applications. Do not enable a button for an unconfigured provider.

Official references: https://supabase.com/docs/guides/auth/social-login/auth-google and https://supabase.com/docs/guides/auth/redirect-urls.

## Backups and recovery

The encrypted backup workflow is prepared but **does not run successfully until the owner configures repository Actions secrets**. Required secrets are `SUPABASE_BACKUP_URL`, `SUPABASE_BACKUP_SERVICE_KEY` and `BACKUP_ENCRYPTION_KEY` (base64 of 32 random bytes). Store a separate copy of the encryption key outside GitHub; losing it makes backups unreadable. Restrict who can edit main and Actions, since service credentials are privileged. Do not enter these secrets into issue comments or chat.

The daily workflow snapshots profiles, applications, application events, old career profiles and saved searches. It encrypts in memory with AES-256-GCM, verifies decryption/integrity and uploads only an encrypted artifact retained for seven days. Rate-limit buckets, recovery tokens, email bodies and regenerable catalogue data are excluded. Records may change during collection; relational checks reject an inconsistent snapshot rather than uploading an invalid one.

Local checks have verified encryption/decryption, incorrect-key rejection, completeness and account/application relationships. `python scripts/backup.py verify FILE.enc` validates an encrypted artifact without printing personal data. **This is not a full PostgreSQL backup and not a completed disaster-recovery test.** Supabase Auth identities, project settings, schema, email-provider configuration and storage are not included. Migrations in this repository plus the original workspace schema are needed to rebuild the database. Export Supabase Auth separately if Google sign-in is enabled.

Before claiming recoverability, restore a decrypted snapshot into an isolated empty test database using the correct schema, preserve IDs/FKs and status events, invalidate all sessions, and test login/export/tracker there. Do not import test restores into production. Keep a dated restore record. No new paid project or backup product is automatically purchased.

## Search indexing

Both previously provided Google and Bing verification tags remain in the document head. Public job pages contain server-rendered details, their own titles/descriptions and canonical URLs. The sitemap includes fresh primary opportunity pages and nonempty region pages. Expired jobs leave search/sitemaps; private account pages are noindex. JobPosting structured data is limited to jobs with a real publication date and sufficient original description; board summaries and scholarship notices are not falsely marked as complete jobs.

From the owner's verified Search Console property, submit https://zagjobsearch.vercel.app/sitemap.xml, inspect the home/search page and a current job URL, then request indexing. Check the Page indexing report afterwards. Do the equivalent sitemap submission in Bing Webmaster Tools. Website changes cannot establish ownership inside an inaccessible account or guarantee ranking/date of indexing.

In Google Analytics, review Enhanced Measurement and disable automatic page/history/form/outbound capture so that the intentionally sanitised manual events remain the collection surface. The code excludes query parameters, fragments, names, email, CV and application contents from its events. Advertiser features are disabled; consent is optional.

## Growth and monetisation

Share individual job links using the share/WhatsApp controls, saved searches and existing campus or community channels you manage. Measure consented Apply/save/signup actions before spending money. No messages are sent to groups automatically. The About page explains independent Ghana coverage and the public address. The sponsor information page supports one-off enquiries without subscriptions, invented partners, prices, sponsorship deals or accepting money.

Before accepting sponsorship or advertising, confirm the hosting plan permits commercial use. Vercel's Hobby documentation restricts that plan to personal, non-commercial use: https://vercel.com/docs/plans/hobby. A strict zero-dollar budget may require a host that permits commercial activity rather than a paid Vercel upgrade. No paid hosting change is authorised or made by this release.
