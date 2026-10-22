# Audit status, updated 22 October 2026

Production: https://zagjobsearch.vercel.app. Original audit release: PR #11, commit 4dcab75. Follow-up: [security review, 21 October](security-review-2026-10-21.md). Status refers to implemented code and the checks below, not a promise that outside providers are configured or every Ghana vacancy is available.

| Finding | Result |
| --- | --- |
| 1. Job pages block indexing | Fixed: live job HTML is index, follow. |
| 2. Sitemap excludes jobs | Fixed: 191 current opportunity URLs in the checked live sitemap. |
| 3. Generic job metadata | Fixed: role/employer titles, descriptions and canonicals. |
| 4. Retired CV metadata | Removed from active job metadata. |
| 5. JavaScript-only details | Fixed: role descriptions render in initial HTML. |
| 6. JobPosting data | Added for eligible complete job descriptions and real publication dates; excluded from summary-only and scholarship pages. |
| 7. Brand/address mismatch | About/footer disclose the actual Vercel address and independent brand. A custom domain is not purchased or claimed. |
| 8. Broken Google sign-in | Backend identity validation and PKCE/state callback implemented; unavailable button hidden. Google provider credentials remain owner setup. |
| 9. Blank OAuth errors | Fixed: actual error state is rendered. |
| 10. Password reset | Hashed expiring single-use links and rate limits implemented. Owner inbox delivery, reset and subsequent login passed on 21 October; the used-link state was confirmed. Gmail authentication and fresh verification delivery passed again on 22 October after updating the sender credentials. |
| 11. Email verification | Implemented; opted-in emails require a verified address. Existing-account verification and a separate new-account signup/verification/login flow passed on 22 October. Login was blocked before verification; boolean database checks confirmed verification links were used and messages marked sent. |
| 12. Account management | Settings, password/email changes, CSV export, deletion and legacy-text removal added. Core live flows passed. Email changes require delivery. |
| 13. Repeated authentication attempts | Database-backed IP/account rate budgets added. |
| 14. Password work factor | New hashes use 600,000 PBKDF2-SHA256 iterations; legacy hashes upgrade on login. |
| 15. Copied session after logout | Fixed through server-side session versions; copied-token rejection passed live. |
| 16. Missing security headers | CSP, frame/content-type/referrer/permissions headers added and checked live. |
| 17. Broad profile grants | Client grants revoked and explicit private service-only policies added. |
| 18. External-only boards | Accurately labelled as external. LinkedIn/Jobberman and other restricted sources still need permission or a supported feed; no claim of importing them. |
| 19. Discovery windows | Added rotating older Current Jobs pages, GLMIS region/type pages and bounded checks of previously tracked records. Coverage remains bounded. |
| 20. Empty early careers | Classifier repaired and source coverage expanded; two eligible early-career listings in the latest check. Inventory is not fabricated. |
| 21. One remote role | Seven Ghana-eligible remote roles in the latest check; availability depends on publishers. |
| 22. Uneven regions | All 16 searchable, live regional counts and regional pages added. Zero current matches remains visible and honest. |
| 23. Missing deadlines | Explicit dates extracted and displayed; unknown dates remain unknown. Manual tracker deadlines are supported. |
| 24. Missing experience/jnr | Jnr recognised; explicit experience years and source skill keywords retained. Unstated seniority remains unspecified. |
| 25. Internship employment bug | Fixed: classification examines employment type as well as title. |
| 26. Salary filtering | Explicit currency/ranges/pay periods parsed; currency-aware search filters and displayed facts added. Unpublished pay is not invented. |
| 27. Summary-only descriptions | Factual summaries labelled, retained source keywords improve search, and full original requirements are linked. Restricted content is not copied wholesale. |
| 28. Application destinations | Apply checks the publisher before redirecting. Direct employer pages are preferred where supplied; agency/board destinations are labelled and cannot be replaced by invented employer links. |
| 29. Duplicates | Canonical URLs and cross-source matching improved, source provenance retained, and distinct same-source employer requisitions preserved. |
| 30. Reports/employer claims | Public issue-report form and private review queue added; source presence is not represented as an employer background check. |
| 31. Old but open employer roles | Explicitly published official employer feed entries survive the arbitrary age cutoff. Unknown old board records remain conservative. |
| 32. Five-reminder cap | Removed; paged reconciliation and a leased 100-message worker added. Gmail authentication and owner verification delivery passed on 22 October; reminder/alert inbox delivery still needs a separate check. |
| 33. Expired queue starvation | Expiry/active-status checks precede pagination and delivery. |
| 34. Wrong date after deadline edit | Automatic reminders recompute deadline minus two days; explicit manual dates remain available. |
| 35. Premature sent flag | Durable outbox marks sent after provider acceptance, retries failures and cancels obsolete/deleted reminders. Gmail failures and malformed responses never mark messages sent. Neither transport guarantees exactly-once delivery after every possible crash. |
| 36. Refresh recovery | Protected database schedule, shorter lease, bounded retry and six-hour normal refresh enabled; protected live run returned 200. |
| 37. Failure alerts | Public source health and scheduled GitHub health workflow added; failures appear in Actions. Owner notification settings control email alerts. |
| 38. Silent parser failures | Malformed sources are distinguished from empty eligible results; partial malformed details fail the source check, retry sooner and surface to monitoring. |
| 39. Unchanged-search loading | Fixed: identical filters/current tab do not enter a permanent loading state. |
| 40. Lost return filters | Job links carry the filtered return URL. |
| 41. Destructive application delete | Confirmation, soft deletion and Undo added; delete/restore passed live. |
| 42. History race | Stale history responses ignored with a request sequence. |
| 43. Submission confirmation | Correctly retained as manual: an external click cannot establish that submission occurred. Saved roles begin as Started. |
| 44. Silent result caps | Indexed database search supports pages beyond 50; tracker/export reads page beyond 500 rows. |
| 45. History lookup index | Application/event foreign-key index added; advisor no longer reports that gap. |
| 46. Unpinned backend | Exact tested Python versions pinned, with dependency compatibility checked. |
| 47. Automated tests | GitHub backend/frontend and isolated PostgreSQL restore checks supplement live HTTP and owner account checks. See the [22 October functional check](functional-check-2026-10-22.md) for the current scope and limits. An exhaustive browser or independent penetration test is not claimed. |
| 48. CV retirement | New profile reads/writes return Gone; old text can be deleted in Settings; policy/storage references updated. |
| 49. Outcome analytics | Consented fixed Apply/save/signup/login/share/search events added without private application contents. Owner confirmed Analytics access and Realtime operation on 21 October; Enhanced Measurement and detailed reporting still need review. |
| 50. Retention/revenue | Saved searches, optional alert pipeline, user-triggered sharing and sponsor information/enquiries added. No subscriptions, paid service, outreach, deal or revenue is created. |

