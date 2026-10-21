# Audit status, updated 21 October 2026

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
| 10. Password reset | Implemented with hashed expiring single-use links and rate limits. SMTP is configured but delivery failed; Gmail HTTPS delivery remains pending. |
| 11. Email verification | Implemented; opted-in emails require a verified address. SMTP is configured but delivery failed; Gmail HTTPS delivery remains pending. |
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
| 32. Five-reminder cap | Removed; paged reconciliation and a leased 100-message worker added. Sending awaits SMTP. |
| 33. Expired queue starvation | Expiry/active-status checks precede pagination and delivery. |
| 34. Wrong date after deadline edit | Automatic reminders recompute deadline minus two days; explicit manual dates remain available. |
| 35. Premature sent flag | Durable outbox marks sent after SMTP success, retries failures and cancels obsolete/deleted reminders. SMTP cannot guarantee exactly-once delivery after every possible crash. |
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
| 47. Automated tests | GitHub backend/frontend checks added; 63 backend regressions and six frontend security tests pass locally, and live account/HTTP/SQL checks supplement CI. Interactive browser checks are not claimed. |
| 48. CV retirement | New profile reads/writes return Gone; old text can be deleted in Settings; policy/storage references updated. |
| 49. Outcome analytics | Consented fixed Apply/save/signup/login/share/search events added without private application contents. Owner confirmed Analytics access and Realtime operation on 21 October; Enhanced Measurement and detailed reporting still need review. |
| 50. Retention/revenue | Saved searches, optional alert pipeline, user-triggered sharing and sponsor information/enquiries added. No subscriptions, paid service, outreach, deal or revenue is created. |

## Verified live

A fresh scheduled run checked all 26 connected readers. Current primary inventory: 181 Ghana jobs, two early-career roles, seven Ghana-eligible remote roles and one open scholarship notice; closed/unconfirmed Scholsec notices remain in their separate views. These are a dated snapshot. Missing source salaries, levels and deadlines are still explicitly missing.

Signup/login, secure session cookie, profile access, tracker fields/history, deadline calculation, CSV formula safety, deletion/undo, saved-search ownership, logout revocation, password rotation and account deletion passed through the real frontend account proxy. The temporary account was removed, with zero leftover test profiles. No user application was submitted and no email was sent.

On 21 October, after creating a local database export that passed an archive-read check and reviewing the downtime warning, the owner completed Supabase's managed update from PostgreSQL 17.6 to build `17.11.0.003`. Post-upgrade SQL confirms PostgreSQL `17.11`, and the management API reports `ACTIVE_HEALTHY`. Catalogue/profile/application counts and three active schedules matched the pre-upgrade snapshot. All 12 application tables retained RLS and their restricted client grants. Public search and job details returned 200; guest account access remained 401. See the security review for the check scope and remaining backup limitations.

At 16:35 UTC on 21 October, the owner manually started [encrypted application backup run 39636204717](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39636204717) on main at `e58775c`. Capture, encryption, decryption/integrity verification and encrypted artifact upload all succeeded. The artifact is retained for seven days. [Run 39637711738](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39637711738) at 16:45 UTC on main `70105c8` also passed using the updated Node.js 24 actions and Ubuntu 24.04, with zero warning/error annotations. This confirms the three backup secrets and updated workflow work together; it does not establish an isolated restore or the first successful scheduled run.

The owner downloaded the second artifact, confirmed local PostgreSQL 17.11 and created the empty `zag_restore_test_20261021` database. A local-only helper and synthetic PostgreSQL restore checks are provided in this repository; restoration of the owner's actual backup remains pending. See operations for the supported application-data scope and the remaining platform, key-rotation and authenticated HTTP/UI checks.

## Still dependent on access, permission or outside systems

- Google sign-in provider configuration. SMTP is configured but delivery failed; Gmail HTTPS sender provisioning and delivery verification remain pending.
- Search ownership, sitemap reads and homepage indexing are confirmed in Google and Bing. Bing read 223 sitemap URLs on 21 October. Search ranking is not guaranteed.
- Restricted-source feeds or publisher agreements; full national/worldwide coverage is not claimed.
- An isolated restore drill and the first successful scheduled backup run. Backup secrets are configured and the first manual encrypted backup passed capture/verification/upload. The owner's local pre-upgrade export passed an archive-read check. Neither check establishes a successful disaster-recovery restore.
- Owner confirmed that the site works on a phone. The 21 October mobile PageSpeed report shows Performance 74, Accessibility 100, Best Practices 100 and SEO 100. Further speed improvements and automated browser checks remain pending.
- One pg_net placement advisory. The automatic approval review blocked its drop/recreate cleanup because it could interrupt maintenance. The protected scheduler remains working; the proposal is outside automatic migrations.

Owner setup is documented in `docs/operations.md`. The product name is not a purchased custom domain. Check hosting commercial-use terms before accepting sponsorship; no paid plan is enabled.
