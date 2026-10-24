# Source investigation for jobs.ac.ghana

Use this local developer workflow to investigate source readers and website regressions. Production imports continue through the existing reviewed providers and maintenance schedule. New discoveries still need eligibility, expiry, source-URL and parser review before becoming catalogue imports.

## The extracted REA subset

The owner supplied REA 6.7.0 in `rea-main.zip`. Only its dependency-free recorded-URL parser and route-segment classification were extracted into `scripts/vendor/rea/`. Its MIT license, source paths, source SHA-256 hashes and transformation record are retained there. TypeScript annotations were removed; the extracted runtime logic is unchanged. This is a small adaptation, not a deployment of the full REA engine or its advertised analysis coverage.

`scripts/source-evidence.mjs` combines that subset with project-specific offline reporting:

1. Group recorded HTTP requests by origin, method and inferred route format.
2. Find literal `fetch`, `axios` and `baseURL` candidates in saved public JavaScript.
3. Compare two network reports for newly observed routes, missing observations and changed response metadata.

The tools perform no network requests, control no browser, execute no analysed JavaScript and access no application database. They use Node.js 22 or later. Network inspection and comparison require no npm packages. JavaScript inspection uses the TypeScript parser already installed by `npm --prefix frontend ci`. No new dependency or paid service is introduced, and application code does not import these tools.

## A repeatable workflow

Use a signed-out public source page in your normal approved browser workflow. Record only the steps needed to understand its listing requests. A HAR may contain credentials or personal data; use public sessions, keep inputs outside version control and do not upload private captures into the live app. The ignored `local-source-evidence/` directory is available for local inputs and reports.

Inspect a saved capture, explicitly selecting each relevant origin:

```sh
node scripts/source-evidence.mjs network local-source-evidence/source.har \
  --origin https://source.example \
  --out local-source-evidence/before.json
```

The alternative metadata-only input format is `{ "format": "public-source-observations-v1", "observations": [...] }`. Each record has `request.method`, `request.url`, and any actually observed `response.status` and `response.content.mimeType`. Missing responses stay unknown. This permits source-preflight evidence without inventing HAR timing or payload fields.

Inspect a saved public script using the document URL that resolves relative `fetch` paths:

```sh
node scripts/source-evidence.mjs script local-source-evidence/public.js \
  --base-url https://source.example/ \
  --out local-source-evidence/script.json
```

Candidates retain source line/column coordinates. Static strings do not establish reachability, HTTP method, authentication requirements, permission to reuse data or a complete API inventory. Aliased clients and dynamic expressions require further review. No discovered endpoint is automatically requested or added to the source allowlist.

Repeat the same origin-scoped capture after a change, then compare:

```sh
node scripts/source-evidence.mjs compare \
  local-source-evidence/before.json local-source-evidence/after.json \
  --out local-source-evidence/comparison.json
```

Reports include input digests and recorded ordinals where applicable. They omit headers, bodies, query values and fragments; known variable, email and token-like path positions are masked. Remaining literal path labels and parameter names still require review before sharing. Output files use private filesystem permissions and refuse overwrite. Inputs are limited to 32 MiB / 50,000 records for captures and 4 MiB for scripts. This is not a complete HAR validator or a semantic JavaScript resolver. A missing observed request is never evidence that a vacancy closed.

## First investigation and resulting fix

The public catalogue baseline completed at `2026-10-24T22:17:15.538865+00:00`: 277 Ghana jobs, 13 early-career opportunities, 116 Ghana-eligible remote roles and 13 open funding notices. Four sources remained degraded: Ghana Current Jobs, Jobweb Ghana, Columbia Italian Academy and NYA apprenticeship. These figures describe that snapshot, not guaranteed current totals.

The local investigation made ordinary bounded public reads and saved a metadata-only request record. Both the apex and www NYA programme-information URLs returned HTTP 500. The registration portal and its 1,950,360-byte public client script returned HTTP 200. The www robots file allowed the programme URL. Static script inspection found the `/api` client base and two unresolved candidates. No registration form, applicant record or authenticated API was accessed. The overview failure remains unresolved; a reachable portal alone does not establish all eligibility and current registration conditions.

Columbia's official fellowship page returned HTTP 200 and its reader parsed locally. Review found a concrete deadline error: the header states December 4, 2026, while the application paragraph specifies 11:59 pm New York time. The old reader kept only the date and returned `2026-12-04T23:59:59+00:00`. It now preserves the explicit clock and returns `2026-12-05T04:59:00+00:00`. Tests also cover daylight saving, date-only notices, conflicting dates and exclusion of recommendation deadlines. This parser fix does not establish the cause of Columbia's separate production availability failure.

The public source status now retains bounded failure categories after the next completed production refresh: `http` with a numeric status, `timeout`, `connection`, `validation` or `reader`. Raw exception messages, URLs, headers and provider bodies are never included. Old summaries can have a null category until refreshed. Source failures remain unavailable, incomplete sources remain partial, and neither can close missing listings merely because their checks failed.

One measured run on the saved 1.95 MB NYA script completed in 0.945 seconds wall time and 1.612 seconds CPU time, with a process peak RSS of 338,944 KiB. This is a single local measurement, not a comparison with full REA or a production performance claim. Investigation captures stay local; only reviewed code and aggregate findings belong in the repository.

## Next source work

Use the next importer failure categories to distinguish provider HTTP rejection, connection/timeout and validation failure before changing a reader. Investigate Ghana Current Jobs and Jobweb failures in small page batches. Preserve confirmed Ghana eligibility, exact deadlines, per-host limits, fresh detail checks and visible incomplete-coverage status. Turn a discovered endpoint into an importer only after its public access, source ownership, pagination and eligibility have been checked. The existing scheduler then maintains that reviewed integration automatically.

Regression checks run with `npm --prefix frontend run test:security`, including the offline investigator's tests. The normal backend suite covers the importer and failure-category changes.
