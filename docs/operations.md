# Operating jobs.ac.ghana

Updated 22 October 2026. The public address is https://zagjobsearch.vercel.app; jobs.ac.ghana is the product name, not a claimed registered domain. No subscription, paid API, plan upgrade or payment processing is introduced by this release.

## Release and verification

The frontend and backend deploy from the same GitHub main commit to their existing Vercel projects. Run `python -m unittest discover -s backend/tests -v` with `PYTHONPATH=backend`, then frontend ESLint and `npm run build`. Runtime Python dependencies are pinned in `backend/requirements.txt` (with the matching lock snapshot retained for CI caching). CI uses exact action commit SHAs, read-only repository permissions and no production secrets for pull requests.

Migrations are additive. Apply `20261017171133_production_reliability_accounts.sql` and `20261017173851_invalidate_account_links.sql` before the new API. Deploy the new API, then apply `20261017172815_automatic_maintenance_schedule.sql`. That schedule is intentionally enabled only after its protected endpoints exist. Rolling back application code does not require removing new columns or user data.

Supabase pg_cron runs the catalogue due check every 15 minutes. Successful collection becomes due after six hours; a partial or failed check retries after 30 minutes. A 10-minute atomic lease prevents overlapping refreshes. Public search responses do not collect sources; only the protected schedule does that work. Source readers have per-host/global concurrency limits, one retry for transient connection/502/503/504 errors, a 130-second collection bound and a 25-second bounded recheck of previously tracked windowed-source records. Forbidden and rate-limited responses are not bypassed.

The optional email worker runs every 15 minutes. It reconciles verified, opted-in reminders and saved searches, then leases up to 100 queued messages. Provider acceptance precedes the sent marker. Stale leases retry; expired links and cancelled/deleted reminders are excluded. Neither transport can provide mathematically exactly-once delivery if a process dies after provider acceptance but before the database acknowledgement; a stable Message-ID and dedupe key reduce duplicates.

The private maintenance secret is generated inside the database. It is not committed or placed in public JavaScript. Routine status checks may be dispatched with `select app_private.dispatch_maintenance('check');`; inspect only status and response content in `net._http_response`, never the request-header queue. Only postgres can dispatch these fixed destinations; verification is service-role-only. Do not expose cron, outbox or token tables publicly.

Cleanup runs daily at 03:30 UTC: expired rate/token records, email queue records over seven days and applications explicitly deleted over 30 days. Existing profiles and active application history are preserved.

## Live checks and failure handling

Local source investigations use [the extracted REA workflow](source-investigation.md): offline request grouping, public JavaScript endpoint candidates and before/after comparison. It adds no production analysis engine or paid service. After a new refresh, source status also includes an optional safe failure category (`http` and numeric status, `timeout`, `connection`, `validation`, or `reader`); old summaries stay null until refreshed. This supports targeted diagnosis without disclosing exception messages or provider bodies.

`python scripts/healthcheck.py` checks backend availability, a catalogue refresh completed within 24 hours, current Ghana jobs, server-rendered job content, the sitemap, robots.txt and unauthenticated Apply denial on both API layers. Stale/failed refreshes, no successfully checked source records or a broken public flow fail the run. Individual partial/unavailable publishers produce warnings and an explicit `catalogue_status: degraded`; they never skip the remaining availability checks. The GitHub job summary lists each source's state, accepted records and failed checks, and the public Sources page keeps the same source warnings. This distinction does not repair or hide external source failures.

`.github/workflows/health.yml` runs every six hours, when the monitor changes on main, and on manual dispatch. A monitor fix therefore gets a fresh run without re-running historical code. GitHub displays real failed runs; enable repository workflow-failure notifications in your own account if you want email alerts. GitHub schedules can be delayed and are not an uptime SLA.

The public Sources page distinguishes successful, unavailable and external-only sources. Unknown salary, experience or deadline values stay unknown. An empty region or programme tab is valid when no eligible source records exist. Job boards may reject automated use or change their page formats. LinkedIn/Jobberman and other external-only destinations do not become importer APIs simply because they have public web pages.

Problem reports go to the private `job_reports` table in the connected Supabase project. Review open reports in the Table Editor, inspect the attributed original posting and close confirmed invalid catalogue records. Anonymous reports do not automatically hide a listing, since that would allow abuse. Source presence is not an employer background check or a guarantee of hiring.

