# Functional check, 22 October 2026

The owner reported that another visitor could not sign up. The visitor's exact
error and reproduction steps were unavailable. That specific failure has not been
reproduced or attributed to a cause. These checks cover observed behavior, not a
guarantee that every browser, account and outside provider works.

## Live checks before the change

The public frontend and API were checked at release `51c2b99`:

- Home, signup, login, recovery, search, internship, scholarship, remote, sources
  and guest tracker pages returned 200.
- Guest session checks correctly reported signed out. Private profile,
  application, settings and saved-search reads returned 401.
- Six invalid signup variants returned 422 without echoing test passwords:
  short password, mismatched confirmation, invalid email, missing age confirmation,
  missing terms acceptance and short name. Unknown-account login returned 401.
- Cross-origin signup was correctly blocked with 403, but that early response
  lacked explicit `Cache-Control: no-store`. This was the only failed assertion
  in the 23-check HTTP matrix; it was not an authentication bypass or an observed
  signup outage.
- Four category APIs returned structured opportunities in their own categories.
  Searching an existing title found its listing; the detail API matched it.
  One current Apply endpoint rechecked its publisher and returned an external
  HTTPS redirect. The check stopped at the redirect without submitting anything.
- The health script passed catalogue freshness, connected-source health, current
  job HTML, canonical metadata, sitemap and robots checks.
- A private no-send Gmail authentication probe passed. Recent delivery metadata
  showed no delivery failure. This does not establish delivery to every inbox.

The owner's separate signup, verification and login passed earlier the same day.
This audit created no accounts and sent no email. Authenticated tracker edits
were not repeated with another person's account.

## Changes and validation

Code review found a partial-success problem: an account was inserted before its
verification email was sent. An email failure could report signup failure even
though the account existed. Signup now acknowledges the created account and
explains how to request a fresh verification link if delivery is uncertain.
Verification remains required and signup does not issue a session. Diagnostics
record a fixed failure category without provider replies or account secrets.

Signup now includes the recovery link and a visible eight-character password
hint. All responses returned by the account proxy explicitly use `no-store`,
including early errors and redirects. Origin and session checks remain enforced.

The fresh release security job flagged Next.js 16.3.8 against three advisories
added to the GitHub Advisory Database on 22 October: GHSA-2464-fhr4-w9xw,
GHSA-p3m5-59mp-jv5r and GHSA-673q-mjm6-r5xr. The installed version is in their
affected ranges; this is not evidence of an actual exploit or the reported
visitor's signup failure. Next.js and its matching ESLint configuration are now
pinned to 16.4.2, with a regenerated lockfile. The maintainer's
[16.4.1 security release](https://github.com/vercel/next.js/releases/tag/v16.4.1)
contains the fixes; [16.4.2](https://github.com/vercel/next.js/releases/tag/v16.4.2)
includes that release's fixes and subsequent maintenance changes.
The runtime dependency audit then returned zero known vulnerabilities.

Seven frontend security regressions passed locally, including upstream failure
privacy and early-response cache assertions. ESLint completed with zero errors
and five existing navigation warnings. The webpack production build and TypeScript
checks passed. Changed Python files passed syntax parsing. The local Python
environment lacks the full backend test dependencies. Backend CI ran 94 tests
with four skipped, including the four added signup regressions; the isolated
PostgreSQL restore job ran 14 successfully. These overlapping batches are not
added together as unique tests. The final release PR's backend, frontend,
dependency audit and isolated restore checks must all pass before merging.

## Remaining limits

The reported visitor's exact signup failure remains unconfirmed. Vercel runtime
error traces could not be retrieved through the current connection. Visitor
Google sign-in is still disabled. Opted-in reminder/alert inbox delivery and
verification-token replay need separate checks. This is a functional regression
check, not an independent penetration test or full platform recovery drill.

The first scheduled encrypted application backup is now confirmed successful:
[run 39755042250](https://github.com/blesszaglago-cmd/zagjobsearch/actions/runs/39755042250).
Its success is separate from the previously completed local application-data
restore and does not establish full Supabase platform recoverability.
