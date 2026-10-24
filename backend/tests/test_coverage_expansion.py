"""Ghana eligibility, actual application windows and individual-role regressions."""

import json
import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

import catalogue as c
import early_career_sources as early
import funding_sources as funds
import marriott_source as marriott
import ghana_sources as ghana
import jobweb_source as jobweb
import workspace_api as workspace
from listing_quality import identity

NOW = datetime(2026, 10, 23, 17, tzinfo=timezone.utc)


def soup(value):
    return BeautifulSoup(value, "html.parser")


def gh_row(board="wikimedia", location="Remote", body=None, title="Engineer"):
    return {
        "id": 1234,
        "title": title,
        "location": {"name": location},
        "content": body
        or "<p>Develop software and work with an international team. Requirements and individual application instructions are supplied by the employer.</p><p>Countries: Brazil, Ghana, Germany and the United Kingdom.</p>",
        "absolute_url": f"https://job-boards.greenhouse.io/{board}/jobs/1234",
        "updated_at": "2026-10-22T12:00:00Z",
    }


class CoverageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = patch.object(c, "NOW", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_wikimedia_requires_role_hiring_list_not_just_remote(self):
        self.assertEqual(
            c.parse_greenhouse(gh_row(), "wikimedia")["category"], "remote"
        )
        self.assertIsNone(
            c.parse_greenhouse(
                gh_row(body="<p>A remote job, available to US applicants only.</p>"),
                "wikimedia",
            )
        )
        self.assertIsNone(
            c.parse_greenhouse(gh_row(location="Remote (US)"), "wikimedia")
        )

    def test_us_internship_is_excluded_even_with_global_company_boilerplate(self):
        row = gh_row(
            title="Software Engineering Internship",
            body="<p>Location: Remote (US)*</p><p>Countries: Ghana, Germany, United States.</p>",
        )
        self.assertIsNone(c.parse_greenhouse(row, "wikimedia"))

    def test_givedirectly_requires_the_roles_hiring_country_statement(self):
        row = gh_row(
            "givedirectly",
            body="<p>We work with many communities in Ghana. Our headquarters are elsewhere.</p>",
        )
        self.assertIsNone(c.parse_greenhouse(row, "givedirectly"))
        row["content"] = (
            "<p>Build reliable software for our international operations and work with colleagues across time zones.</p><p>Location: At this stage we are prioritizing hiring in the countries below, through an employer of record: Canada, Ghana, Kenya.</p>"
        )
        self.assertIsNotNone(c.parse_greenhouse(row, "givedirectly"))

    def test_canonical_worldwide_is_distinct_from_foreign_or_ambiguous_regions(self):
        row = gh_row("canonical", "Home based - Worldwide", title="Graduate Engineer")
        self.assertEqual(c.parse_greenhouse(row, "canonical")["category"], "remote")
        self.assertEqual(c.parse_greenhouse(row, "canonical")["job_type"], "graduate")
        row["location"]["name"] = "Home based - EMEA"
        self.assertIsNone(c.parse_greenhouse(row, "canonical"))
        row["location"]["name"] = "Home based - Worldwide"
        row["title"] = "Field Engineering Manager (Americas)"
        self.assertIsNone(c.parse_greenhouse(row, "canonical"))
        row["title"] = "Engineer"
        row["content"] = (
            "Location: This position is in APAC only. Work with engineering colleagues and support the team."
        )
        self.assertIsNone(c.parse_greenhouse(row, "canonical"))

    def test_foreign_pay_examples_do_not_become_ghana_salary(self):
        row = gh_row(
            body="<p>US applicants: $100,000 to $120,000 per year.</p><p>Work with the international development team. Countries: Ghana, Germany.</p>"
        )
        job = c.parse_greenhouse(row, "wikimedia")
        self.assertIsNone(job["salary_min"])
        self.assertIsNone(job["salary_currency"])
        self.assertEqual(job["date_kind"], "source_updated")

    def test_employer_feed_cannot_replace_application_host(self):
        row = gh_row()
        row["absolute_url"] = "https://unrelated.example/jobs/1234"
        with self.assertRaises(ValueError):
            c.parse_greenhouse(row, "wikimedia")

    async def test_apply_rechecks_employer_country_eligibility(self):
        job = c.parse_greenhouse(gh_row(), "wikimedia")
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": job["id"],
                "payload": job,
                "status": "active",
                "deadline": None,
                "last_checked_at": NOW.isoformat(),
                "first_seen_at": NOW.isoformat(),
            }
        ]
        changed = gh_row()
        changed["content"] = "<p>Countries: Germany, United States.</p>"
        response = httpx.Response(
            200, json=changed, request=httpx.Request("GET", job["check_url"])
        )
        client = AsyncMock()
        client.get.return_value = response
        with patch.object(c, "supabase", db), patch.object(
            c, "source_client"
        ) as factory, patch.object(
            c, "PublicSourceClient", side_effect=lambda client: client
        ):
            factory.return_value.__aenter__.return_value = client
            with self.assertRaises(HTTPException) as error:
                await c.catalogue_details(job["id"], verify=True)
        self.assertEqual(error.exception.status_code, 410)
        db.table.return_value.update.assert_called_with({"status": "closed"})

    def test_lincoln_older_closed_intake_does_not_close_next_intake(self):
        body = soup(
            """<h1>Global Leaders Scholarship</h1><p>Available to international students: 50% of tuition fees. You must already have an offer for an undergraduate or postgraduate taught programme.</p><p>Applications for January 2027 are now closed.</p><p>For a programme of study commencing in September 2027: Monday 7 June 2027</p><p>For a programme of study commencing in January 2028: Monday 18 October 2027</p>"""
        )
        job = funds.parse_call(body, "lincoln-global-leaders")
        self.assertTrue(job["can_apply"])
        self.assertEqual(job["deadline"][:10], "2027-06-07")
        self.assertEqual(job["study_levels"], ["undergraduate", "masters"])
        self.assertEqual(job["funding"], "partial")
        self.assertEqual(
            job["source_urls"][0], funds.CALLS["lincoln-global-leaders"]["url"]
        )

    def test_loeb_exact_pm_clock_and_application_not_recommendation_deadline(self):
        body = soup(
            "<p>International candidates are encouraged to apply, with a minimum of 8 years experience. Applications for the 2027-28 Fellowship year are now open.</p><p>Recommendations due January 12, 2027 at 11:59PM ET.</p><p>Apply for the Loeb Fellowship, due January 5,2027 at 11:59PM ET.</p>"
        )
        job = funds.parse_call(body, "harvard-loeb")
        self.assertEqual(job["deadline"], "2027-01-06T04:59:00+00:00")
        self.assertEqual(job["study_levels"], [])

    def test_bodleian_explicit_5pm_is_preserved(self):
        body = soup(
            "Applications are open for Visiting Fellowships. Applications are welcome from both academically affiliated and independent scholars. Sub-Saharan Africa scholars can apply. Awards up to £2,200 per month. The deadline is 27 November 2026, 5pm (GMT)."
        )
        self.assertEqual(
            funds.parse_call(body, "bodleian-visiting")["deadline"],
            "2026-11-27T17:00:00+00:00",
        )

    def test_columbia_uses_the_exact_new_york_application_clock(self):
        body = soup(
            "Candidates of any nationality are invited to apply. Each application includes a copy of the PhD degree. Fellows receive a full-time salary. "
            "DEADLINE: Friday, December 4, 2026. "
            "The application deadline is Friday, December 4, 2026 (11:59 pm, New York time). "
            "The deadline for recommendation letters is December 14."
        )
        job = funds.parse_call(body, "columbia-italian-academy")
        self.assertEqual(job["deadline"], "2026-12-05T04:59:00+00:00")
        self.assertIn("11:59 pm New York time", job["deadline_note"])
        self.assertNotIn("without an exact time", job["deadline_note"])

    def test_columbia_clock_uses_daylight_saving_for_the_provider_date(self):
        self.assertEqual(
            funds.deadline_text(
                "columbia-italian-academy",
                "DEADLINE: June 4, 2027. The application deadline is June 4, 2027 (11:59 pm, New York time).",
            ),
            ["June 4, 2027 11:59 pm New York time"],
        )
        body = soup(
            "Candidates of any nationality are invited to apply. Each application includes a copy of the PhD degree. Fellows receive a full-time salary. "
            "DEADLINE: June 4, 2027. The application deadline is June 4, 2027 (11:59 pm, New York time)."
        )
        self.assertEqual(
            funds.parse_call(body, "columbia-italian-academy")["deadline"],
            "2027-06-05T03:59:00+00:00",
        )

    def test_columbia_date_only_notice_does_not_invent_an_exact_clock(self):
        body = soup(
            "Candidates of any nationality are invited to apply. Each application includes a copy of the PhD degree. Fellows receive a full-time salary. DEADLINE: December 4, 2026."
        )
        job = funds.parse_call(body, "columbia-italian-academy")
        self.assertIn("without an exact time", job["deadline_note"])

    def test_columbia_conflicting_provider_dates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "deadlines conflict"):
            funds.deadline_text(
                "columbia-italian-academy",
                "DEADLINE: December 4, 2026. The application deadline is December 5, 2026 (11:59 pm, New York time).",
            )

    def test_unesco_prior_master_qualification_is_not_a_masters_scholarship(self):
        body = soup(
            "Applications are now open for the SCRS Research Continuity Grants. African nationals based at a recognized university can apply. Applications are welcome from all African countries. Research must have been interrupted by an armed conflict or natural or biological hazard. Applicants need a master's degree. Application deadline: 15 November 2026, 23:59 Paris time."
        )
        job = funds.parse_call(body, "unesco-research-continuity")
        self.assertEqual(job["deadline"], "2026-11-15T22:59:00+00:00")
        self.assertEqual(job["job_type"], "research-grant")
        self.assertEqual(job["study_levels"], [])

    def test_lse_funding_deadline_precedes_later_admission_deadline(self):
        body = soup(
            "Overseas full-time students Open. We offer scholarships to help both home and overseas students. Admission deadline: 27 May 2027. Deadline for the LSE PhD Studentships and ESRC funding: 13 January 2027"
        )
        job = funds.parse_call(body, "lse-demography-funding")
        self.assertEqual(job["deadline"][:10], "2027-01-13")
        self.assertEqual(job["study_levels"], ["mphil", "phd"])

    def test_unsupported_eligibility_or_deadline_is_not_marked_open(self):
        for text in [
            "International scholarship for 2027",
            "Available to domestic students only. Application deadline: 5 December 2026",
        ]:
            with self.assertRaises(ValueError):
                funds.parse_call(soup(text), "lincoln-global-leaders")

    def test_provider_recheck_rejects_a_redirected_or_substituted_url(self):
        key = "ucl-hp-ai-education"
        job = {"source_key": key, "check_url": funds.CALLS[key]["url"]}
        response = httpx.Response(
            200, text="", request=httpx.Request("GET", "https://unrelated.example/call")
        )
        with self.assertRaises(ValueError):
            funds.recheck(job, response)

    def test_provider_closure_overrides_future_deadline(self):
        body = soup(
            "International candidates are encouraged to apply, with a minimum of 8 years experience. Applications are now closed. Loeb Fellowship, due January 5,2027 at 11:59PM ET."
        )
        job = funds.parse_call(body, "harvard-loeb")
        self.assertEqual(job["listing_status"], "closed")
        self.assertFalse(job["can_apply"])

    def test_individual_votex_roles_keep_distinct_ids_and_source_sections(self):
        index = soup(
            '<main><a href="/internships#operations"><h2>Operations Interns</h2>Ghana Internship</a></main>'
        )
        detail = soup(
            '<main>Now Hiring<section id="operations"><article><h3>Personal Assistant</h3><p>Organise calendars and support business operations.</p><a href="mailto:recruit@example.test">Apply</a></article><article><h3>Data Entry Intern</h3><p>Maintain records and prepare spreadsheets.</p><a href="mailto:recruit@example.test">Apply</a></article></section></main>'
        )
        jobs = early.parse_votex(index, detail)
        self.assertEqual(len(jobs), 2)
        self.assertNotEqual(jobs[0]["id"], jobs[1]["id"])
        self.assertEqual({j["category"] for j in jobs}, {"early"})
        self.assertEqual(
            {j["url"] for j in jobs}, {early.VOTEX + "/internships#operations"}
        )
        self.assertIsNone(jobs[0]["created"])

    def test_votex_missing_location_and_incomplete_details_fail_closed(self):
        with self.assertRaises(ValueError):
            early.votex_groups(
                soup(
                    '<main><a href="/internships#operations"><h2>Interns</h2>Anywhere</a></main>'
                )
            )
        with self.assertRaises(ValueError):
            early.parse_votex(
                soup(
                    '<main><a href="/internships#operations"><h2>Interns</h2>Ghana</a></main>'
                ),
                soup("<main>Now Hiring</main>"),
            )
        self.assertEqual(
            early.parse_votex(
                soup("<main>No open roles</main>"), soup("<main>No open roles</main>")
            ),
            [],
        )

    def test_university_index_expiry_and_future_dates_are_not_current(self):
        for posted, count in [("2026-10-20", 1), ("2026-10-01", 0), ("2026-11-01", 0)]:
            index = soup(
                f'<div class="views-row"><div class="views-field-title"><a href="/careers/announcements/internship-opportunity">Internship</a></div><div class="views-field-created"><time datetime="{posted}"></time></div></div>'
            )
            self.assertEqual(len(early.ug_cards(index)), count)

    def test_university_header_body_and_events_are_not_vacancy_details(self):
        detail = soup(
            '<div class="field--name-body">University of Ghana</div><main><div class="field--name-body"><p>TVS Motor Company is hiring Data &amp; AI Engineering Interns in Accra, Ghana.</p><p>Students and recent graduates with Python, SQL and data skills can apply for this six month internship through the employer contacts in the announcement.</p></div></main>'
        )
        job = early.parse_ug(
            detail, early.UG + "/careers/announcements/internship-opportunity", NOW
        )
        self.assertEqual(job["company"], "TVS Motor Company")
        self.assertEqual(job["title"], "Data & AI Engineering Interns")
        self.assertEqual(job["regions"], ["Greater Accra"])
        self.assertIsNone(
            early.parse_ug(
                soup(
                    '<main><div class="field--name-body"><p>Join our career day and request an internship letter.</p></div></main>'
                ),
                "unused",
                NOW,
            )
        )

    def test_national_apprenticeship_is_training_registration_not_a_paid_job(self):
        overview = soup(
            '<a href="https://www.nap.nya.gov.gh/">Apply online</a><p>Must be a Ghanaian citizen, between 15 and 40 years. No minimum academic qualification. You must be a resident in the community, district, or region.</p>'
        )
        landing = soup('<script src="/assets/index-example.js"></script>')
        asset = 'kicker:"Applications are open", route:"/apply/apprentice"'
        job = early.parse_nap(overview, landing, asset)
        self.assertEqual(job["job_type"], "apprenticeship")
        self.assertEqual(len(job["regions"]), 16)
        self.assertIsNone(job.get("salary_min"))
        self.assertIn("does not guarantee", job["description"])
        with self.assertRaises(ValueError):
            early.parse_nap(
                overview,
                landing,
                asset.replace("Applications are open", "Applications are closed"),
            )

    async def test_portal_asset_cannot_redirect_outside_official_host(self):
        client = AsyncMock()
        client.get.return_value = httpx.Response(
            200,
            text="",
            request=httpx.Request("GET", "https://unrelated.example/code.js"),
        )
        with patch.object(
            early,
            "page",
            AsyncMock(
                side_effect=[
                    soup("<p>Overview</p>"),
                    soup('<script src="/assets/index-example.js"></script>'),
                ]
            ),
        ):
            with self.assertRaises(ValueError):
                await early.nap(client)

    def marriott_detail(self, country="GH"):
        url = marriott.BASE + "/engineer/job/P1-1234-0"
        data = {
            "@type": "JobPosting",
            "url": url,
            "identifier": {"value": "P1-1234-0"},
            "title": "Maintenance Engineer",
            "description": "Maintain and repair hotel equipment, follow safety procedures and support the facilities team with documented maintenance and guest service.",
            "datePosted": "2026-10-20",
            "employmentType": ["FULL_TIME"],
            "jobLocation": [
                {"address": {"addressCountry": country, "addressLocality": "Accra"}}
            ],
        }
        return url, soup(
            '<script type="application/ld+json">' + json.dumps(data) + "</script>"
        )

    def test_marriott_schema_must_confirm_ghana_and_individual_identity(self):
        url, detail = self.marriott_detail()
        job = marriott.parse_detail(detail, url)
        self.assertEqual(job["category"], "jobs")
        self.assertEqual(job["job_type"], "full-time")
        self.assertEqual(job["regions"], ["Greater Accra"])
        foreign_url, foreign = self.marriott_detail("KE")
        self.assertIsNone(marriott.parse_detail(foreign, foreign_url))
        with self.assertRaises(ValueError):
            marriott.parse_detail(detail, url.replace("1234", "5678"))

    async def test_marriott_pagination_preserves_country_filter_and_requires_all_results(
        self,
    ):
        first = soup(
            "<main>Showing 1 - 10 of 11 jobs"
            + "".join(f'<a href="/role/job/P1-{n}-0">Role</a>' for n in range(1, 11))
            + "</main>"
        )
        last = soup(
            '<main>Showing 11 - 11 of 11 jobs<a href="/role/job/P1-11-0">Role</a></main>'
        )
        with patch.object(
            marriott, "page", AsyncMock(side_effect=[first, last])
        ) as read:
            self.assertEqual(len(await marriott.index_links(None)), 11)
        self.assertIn(marriott.COUNTRY_FILTER, read.call_args_list[1].args[1])
        with patch.object(marriott, "page", AsyncMock(side_effect=[first, first])):
            with self.assertRaises(ValueError):
                await marriott.index_links(None)
        with self.assertRaises(ValueError):
            marriott.parse_index(soup("<main>Showing 1 - 10 of 14601 jobs</main>"))

    async def test_marriott_removed_index_entry_cannot_be_applied_to(self):
        url, detail = self.marriott_detail()
        job = marriott.parse_detail(detail, url)
        response = httpx.Response(
            200, text=str(detail), request=httpx.Request("GET", url)
        )
        with patch.object(marriott, "index_links", AsyncMock(return_value=set())):
            self.assertIsNone(await marriott.recheck(None, job, response))

    def test_marriott_board_reposts_share_employer_identity(self):
        url, detail = self.marriott_detail()
        job = marriott.parse_detail(detail, url)
        self.assertEqual(
            identity(job), identity({**job, "company": "Accra Marriott Hotel"})
        )

    async def test_bounded_batches_preserve_completed_results_and_cancel_pending_work(
        self,
    ):
        import asyncio

        cancelled = asyncio.Event()

        async def stalled():
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def completed():
            return "confirmed"

        result = await ghana.checked_batch([completed(), stalled()], timeout=0.01)
        self.assertEqual(result[0], "confirmed")
        self.assertIsInstance(result[1], TimeoutError)
        self.assertTrue(cancelled.is_set())

    async def test_partial_refresh_only_stamps_verified_rows_and_cannot_close_missing_rows(
        self,
    ):
        job = c.parse_greenhouse(gh_row(), "wikimedia")
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = True
        with patch.object(c, "supabase", db), patch.object(
            c, "refresh_state", return_value={"archive_page": 9}
        ), patch.object(
            c,
            "catalogue_rows",
            side_effect=[
                [],
                [{"id": "not-rechecked", "source_key": "synthetic-source"}],
            ],
        ), patch.object(
            c,
            "collect",
            AsyncMock(
                return_value=[
                    ("synthetic-source", ghana.CheckedListings([job], failed_checks=1))
                ]
            ),
        ):
            result = await c.refresh()
        self.assertEqual(result["sources"][0]["state"], "partial")
        self.assertEqual(result["sources"][0]["accepted"], 1)
        records = db.table.return_value.upsert.call_args.args[0]
        self.assertEqual([record["id"] for record in records], [job["id"]])
        self.assertEqual(records[0]["last_checked_at"], NOW.isoformat())
        self.assertFalse(db.table.return_value.update.return_value.in_.called)
        update = db.table.return_value.update.call_args.args[0]
        self.assertIsNotNone(update["last_error"])
        self.assertEqual(update["next_refresh_at"], "2026-10-23T17:30:00+00:00")

    async def test_failed_jobweb_detail_cannot_be_replaced_by_a_feed_only_record(self):
        index = soup(
            '<ol class="jobs"><a href="/jobs/first-role/">First</a><a href="/jobs/second-role/">Second</a></ol>'
        )
        body = "<p>Location: Accra, Ghana</p><p>Support office operations, communicate with colleagues and maintain accurate records for the local team.</p><p>Closing Date: 30 October 2026</p>"
        feed = (
            '<rss xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><item><title>First Officer at Example</title><link>https://jobwebghana.com/jobs/first-role/</link><pubDate>23 October 2026</pubDate><content:encoded><![CDATA['
            + body
            + "]]></content:encoded></item></channel></rss>"
        )
        client = AsyncMock()
        client.get.return_value = httpx.Response(
            200, text=feed, request=httpx.Request("GET", jobweb.BASE + "/feed/")
        )

        async def read(client, url):
            if url.endswith("/first-role/"):
                raise httpx.HTTPStatusError(
                    "Unavailable",
                    request=httpx.Request("GET", url),
                    response=httpx.Response(403),
                )
            if url.endswith("/second-role/"):
                return soup(
                    '<div class="section_header"><h1 class="title">Second Officer at Example</h1><span class="date"><strong>23 October 2026</strong></span></div><div class="section single"><div class="section_content"><font>'
                    + body
                    + "</font></div></div>"
                )
            return index

        with patch.object(jobweb, "page", side_effect=read):
            _, jobs = await jobweb.collect(client)
        self.assertEqual(jobs.failed_checks, 1)
        self.assertEqual([job["title"] for job in jobs], ["Second Officer"])

    def test_tracker_keeps_distinct_roles_on_one_page_and_deduplicates_repeated_saves(
        self,
    ):
        records = []

        class Query:
            def __init__(self, table):
                self.table, self.filters, self.pending = table, {}, None

            def select(self, columns):
                return self

            def eq(self, field, value):
                self.filters[field] = value
                return self

            def is_(self, field, value):
                self.filters[field] = None if value == "null" else value
                return self

            def limit(self, count):
                return self

            def insert(self, value):
                self.pending = value
                return self

            def execute(self):
                if self.table == "profiles":
                    return SimpleNamespace(data=[{"onboarding_complete": True}])
                if self.pending is not None:
                    row = {**self.pending, "id": f"synthetic-{len(records) + 1}"}
                    records.append(row)
                    return SimpleNamespace(data=[row])
                return SimpleNamespace(
                    data=[
                        row
                        for row in records
                        if all(
                            row.get(key) == value for key, value in self.filters.items()
                        )
                    ]
                )

        db = MagicMock()
        db.table.side_effect = Query
        url = "https://careers.example.test/internships#operations"
        first = workspace.Application(
            job_title="Personal Assistant",
            company_name="Example Employer",
            source_url=url,
        )
        second = workspace.Application(
            job_title="Data Entry Intern",
            company_name="Example Employer",
            source_url=url,
        )
        other_company = workspace.Application(
            job_title="Personal Assistant",
            company_name="Another Employer",
            source_url=url,
        )
        with patch.object(workspace, "supabase", db):
            saved_first = workspace.add_application(first, user="synthetic-owner")
            saved_second = workspace.add_application(second, user="synthetic-owner")
            saved_other = workspace.add_application(
                other_company, user="synthetic-owner"
            )
            repeated = workspace.add_application(first, user="synthetic-owner")
        self.assertEqual(len(records), 3)
        self.assertNotEqual(saved_first["id"], saved_second["id"])
        self.assertNotEqual(saved_first["id"], saved_other["id"])
        self.assertEqual(saved_first["id"], repeated["id"])