## Email delivery

The app's existing password accounts use its own hashed-password table. Therefore setting Supabase Auth SMTP alone does **not** configure these application emails. Select one transport with `EMAIL_PROVIDER` in the **backend Vercel production environment variables**. Unknown providers and incomplete credentials disable email rather than silently falling back.

For the Gmail HTTPS transport, set:

- `EMAIL_PROVIDER=gmail_api`
- `EMAIL_FROM` to the owner-authorized Gmail mailbox, optionally with the product display name
- `GMAIL_OAUTH_CLIENT_ID`, `GMAIL_OAUTH_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`
- `FRONTEND_URL=https://zagjobsearch.vercel.app`

The owner connects only the service mailbox, using the `gmail.send` permission. This is separate from visitor Google sign-in. Store the client secret and refresh token as Production-only Vercel Secrets, with separate credentials for any future preview testing. Enter values directly in provider settings, never chat, screenshots, source or issue descriptions. OAuth Playground's request/response panel can expose credentials even when its settings panel is closed. After an exposure, revoke the Google Account app connection, replace the client secret, and obtain a fresh refresh token privately.

Gmail refreshes short-lived access tokens in memory for each worker batch. It uses fixed Google HTTPS endpoints with certificate verification, no redirects or environment proxies, and bounded HTTP timeouts. MIME messages are base64url encoded. A message is marked sent only after Gmail returns a successful response with a message ID. Failed, redirected, malformed and rate-limited responses remain failures with bounded queue retries; there is no automatic retry of an individual HTTP send. Provider response bodies, credentials, bearer tokens and message contents are excluded from diagnostics. A token refresh proves authentication, not inbox delivery or Google branding approval. Gmail quotas and permission revocation still apply.

For SMTP, omit `EMAIL_PROVIDER` or set `EMAIL_PROVIDER=smtp`, then configure:

- `SMTP_HOST`, `SMTP_PORT` (465 uses implicit TLS; 587 requires STARTTLS)
- `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` (or `EMAIL_FROM`, a sender the provider permits)
- `FRONTEND_URL=https://zagjobsearch.vercel.app`

The maintenance-key protected `GET /cron/email-status` authenticates with the selected
transport without sending a message. Gmail exchanges the stored refresh token;
SMTP performs its encrypted login. It returns only configuration/authentication flags,
a safe failure category and a numeric HTTP/SMTP code when available. Gmail token
failures can also include an allowlisted `oauth_error` such as `invalid_grant` or
`invalid_client`. Only recognized fixed codes leave the transport; descriptions,
unknown error strings, nested error objects and credentials are omitted. A configured
flag alone does not establish successful login or delivery. Passwords and raw
provider replies are never included in this response or delivery errors. The
private SMTP diagnostic also accepts `?port=465` or `?port=587` to test either encrypted
connection without changing the configured delivery port. Safe exception names
and numeric OS error codes distinguish network failures from rejected logins.
Gmail's grouped 16-letter app-password paste format is accepted. SMTP connections
validate the server certificate and hostname.

Use an existing provider/account that permits your intended sending volume without charges. There is no promise that a free provider can send unlimited email. Redeploy the backend after adding variables. `/auth/config` exposes only capability flags and the existing public Supabase key, never SMTP credentials. Test delivery with an owner-controlled account, verify the sender and spam placement, then test a recovery link once and confirm replay fails. New registrations require verification only when email is configured; existing accounts can continue to log in. Verified email and explicit opt-in are required for reminder/alert delivery.

A future sender or credential change requires a fresh owner-requested inbox check in addition to the authentication probe. Do not resend expired verification/recovery links from the old queue. In-app tracking, deadline dates and exports remain usable.

On 21 October 2026, the owner corrected the Gmail client secret and the backend was redeployed from reviewed commit `efb144a`. Both Gmail credentials remain Production-only Vercel Secrets. The private authentication probe returned `configured: true` and `authenticated: true`. A fresh password-reset email reached the owner's inbox; the owner reset the password and logged in with it. A read-only database check confirmed the latest reset token was marked used, no reset links remained active for that account, the email was verified and the outbox recorded the message as sent. The owner confirmed storing the client secret and refresh token as separate password-manager entries. No credential values are included in this record. Duplicate token submission, standalone signup verification and reminder/alert inbox delivery still require separate checks. Google branding approval and visitor Google sign-in are not established by this sender test.

