# Audit status — 20 October 2026

Production: https://zagjobsearch.vercel.app. Main release: PR #11, commit 4dcab75. Status refers to implemented code and the checks below, not a promise that outside providers are configured or every Ghana vacancy is available.

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
| 10. Password reset | Implemented with hashed expiring single-use links and rate limits. Production delivery awaits SMTP configuration. |
| 11. Email verification | Implemented; opted-in emails require a verified address. Production delivery awaits SMTP. |
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
| 47. Automated tests | GitHub backend/frontend checks added; 47 regressions pass locally, and live account/HTTP/SQL checks supplement CI. Interactive browser checks are not claimed. |
| 48. CV retirement | New profile reads/writes return Gone; old text can be deleted in Settings; policy/storage references updated. |
| 49. Outcome analytics | Consented fixed Apply/save/signup/login/share/search events added without private application contents. Analytics account reporting and Enhanced Measurement settings still need owner verification. |
| 50. Retention/revenue | Saved searches, optional alert pipeline, user-triggered sharing and sponsor information/enquiries added. No subscriptions, paid service, outreach, deal or revenue is created. |

## Verified live

A fresh scheduled run checked all 26 connected readers. Current primary inventory: 181 Ghana jobs, two early-career roles, seven Ghana-eligible remote roles and one open scholarship notice; closed/unconfirmed Scholsec notices remain in their separate views. These are a dated snapshot. Missing source salaries, levels and deadlines are still explicitly missing.

Signup/login, secure session cookie, profile access, tracker fields/history, deadline calculation, CSV formula safety, deletion/undo, saved-search ownership, logout revocation, password rotation and account deletion passed through the real frontend account proxy. The temporary account was removed, with zero leftover test profiles. No user application was submitted and no email was sent.

## Still dependent on access, permission or outside systems

- Google OAuth provider configuration and backend SMTP credentials; currently disabled.
- Search Console/Bing authenticated ownership, sitemap submission and indexing reports; website-side tags and crawl fixes are deployed.
- Restricted-source feeds or publisher agreements; full national/worldwide coverage is not claimed.
- Backup repository secrets and an isolated restore drill. Encryption/integrity tests are not a disaster-recovery test.
- Interactive mobile/accessibility verification. PageSpeed API returned a shared-quota 429, so no score is claimed.
- One pg_net placement advisory. The automatic approval review blocked its drop/recreate cleanup because it could interrupt maintenance. The protected scheduler remains working; the proposal is outside automatic migrations.

Owner setup is documented in `docs/operations.md`. The product name is not a purchased custom domain. Check hosting commercial-use terms before accepting sponsorship; no paid plan is enabled.
