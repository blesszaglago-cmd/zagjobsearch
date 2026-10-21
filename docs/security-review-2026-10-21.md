# Security review, 21 October 2026

Site: https://zagjobsearch.vercel.app/

Reviewed base: `f68266a84e07f8825f43f3d4a29f9a826ad4e4f1`. Remediation is committed alongside this report. This is a scoped source, configuration and regression review, not independent penetration-test certification. User application records were not retrieved or modified. No destructive injection, load test, account email or external job application was performed.

## Changes

- Replaced text arrows, carousel chevrons, search and checklist glyphs with shared inline SVG icons. Existing labels and the Ghana design remain.
- Updated `certifi` from `2026.7.22` to `2026.10.19` for [GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2), published 20 October. This updates the trust bundle used by Python HTTPS clients.
- Parse third-party RSS with pinned `defusedxml==0.7.1`. Reject DTD/entity declarations and isolate failed feeds.
- Removed submitted input and exception context from validation responses. A mismatched signup password previously caused the entire submitted form to appear in its 422 response.
- Reject non-ASCII maintenance authentication cleanly. Compare frontend cron headers using byte lengths and constant-time comparison; malformed headers previously caused server errors.
- Added backend input-boundary tests, frontend cookie/origin/authorization tests, and dependency/source checks on pull requests, main pushes and weekly. The workflow uses read-only repository permission and no production secrets.

## Evidence

| Check | Result |
| --- | --- |
| Backend regressions | 63 passed, including six new security boundary tests. |
| Frontend security tests | Six passed: malformed cron auth, missing configuration, cross-origin changes, guest access and secure session cookies. |
| Frontend quality | ESLint, TypeScript and production build passed. |
| Python dependencies | 49 pinned runtime packages checked with pip-audit 2.10.1; no known vulnerabilities after remediation. |
| Frontend runtime dependencies | `npm audit --omit=dev` reported zero known vulnerabilities. This excludes development tools. |
| Python source | Bandit 1.9.4 reported no medium/high findings after remediation. Remaining low-severity notices were reviewed, not globally suppressed. |
| Current tracked-source secret patterns | No matches for the tested private-key, Supabase secret, GitHub token or Google OAuth secret patterns. This is not a full historical credential audit. |
| Database access | All 11 public application tables and the private maintenance table have RLS enabled. `anon` and `authenticated` lack direct SELECT/INSERT/UPDATE/DELETE privileges on them. |
| Server RPCs | Six checked application RPCs use invoker security, contain no dynamic EXECUTE, and are not executable by `anon` or `authenticated`. |

### SQL injection checks

Catalogue search uses a fixed SQL function and JSON parameters, not concatenated SQL. Email lookup uses the PostgREST client's encoded filter parameters. Tests use the actual HTTP query builder with an in-memory transport to verify that hostile strings cannot add REST filters or alter the RPC path.

Read-only database checks supplied a quote/comment-shaped query and a filter-shaped location. The former became the full-text terms `'1' & '1'`, matching 21 public jobs versus a 198-job baseline. It did not execute `OR` as SQL or return the entire catalogue. The location expression matched zero jobs. Counts are a dated snapshot. An invalid SQL-shaped login email is rejected before authentication. Existing regressions also check session tampering/revocation and cross-account application access.

No SQL injection bypass was found in these reviewed paths and cases. This does not establish that every possible attack or deployment configuration has been tested.

## Managed database update completed

On 21 October, the owner created a local custom-format database export before the upgrade. The 581,924-byte archive passed a full read through `pg_restore --file NUL`; this checks archive readability, not a successful restore into an isolated database. No backup contents or database password were uploaded to this repository.

The owner reviewed the offered version and the warning of up to one hour of service downtime, then started Supabase's managed upgrade at 15:37 UTC. At 15:47 UTC, the management API reported `ACTIVE_HEALTHY` on build `17.11.0.003`, and SQL reported PostgreSQL `17.11`. The earlier metadata preflight found zero ltree indexes, GiST float indexes and custom application operators.

Post-upgrade checks found matching catalogue, profile, application and active-schedule counts. All 12 application tables retained RLS, with no direct SELECT/INSERT/UPDATE/DELETE access for `anon` or `authenticated`. The public homepage, catalogue search, job JSON and rendered job details returned 200; the job page retained its external-application route. A guest account request still returned 401. These HTTP checks do not establish an authenticated browser session or a completed external job application.