A later verification request failed with `gmail_api_authentication_failed (400)`;
a fresh private probe reproduced it with unchanged environment metadata. The
allowlisted diagnostic subsequently identified `invalid_grant`; the reason the old
grant became invalid remains unknown. Do not infer a specific cause from HTTP 400
alone. Google documents token endpoint errors at
https://developers.google.com/identity/openid-connect/reference.

On 22 October, the owner obtained a fresh refresh token using their own OAuth
credentials and updated the Production-only Vercel Secret. The first redeployment
returned `invalid_client`. After the owner updated the Production-only client
secret to match the successful Playground exchange, a redeployment from reviewed
commit `a4919bf` passed the private authentication check. A fresh owner-requested
verification email reached the inbox and the site confirmed successful verification.
A boolean-only database check confirmed the address was verified, the latest
verification link was recently marked used, no verification links remained active
for that account and the outbox recorded the email as sent. No credential or
account-link values are included in this record. This covers an existing owner's
verification flow. A later owner-performed Incognito check on 22 October confirmed
new-account signup, refusal to log in before verification, successful verification
and subsequent login to the tracker. A boolean-only database check confirmed the
new verification link was used, no verification links remained active, the address
was verified and its email was marked sent. Duplicate token submission and opted-in
reminder/alert inbox delivery still need separate checks. Google branding and
visitor Google sign-in remain separate work.

Official transport references: https://developers.google.com/workspace/gmail/api/guides/sending and https://developers.google.com/identity/protocols/oauth2/web-server.

## Google sign-in: owner setup still required

Google was disabled in the Supabase project's public Auth settings during this audit. Create or reuse an owner-controlled Google Cloud OAuth web client and configure the Supabase Google provider with its client ID and secret. Use these addresses:

- Google authorised JavaScript origin: `https://zagjobsearch.vercel.app`
- Google authorised redirect URI: `https://yjrmvnmjaujnjmvcwmfc.supabase.co/auth/v1/callback`
- Supabase Site URL: `https://zagjobsearch.vercel.app`
- Supabase redirect allow-list entry: `https://zagjobsearch.vercel.app/api/account/google/callback**` (the app adds a random state query parameter; keep the origin/path fixed)

Review the consent screen and testing/production publication settings. Set backend `GOOGLE_AUTH_ENABLED=true` only after the provider and redirect configuration work, then redeploy. The app validates Supabase's verified Google identity on the server and uses PKCE/state cookies. New Google users complete age/terms onboarding before saving applications. Do not enable a button for an unconfigured provider.

Official references: https://supabase.com/docs/guides/auth/social-login/auth-google and https://supabase.com/docs/guides/auth/redirect-urls.

## Backups and recovery

The owner configured all three repository Actions secrets on 21 October 2026: `SUPABASE_BACKUP_URL`, `SUPABASE_BACKUP_SERVICE_KEY` and `BACKUP_ENCRYPTION_KEY` (base64 of 32 random bytes). [Manual run 39636204717](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39636204717) succeeded on main at `e58775c`: capture, encryption, decryption/integrity verification and encrypted artifact upload all passed. The artifact expires on 28 October. The workflow is scheduled daily at 04:13 UTC. The first successful scheduled run is now confirmed: [run 39755042250](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39755042250) completed on 22 October at commit `a4919bf`. GitHub started it at 09:23 UTC; the nominal schedule is not an exact-time guarantee. Store a separate copy of the encryption key outside GitHub; losing it makes backups unreadable. Restrict who can edit main and Actions, since service credentials are privileged. Do not enter these secrets into issue comments or chat.

