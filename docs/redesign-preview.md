# ZagJobSearch redesign preview

This branch replaces the interface with solid white surfaces, lavender and mint sections, charcoal controls, and a scalable Z logo. Search, signup and login keep using the existing FastAPI backend. Apply prompts visitors to log in and then opens the external source. The existing local profile is a UI gate, not authenticated server authorization. Application tracking still needs server sessions and a database migration before it can safely be implemented.

## Job discovery

- Himalayas supplies remote listings and now retains string country restrictions, salary units and expiry dates.
- Adzuna is optional when keys are missing, and South Africa is included in its supported countries.
- The frontend adds a Jobicy route. It retrieves a common feed of up to 200 recent jobs through Next's persistent Data Cache, with hourly revalidation, then filters and pages locally. Jobicy attribution and public source URLs are preserved. This is a limited recent feed, not an archive of all vacancies. Check geography on the posting; unknown eligibility is not treated as worldwide.
- Sources fail independently and available results remain visible. Results are deduplicated by company, role and location, following the source-by-source discovery and stable job identity patterns reviewed in [ai-job-search](https://github.com/MadsLorentzen/ai-job-search). Its Danish workflow is not embedded or run as a global scraper. [career-ops](https://github.com/career-ops-hq/career-ops) is also a local workflow rather than a hosted universal jobs API. The supplied FreeLLMAPI project routes AI model requests; it supplies no job data. No third-party repository code has been copied.

Provider documentation: [Himalayas](https://himalayas.app/api), [Jobicy](https://jobicy.com/jobs-rss-feed), [Adzuna](https://developer.adzuna.com/).

## Deployment and Google

Keep `NEXT_PUBLIC_API_URL` set to the deployed API. Set `NEXT_PUBLIC_SITE_URL=https://zagjobsearch.vercel.app`. Add the Google Search Console HTML-tag token as `GOOGLE_SITE_VERIFICATION` and redeploy. Verify ownership, submit `/sitemap.xml`, and request indexing of the homepage. Metadata, canonical URL, WebSite structured data, icon, social image, robots and sitemap are included. Search and account pages are excluded from indexing. Google decides whether and when to index a page.

Merge only after preview review. Backend fixes also need the API project's deployment. The Vercel connector returned a team-scope 403 during inspection; reconnect it to the team owning zagjobsearch to inspect deployments.

## Validation

Frontend production build, TypeScript and ESLint. Backend regression fixtures: `cd backend && python -m unittest discover -s tests` after installing requirements. Browser checks are recorded in the PR when available.
