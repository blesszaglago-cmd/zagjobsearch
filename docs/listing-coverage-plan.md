# Ghana listing coverage, 22 October 2026

The priority is current, usable Ghana vacancies before adding conversational matching. The assistant discussed with the owner is typed conversation; it is outside this release.

## Measured baseline

The live catalogue refresh completed at 21:16 UTC on 22 October. It returned 215 regular jobs, two early-career roles, seven Ghana-eligible remote roles and one open scholarship notice. All 26 connected readers reported successful checks; 18 returned at least one record, including scholarship notices. A successful empty feed is not the same as a broken reader.

Nine regions had no current mapped listings. Among the 224 non-scholarship opportunities, 115 lacked a closing date, 128 lacked a stated seniority label and 219 lacked a salary range. Missing source information stays unknown. A regional zero measures this catalogue's coverage, not the absence of jobs in that region.

Ghana Current Jobs, GLMIS, HIREghana and a limited set of employer boards provide current imports. LinkedIn, Jobberman, JobsInGhana and several other boards remain external destinations. Linking a board does not import its jobs.

## First employer expansion

- M-KOPA: its official career page links to its Ashby board. The documented public posting API returned ten Ghana-eligible roles in the source check: eight regular jobs and two remote roles. Primary and secondary work locations are checked. Explicit role titles also identify Ho, Aflao, Hohoe and Dambai.
- Fido: five Ghana-eligible vacancies on the official careers index passed the live reader, including two national-service roles. All retained their original detail links and individual application links.
- A read-only baseline query found no existing active catalogue records for these employers. These are source-check counts, not a promise of a permanent net increase. The deployed refresh and public search must establish the actual resulting totals after freshness and duplicate checks.
- Both readers use existing scheduled refreshes, source monitoring and removal checks before Apply. Source unavailability does not falsely establish that all its jobs closed. Hybrid work is not labelled fully remote; `FTC` titles classify as contracts.

References: [M-KOPA careers](https://www.m-kopa.com/careers), [Ashby public posting API](https://developers.ashbyhq.com/docs/public-job-posting-api), [Fido careers](https://gh.fido.money/careers).

## Next priorities

1. Expand direct employers by sector and by the regions with no matches. Audit healthcare, schools/universities, manufacturing, banks, mining and regional sales/field employers. Each addition needs live vacancies, an accessible public feed or allowed public pages, reliable location evidence and a tested closure path. mPharma's official job board is connected by the subsequent academic/vacancy expansion.
2. Add NGO opportunities through a supported feed. ReliefWeb documents a public jobs API, but every request requires an approved appname. Request that identifier before connecting; do not borrow another application's identifier. No application request was submitted during this review. [Official API documentation](https://apidoc.reliefweb.int/).
3. Jobweb Ghana is now connected using bounded public RSS/index discovery and readable vacancy evidence. Its public pages were accessible during this review, unlike the earlier audit. One inspected Tumu advert had structured Accra location and salary/expiry fields not established by its readable text. Do not blindly copy those fields, bypass access controls or infer completeness from the discovery window.
4. Seek supported feeds or reuse permission for the larger boards. Jobberman requires approval for automated extraction. LinkedIn's search totals are not this site's inventory and are not a verified count of distinct current Ghana vacancies. No publisher outreach or scraping of restricted sources was performed.
5. Consider employer-submitted vacancy URLs with source/ownership checks, expiry handling and a review queue for ambiguous reports. This would require a separate product change.

## Acceptance criteria for further additions

Track newly added unique vacancies, region/sector coverage, early-career coverage, source-check success, closure handling and the proportion of usable application links. Record discovered and rejected counts when extending readers so parser loss can be distinguished from genuinely empty sources. Count separate vacancy postings rather than unverified numbers of available seats.

Keep sources attributed, use employer destinations where supplied, preserve application history after a vacancy closes and show missing salary/deadline/experience facts honestly. Review ambiguous or conflicting source metadata. Do not set an arbitrary inventory target that encourages expired, duplicated or foreign vacancies.

The first batch's local checks cover Ghana eligibility in secondary addresses, foreign/unlisted exclusions, explicit work-town mapping, hybrid/remote distinction, contract classification, trusted application URLs, malformed feed handling and removal checks. Full backend and release CI checks supplement the live source-reader probes. No account data, credentials or email are part of this source expansion.

## Academic and vacancy expansion

The follow-up release connects DAAD-funded Ghana-origin programmes, University of Ghana RID calls, carefully filtered KNUST OGR calls, mPharma, ALX Africa and Jobweb Ghana. The live preflight found 18 DAAD programme notices (only three with a confirmed current application window), two distinct open UG research calls and a rolling KNUST/J-PAL research call. These are source-check counts, not a claim of complete internet coverage. Many annual programmes are genuinely closed or lack a confirmed current deadline. All 14 ScholSec notices already existed in the catalogue and remain accessible by source and status.

University reposts can conflict with funder deadlines. Prefer the primary provider and retain institutional nomination, residency, collaborator and qualification requirements. The DigiFI rolling window is checked against J-PAL itself. Unfunded visiting stays and restricted foreign-only opportunities do not inflate open scholarship counts. Maintain the $0 budget and automatic six-hour refresh cycle; no CV/chat assistant is included. Production inventory and external redirects must be checked after the schema/function update and matched frontend/backend deployments.
