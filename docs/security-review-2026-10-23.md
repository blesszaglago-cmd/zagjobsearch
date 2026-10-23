# Security review, 23 October 2026

Scope: jobs.ac.ghana at https://zagjobsearch.vercel.app, its FastAPI backend, this repository and project-specific Supabase/Vercel settings. Reviewed base: `2b8497752fa4b8a1e60315c7dbc7ed3bb27178c9`. This is an authorized defensive review, not an independent penetration-test certificate. Tests use synthetic accounts, disposable PostgreSQL and in-memory providers. No visitor records, passwords, mail contents or production backups were retrieved. No real account was created, no recovery email sent and no external application submitted during this review.

## Threats and findings

| Attack class | How it could affect this product | Review result |
| --- | --- | --- |
| Account pre-hijacking | Someone registers another person's mailbox with a password they know; automatic Google linking subsequently verifies that workspace while retaining the password. | Fixed. First provider binding is transactional. Unverified passwords are discarded, prior sessions advance and outstanding links are invalidated. Verified password accounts retain their password. A different provider identity cannot overwrite a binding. The visitor Google button is currently disabled; the backend path was reviewed independently of that UI flag. |
| Credential and session races | A stale password upgrade or read/modify/write sign-out can overwrite a newer credential/session state. An authenticated email-change request already in progress can issue a link after a reset. | Fixed with conditional hash upgrades, atomic version-checked session rotation and session-version-bound account links. Credential operations lock the profile before token rows, avoiding competing reset-link lock order. |
| Cross-account access / IDOR | Changing an application/search UUID or submitting someone else's user ID could expose or modify their tracker. | Existing ownership controls passed. New HTTP tests cover edit, delete, restore, event history, saved-search deletion and submitted-owner overrides. Database RLS and direct role grants were independently inspected. |
| SQL, REST-filter and command injection | Hostile search text, email filters or record IDs could alter a database query or reach a system command. | Fixed SQL RPCs and encoded PostgREST parameters passed adversarial tests. UUID/status/field validation remains enforced. Public handlers have no command-execution or deserialization feature. No injection bypass was found in the reviewed paths. |
| Server-side request forgery / malicious redirects | A listing provider or stored verification URL could redirect the importer into an internal address before the old post-fetch host check ran. | Fixed. Reviewed hosts only; HTTPS/443; no embedded credentials; same-host redirects validated before sending; bounded hops. DNS answers must be public, the connection uses the validated numeric address and TLS still verifies the original hostname. Apply fails closed without an approved verification endpoint. |
| XSS, XML entities and browser embedding | Imported descriptions, search strings, notes, feeds or URLs could inject executable content, expand XML entities or frame the account interface. | React escaping, JSON-LD escaping, restricted link schemes, defused XML, frame blocking and no-sniff remain. CSP now explicitly blocks inline event handlers and base tags. Apply/manual links reject embedded credentials; Apply rejects unusual ports. CSP's script-element inline allowance remains a documented limitation below. |
| CSRF, OAuth/login forgery and session theft | Another website could submit account changes or swap an OAuth response. | Same-origin mutation checks, PKCE/state and secure HttpOnly cookies passed. Failed OAuth callbacks now clear temporary state cookies. Sessions reject tampering, oversized tokens, expired/wrong-audience/invalid claims and revoked versions before private data can be returned. |
| Resource exhaustion and automated abuse | Large/chunked/compressed submissions, source response bombs or repeated source checks could consume the free database/function budget. | Frontend and backend account JSON capped at 64 KiB before model parsing; reports at 12 KiB on the frontend. Source responses capped at 8 MiB compressed and decompressed; gzip output is bounded during decompression. Signed, short-lived, route-bound IP forwarding replaces caller-controlled XFF. Per-IP and per-account limits cover login/recovery/signup, private reads/writes and Apply verification. This does not prove resistance to every distributed flood. |
| Secret exposure and supply chain | Preview code with production database credentials, a wrongly configured public key, a leaked signing key or a vulnerable dependency could compromise private records. | New preview deployments no longer receive production Supabase/Adzuna settings. Fresh Production-only proxy and session keys were installed as Vercel Secrets without reading existing secret values. The public auth config refuses administrative keys. Dependency audits passed and history-pattern scans found no real credential matches in their scope. Checkout steps no longer persist the CI token. |
| Account discovery / error leakage | Duplicate signup responses or a recovery-provider failure could reveal registered addresses or disclose provider details. | Signup now returns the same message-only response for existing/new addresses, without account IDs. Recovery delivery failure and unknown-address responses match. Password hashing work is performed for both signup cases. No claim of perfectly indistinguishable network timing is made. |

## Deployment and database evidence