## Verified live

A fresh scheduled run checked all 26 connected readers. Current primary inventory: 181 Ghana jobs, two early-career roles, seven Ghana-eligible remote roles and one open scholarship notice; closed/unconfirmed Scholsec notices remain in their separate views. These are a dated snapshot. Missing source salaries, levels and deadlines are still explicitly missing.

Signup/login, secure session cookie, profile access, tracker fields/history, deadline calculation, CSV formula safety, deletion/undo, saved-search ownership, logout revocation, password rotation and account deletion passed through the real frontend account proxy. The temporary account was removed, with zero leftover test profiles. No user application was submitted and no email was sent.

On 21 October, after creating a local database export that passed an archive-read check and reviewing the downtime warning, the owner completed Supabase's managed update from PostgreSQL 17.6 to build `17.11.0.003`. Post-upgrade SQL confirms PostgreSQL `17.11`, and the management API reports `ACTIVE_HEALTHY`. Catalogue/profile/application counts and three active schedules matched the pre-upgrade snapshot. All 12 application tables retained RLS and their restricted client grants. Public search and job details returned 200; guest account access remained 401. See the security review for the check scope and remaining backup limitations.

At 16:35 UTC on 21 October, the owner manually started [encrypted application backup run 39636204717](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39636204717) on main at `e58775c`. Capture, encryption, decryption/integrity verification and encrypted artifact upload all succeeded. The artifact is retained for seven days. [Run 39637711738](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39637711738) at 16:45 UTC on main `70105c8` also passed using the updated Node.js 24 actions and Ubuntu 24.04, with zero warning/error annotations. This confirms the three backup secrets and updated workflow work together. The first successful scheduled run is now confirmed: [scheduled run 39755042250](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39755042250) completed successfully on 22 October at commit `a4919bf`. GitHub started it at 09:23 UTC, later than the nominal 04:13 schedule; scheduled execution is not an exact-time guarantee.