For `SUPABASE_BACKUP_SERVICE_KEY`, create a separate secret key named `github_backups` in the project's Settings > API Keys and copy it directly into the GitHub repository secret. Use the modern `sb_secret_...` key described in [Supabase's API key guide](https://supabase.com/docs/guides/getting-started/api-keys). The exporter sends it in the `apikey` header, as required for these non-JWT keys. Publishable keys cannot authorize this private backup.

The daily workflow snapshots profiles, applications, application events, old career profiles and saved searches. It encrypts in memory with AES-256-GCM, verifies decryption/integrity and uploads only an encrypted artifact retained for seven days. Rate-limit buckets, recovery tokens, email bodies and regenerable catalogue data are excluded. Records may change during collection; relational checks reject an inconsistent snapshot rather than uploading an invalid one.

The first run reported deprecated Node.js 20 actions and a forthcoming `ubuntu-latest` image change. The workflow now pins official Node.js 24 action releases by commit SHA and uses `ubuntu-24.04`. [Manual run 39637711738](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39637711738) at 16:45 UTC on main `70105c8` verified those updated pins: capture, verification and encrypted upload succeeded, with zero warning/error annotations in the job log. The owner downloaded this encrypted artifact for the recovery drill.

Local checks have verified encryption/decryption, incorrect-key rejection, completeness and account/application relationships. `python scripts/backup.py verify FILE.enc` validates an encrypted artifact without printing personal data. **This is not a full PostgreSQL backup and not a completed disaster-recovery test.** Supabase Auth identities, project settings, schema, email-provider configuration and storage are not included. Migrations in this repository plus the original workspace schema are needed to rebuild the database. Export Supabase Auth separately if Google sign-in is enabled.

Before claiming recoverability, restore a decrypted snapshot into an isolated empty test database using the correct schema, preserve IDs/FKs and status events, invalidate all sessions, and test login/export/tracker there. Do not import test restores into production. Keep a dated restore record. No new paid project or backup product is automatically purchased.

### Local application-data restore drill

The owner confirmed a local PostgreSQL 17.11 server at `127.0.0.1:5432` and created an empty UTF-8 database named `zag_restore_test_20261021`. The downloaded encrypted application ZIP is distinct from the earlier `pg_dump` archive. `pg_restore` cannot import this encrypted application ZIP.

`scripts/restore_backup.py` is a standalone helper requiring Python 3.10 or newer and the optional packages in `scripts/requirements-restore.txt`. Install those packages in a separate virtual environment. Keep both source files available on the owner's computer; no Supabase API key or database password belongs in either file.

First run `python scripts/restore_backup.py PATH_TO_DOWNLOADED_ZIP --verify-only`. Enter the exact saved encryption key at the hidden prompt. This checks the owner-held copy of the key against the actual backup, including accidental key regeneration. The ZIP is read in memory without extracting files or writing a plaintext backup. Unexpected archive members, wrong keys, changed ciphertext, incomplete tables and unsupported columns stop the operation.

Then run `python scripts/restore_backup.py PATH_TO_DOWNLOADED_ZIP --database zag_restore_test_20261021`. The helper requests the saved encryption key and local PostgreSQL password through hidden prompts. It fixes both the host and network address to `127.0.0.1`, accepts only `zag_restore_test_...` database names, and refuses an existing database containing user tables, views or sequences. The snapshot's source URL is never used as a destination.

The helper reconstructs the five application tables, constraints, indexes, RLS and event trigger from the schema reviewed on 21 October. It imports all records using JSON parameters in one transaction and compares every restored value in PostgreSQL before committing. Historical events load before the trigger is installed, avoiding extra events. Restored profile session versions advance by one. Any import or verification failure rolls back the schema and records. Only aggregate verification/counts print; the local database itself contains private restored data and password hashes.

CI runs guard tests and real PostgreSQL 17.11 restores with synthetic fixtures. It checks rollback, refusal to overwrite, preserved IDs/JSON/history, the event trigger, and production login/CSV helpers using restored rows with substituted data lookups. This does not test a browser, the real PostgREST service or Supabase Auth. These synthetic checks are separate from the owner's drill using the actual artifact, recorded below.

By 21:17 UTC on 21 October 2026, the owner had restored the downloaded artifact from run `39637711738` into `zag_restore_test_20261021` on the local PostgreSQL 17.11 server. The shared terminal result reported `restore_verified: true` and `snapshot_session_versions_advanced: true`, confirming the helper's import, restored-value comparisons and commit. An earlier check against the same ZIP reported `encrypted_backup_verified: true`; the owner then confirmed saving the matching recovery key in a password manager. Windows PowerShell supplied the key and hidden-entered local database password to the reviewed helper functions through process stdin, with no secret in command arguments, environment variables or plaintext backup files. Only aggregate results were shared, with no credentials or private row values. This destination now contains the recovered private application data and is no longer an empty test database.

This recovery schema deliberately excludes catalogue data, provider settings, delivery/recovery queues, application RPCs, Supabase Auth identities, storage and scheduled maintenance. It is not a platform rebuild or a production migration. Recheck it when the source schema changes. For a real recovery, also rotate `SESSION_SECRET` before reopening access; advancing a version from an old snapshot alone cannot invalidate every session issued after that snapshot. Complete the remaining platform and authenticated HTTP/UI recovery checks before claiming full disaster recovery.

## Search indexing

Both previously provided Google and Bing verification tags remain in the document head. Public job pages contain server-rendered details, their own titles/descriptions and canonical URLs. The sitemap includes fresh primary opportunity pages and nonempty region pages. Expired jobs leave search/sitemaps; private account pages are noindex. JobPosting structured data is limited to jobs with a real publication date and sufficient original description; board summaries and scholarship notices are not falsely marked as complete jobs.

From the owner's verified Search Console property, submit https://zagjobsearch.vercel.app/sitemap.xml, inspect the home/search page and a current job URL, then request indexing. Check the Page indexing report afterwards. Do the equivalent sitemap submission in Bing Webmaster Tools. Website changes cannot establish ownership inside an inaccessible account or guarantee ranking/date of indexing.

In Google Analytics, review Enhanced Measurement and disable automatic page/history/form/outbound capture so that the intentionally sanitised manual events remain the collection surface. The code excludes query parameters, fragments, names, email, CV and application contents from its events. Advertiser features are disabled; consent is optional.

## Growth and monetisation

Share individual job links using the share/WhatsApp controls, saved searches and existing campus or community channels you manage. Measure consented Apply/save/signup actions before spending money. No messages are sent to groups automatically. The About page explains independent Ghana coverage and the public address. The sponsor information page supports one-off enquiries without subscriptions, invented partners, prices, sponsorship deals or accepting money.

Before accepting sponsorship or advertising, confirm the hosting plan permits commercial use. Vercel's Hobby documentation restricts that plan to personal, non-commercial use: https://vercel.com/docs/plans/hobby. A strict zero-dollar budget may require a host that permits commercial activity rather than a paid Vercel upgrade. No paid hosting change is authorised or made by this release.

## Release verification on 20 October 2026

PR #11 is merged and both production deployments are ready. The database scheduler completed a protected refresh with all 26 connected readers successful. Public HTML, security headers, canonical job URLs, robots.txt, a sitemap with 191 opportunity URLs, external Apply redirects and private-page noindex were checked. A temporary account passed signup/login, tracker edits/history, automatic two-day deadline calculation, CSV safety, delete/restore, saved searches, copied-session revocation, password rotation and permanent account deletion; it was removed afterwards. No verification or reminder email was sent.

At that 20 October release, PageSpeed API verification returned HTTP 429 for the shared service quota, so no score was claimed; interactive mobile/accessibility checks and an actual backup restore had not yet been verified. Google/email provider flags were false in production. Subsequent owner checks and the 21 October local application-data restore are recorded above and in `docs/audit-status.md`.

Supabase currently reports one extension-placement advisory for pg_net. Its HTTP functions actually live in the net schema; the extension metadata was registered in public. Automatic approval review rejected drop/recreate relocation because it could interrupt maintenance or invalidate dependencies. The working extension was retained. A proposal is stored in docs/proposals/maintenance-extension-schema.sql, outside the migrations directory; it is not scheduled or automatically applied. Reconsider only after explicit approval and verification in an isolated compatible database. The next fresh installation uses the extensions metadata schema.
# Source detail progress

The `source_progress_queue` migration must precede deployment of the resumable
Ghana Current Jobs / Jobweb reader. Retry queues and publisher pauses live in the
private `catalogue_refresh.source_progress` column. The public Sources page shows
safe failure categories and queued counts, not queued URLs or raw errors. Confirmed
detail 404/410 responses retire matching records; timeouts preserve them. See
[source tools](source-tools.md) for limits, verification and the isolated parser lab.