- All 11 public application tables and the private maintenance table have RLS enabled and no direct SELECT/INSERT/UPDATE/DELETE privileges for `anon` or `authenticated`. No public storage buckets or duplicate provider bindings were found.
- Anonymous Data API probes requested zero rows. Profiles, applications, account tokens and email outbox were denied; `net` returned `406 / PGRST106`, confirming it is not an exposed API schema. The account-token probe used its actual `token_hash` column and requested zero rows.
- Vercel metadata showed the backend's Supabase configuration and Adzuna credentials scoped to Production and Preview. Those entries are now Production-only. Dedicated `SESSION_SECRET` and matching `INTERNAL_PROXY_SECRET` values are Production-only Secrets. The signing change intentionally ends previous browser sessions once the new backend is deployed.
- Environment changes affect new deployments. Existing immutable previews retain their original environment and remain behind the observed Vercel SSO deployment protection. No claim is made that old deployment environments were erased or that production service keys were rotated.
- The migration is additive: a unique provider-binding index, account-link issuance version, compatibility trigger and service-only invoker functions. It preserves application records and the scheduler. Credential concurrency tests run on disposable PostgreSQL 17.11 in CI; no production test identities are needed.

## Validation

- Backend suite: 188 discovered; 174 ran locally and 14 require disposable PostgreSQL. The separate `backup-restore` CI gate runs those database tests, including nine new account-security cases, with real concurrent connections and synthetic data. Overlapping restore tests are not added to the backend count.
- Frontend: 22 security tests passed; strict ESLint and TypeScript/production build passed.
- Full npm audit, including development packages: zero known vulnerabilities. Locked Python runtime audit: no known vulnerabilities. Bandit: no medium/high findings at the selected confidence threshold.
- History scan: 493 text blobs under 3 MB checked for selected private-key, modern Supabase secret, GitHub, Google OAuth/refresh-token and legacy service-role JWT patterns. One matched modern-key fixture was confirmed to be the explicit test-only dummy. This is a targeted scan, not proof that arbitrary secrets never entered history.
- Provider compatibility: all 48 readers completed through the new redirect/body wrapper using the local environment's required egress proxy. One Ghana Current Jobs batch was partial, retaining 96 checked records and 21 failed checks. Production uses the DNS-pinned transport rather than that local proxy; deployment Apply/source checks must verify that boundary separately.
- Required release gates: backend, frontend, backup-restore and dependency-and-source-audit. Production aliases and safe public HTTP checks must then match the merged release. The pull-request description records the final release evidence.

## Remaining boundaries

1. **Managed pg_net advisory.** Supabase still reports [extension_in_public](https://supabase.com/docs/guides/database/database-linter?lint=0014_extension_in_public) for pg_net. Its `net` schema is not exposed to anonymous REST requests. Supabase documents that project-level revokes on managed pg_net objects are ineffective and can break scheduled HTTP jobs. No extension drop/reinstallation or unsupported privilege rewrite was attempted. The running maintenance schedule is retained.
2. **Custom firewall and runtime visibility.** Unscoped firewall lookups returned no configuration; the explicit known team scope returned 403. This does not establish that platform DDoS mitigation is absent. Custom rules, runtime traces and real-traffic false positives remain unverified until the connection is authorized for that team. No paid service or blocking WAF rule was added.
3. **Strict script CSP.** Next.js static pages still need their inline bootstrap scripts. The current policy blocks inline event attributes but retains `script-src 'unsafe-inline'`. Removing that allowance needs nonce/dynamic-rendering or a validated hash strategy across all pages, including analytics and client navigation. No exploitable script-injection sink was found in the reviewed rendering paths, but this allowance weakens defense in depth.
4. **Owner account controls.** GitHub, Vercel, Supabase and the email sender's MFA/recovery settings cannot be established from the repository or the reviewed connector metadata. The owner must confirm those controls. Visitor MFA is not currently a product feature.
5. **Review limits.** No destructive/live load test, independent pentest, production account takeover attempt or new authenticated production browser session was performed. Google provider consent and opted-in reminder inbox delivery remain distinct functional checks. Listing provenance checks cannot guarantee that every external employer is honest. Security work and dependency monitoring remain ongoing.

## Maintenance

Keep `INTERNAL_PROXY_SECRET` server-only and equal in the two Production projects. Keep `SESSION_SECRET` independent of the database key. Preview testing that needs a database must use isolated test data and credentials. Adding a listing reader requires an explicit review of its HTTPS hosts in `backend/public_http.py`; do not broaden redirects or restore arbitrary URL fetching to make a publisher work.

The existing CI workflow checks dependencies and source on PRs/main and weekly. Its database job runs synthetic account race/ownership cases. The encrypted backup/isolated restore work recorded on 21–22 October remains separate from this review; no production backup was downloaded here.

## Primary references

- [OWASP Top 10:2025](https://top10.owasp.org/2025/)
- [OWASP SSRF prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP authentication](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [Supabase identity linking and unconfirmed identities](https://supabase.com/docs/guides/auth/auth-identity-linking)
- [Supabase RLS and privileged keys](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase managed pg_net privilege constraints](https://supabase.com/docs/guides/troubleshooting/revoking-access-to-pg_net-objects-has-no-effect-0bbc16)
- [Vercel request headers](https://vercel.com/docs/headers/request-headers)
- [HTTPX custom transports](https://www.python-httpx.org/advanced/transports/)
- [HTTPCore network backends](https://www.encode.io/httpcore/network-backends/)
- [Next.js security release, 14 October 2026](https://nextjs.org/blog/nextjs-security-update-october-14-2026)

Supabase's current changelog was checked. The relevant upcoming CBC TLS retirement does not require a change to this app's current Python/OpenSSL clients. The project is already on PostgreSQL 17.11; no database engine upgrade was performed in this task.