The owner downloaded the second artifact, verified that the saved key decrypts it and confirmed saving that recovery key in a password manager. By 21:17 UTC on 21 October, the actual encrypted artifact had been restored into the isolated local PostgreSQL 17.11 database `zag_restore_test_20261021`. The terminal reported `restore_verified: true` and `snapshot_session_versions_advanced: true`, confirming the helper's transactional import and restored-value comparisons. Only aggregate results were shared; no credentials or private row values were retrieved. This completes the owner's application-data restore drill. See operations for its scope and the remaining platform, key-rotation and authenticated HTTP/UI recovery checks.

On 21 October, the owner corrected the Gmail client secret and the backend was redeployed from reviewed commit `efb144a`. The private authentication probe then returned `configured: true` and `authenticated: true`. A fresh owner-requested password-reset email reached the inbox. The owner completed the reset and logged in with the new password. A read-only database check returned booleans confirming the latest reset token was used, no reset links remained active for that account, the account email was verified and the outbox recorded the message as sent. The owner also confirmed saving the client secret and refresh token as separate password-manager entries. This verifies live account recovery. A duplicate token submission, standalone signup verification and opted-in reminder/alert delivery were not tested in this check; Google branding and visitor Google sign-in remain separate work.

Later that evening, an owner verification request failed before sending: the outbox recorded `gmail_api_authentication_failed (400)`. A fresh private authentication probe also returned HTTP 400. Production environment metadata matched the successful recovery check. The private diagnostic permits only a fixed allowlist of OAuth error codes; it excludes error descriptions, unknown strings and credential values. The later diagnostic identified `invalid_grant`; the reason the old grant became invalid remains unknown.

On 22 October, the owner obtained a fresh refresh token using their own OAuth credentials and updated the Production-only Vercel Secret. An initial redeployment returned `invalid_client`. After the owner aligned the saved client secret with the successful Playground exchange, a redeployment from reviewed commit `a4919bf` returned `configured: true` and `authenticated: true`. A fresh owner-requested verification email reached the inbox, and the owner completed verification on the site. A boolean-only database check confirmed the address was verified, the latest verification link was recently marked used, no verification links remained active for that account and the outbox recorded the message as sent. No credential or account-link values are included in this record. This checks verification for an existing owner account; new-account signup and opted-in reminder/alert inbox delivery remain separate checks.

Later on 22 October, the owner created a separate account in an Incognito window. Screenshots show successful signup, refusal to log in before verification, successful verification and the signed-in tracker. The owner confirmed successful login. A boolean-only database check confirmed the new address was verified, its latest verification link was recently used, no verification links remained active and the outbox marked its verification email sent. This completes the new-account signup/verification/login check; reminder/alert delivery and duplicate token submission remain separate checks.

## Still dependent on access, permission or outside systems

- Opted-in reminder/alert inbox checks and duplicate token submission. Gmail authentication, existing-account verification and a separate new-account signup/verification/login flow passed on 22 October. Future sender changes require fresh authentication and inbox checks.
- Google sign-in provider configuration and Google branding verification. Sender consent does not establish public app approval.
- Search ownership, sitemap reads and homepage indexing are confirmed in Google and Bing. Bing read 223 sitemap URLs on 21 October. Search ranking is not guaranteed.
- Restricted-source feeds or publisher agreements; full national/worldwide coverage is not claimed.
- A full platform recovery drill. The first scheduled encrypted backup passed on 22 October. Manual encrypted capture/verification/upload and an isolated restore of the owner's actual application-data artifact passed. The separate pre-upgrade PostgreSQL export has passed only an archive-read check; its restore, provider configuration and authenticated HTTP/UI recovery remain unverified.
- Owner confirmed that the site works on a phone. The 21 October mobile PageSpeed report shows Performance 74, Accessibility 100, Best Practices 100 and SEO 100. Further speed improvements and automated browser checks remain pending.
- One pg_net placement advisory. The automatic approval review blocked its drop/recreate cleanup because it could interrupt maintenance. The protected scheduler remains working; the proposal is outside automatic migrations.

Owner setup is documented in `docs/operations.md`. The product name is not a purchased custom domain. Check hosting commercial-use terms before accepting sponsorship; no paid plan is enabled.