The dashboard showed its post-upgrade base backup in progress. Completion of that provider backup was not independently confirmed by these checks. The owner keeps the separate pre-upgrade export; restoring that PostgreSQL archive remains unverified and is distinct from the successful encrypted application-data drill below.

## Encrypted application backup verified

The owner configured all three backup repository secrets and started [manual run 39636204717](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39636204717) at 16:35 UTC on 21 October, on main at `e58775c`. GitHub reports success for capture, encryption, decryption/integrity verification and upload. Logs report `verified: true`, and artifact metadata confirms a nonexpired encrypted archive with seven-day retention, expiring on 28 October. No secret values or private backup contents were downloaded for this review.

This application snapshot covers profiles, applications, application events, legacy career profiles and saved searches. It excludes Supabase Auth identities, schema, project settings and storage. It is distinct from the owner's pre-upgrade PostgreSQL export and the provider's base backup. A successful scheduled run and authenticated HTTP/UI recovery checks remain unverified; the local application-data restore is recorded below.

The first successful run used older Node.js 20 actions and `ubuntu-latest`. A follow-up pinned the three official action releases to reviewed Node.js 24 commit SHAs and Ubuntu 24.04. [Run 39637711738](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39637711738) at 16:45 UTC on main `70105c8` passed capture/verification/upload with zero warning/error annotations, independently confirming those updated pins. The owner downloaded the encrypted artifact.

## Local application-data recovery verified

The owner confirmed PostgreSQL 17.11 at `127.0.0.1:5432` and created an empty UTF-8 test database, `zag_restore_test_20261021`. A new standalone helper reads the encrypted ZIP in memory, requests secrets through hidden prompts and verifies the saved key before requesting a database password. It fixes the host and host address to loopback, restricts database names, refuses nonempty destinations, uses parameterized imports and rolls back failed imports or value comparisons. The source URL is not used for a connection.

The helper's five-table schema was checked against read-only production metadata, including columns, constraints, indexes and the application-event trigger. No production records, database password or encryption key were retrieved. RLS is enabled locally with no public table grants. Existing IDs and historical events are preserved; the event trigger is installed after importing history. Restored session versions advance by one, while an actual recovery still requires rotating the session-signing secret to cover sessions issued after an old snapshot.

Guard checks and a dedicated PostgreSQL 17.11 CI job use synthetic data to test encryption-file compatibility, rejection paths, atomic rollback, overwrite protection and recovered history/JSON. Login and CSV helpers use recovered SQL rows with substituted lookups; this is not a full authenticated HTTP/browser or Supabase Auth test.

By 21:17 UTC on 21 October, the owner had restored the actual downloaded artifact from run `39637711738` into the local `zag_restore_test_20261021` database. The terminal reported `restore_verified: true` and `snapshot_session_versions_advanced: true`, confirming import, restored-value comparisons and commit. The same ZIP had already passed decryption with the owner-held key, which the owner confirmed saving in a password manager. PowerShell supplied the locally held key and hidden-entered database password to the reviewed helper functions through process stdin. Only aggregate results were shared, with no credentials or private row values. This completes the local application-data drill; the helper excludes platform settings, RPCs, queues, maintenance and storage and is not a full Supabase rebuild.

## Remaining work

1. **Development dependency advisory.** Full npm audit reports five affected development packages from one `braces` advisory, [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm). Upstream lists no patched version. This dependency is in the lint tooling, not an identified runtime input path. A forced downgrade of the Next.js lint configuration was not applied. Recheck when upstream publishes a compatible fix.
2. **pg_net placement advisory.** The post-upgrade advisor still reports [extension_in_public](https://supabase.com/docs/guides/database/database-linter?lint=0014_extension_in_public). Earlier automatic approval review rejected dropping/recreating the extension because it could interrupt maintenance. The functioning scheduler was retained; no workaround or repeated destructive attempt was made.
3. **Account recovery and backup readiness.** SMTP is configured but delivery failed; Gmail HTTPS delivery and owner verification remain pending. No successful verification/recovery email delivery is claimed. Manual encrypted application backup and an isolated restore of the owner's actual artifact passed. The first successful scheduled run, full platform/authenticated recovery and a restore of the separate pre-upgrade PostgreSQL export remain unverified.
4. **Review limits.** No independent penetration test, production traffic/load test, authenticated browser audit or exhaustive source/history secret scan was performed. The current CSP still permits inline scripts; a stricter policy needs separate validation against the statically rendered Next.js application.
