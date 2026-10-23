"""Eligibility, window, source attribution and academic pagination regressions."""

import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from bs4 import BeautifulSoup

fake = types.ModuleType("database.supabase_client")
fake.supabase = MagicMock()
with patch.dict(sys.modules, {"database.supabase_client": fake}):
    import catalogue as c
import academic_sources as a

NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


def soup(html):
    return BeautifulSoup(html, "html.parser")


def daad_card(
    identity="12345678",
    deadline="24.09.2026 Selection in February 2027. 17.03.2027",
    title="Research Grants in Germany",
):
    return f"""<li class="c-scholarship-list__item"><h3><a href="?origin=145&target=145&detail_to_show=0&detail_to_show={identity}">{title}</a></h3><p>Research stays during a doctorate or in the early postdoc phase.</p><dl><dt>Status:</dt><dd>Doctoral candidates/PhD students Postdoctoral researchers</dd><dt>Application deadline:</dt><dd>{deadline}</dd></dl></li>"""


def daad_index(cards, total=1, extra=""):
    return soup(
        f'<select name="origin"><option value="145" selected>Ghana</option></select>{total} Scholarship Options<ul>{cards}</ul>{extra}'
    )


def ug_notice(body, title="Research Fund", deadline="30 November 2026 (24:00 CET)"):
    return soup(
        f'<div id="block-mainpagecontent"><article><h3>{title}</h3><div class="date-social"><p>22 October 2026</p></div><div class="page-image"><p>The University of Ghana invites the University community to apply.</p>{body}</div><div class="deadline-details"><h6>Deadline</h6><p>{deadline}</p></div></article></div>'
    )


class AcademicSourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.module = patch.dict(sys.modules, {"catalogue": c})
        self.module.start()
        self.addCleanup(self.module.stop)
        self.clock = patch.object(c, "NOW", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def test_deadline_zones_and_end_of_day(self):
        self.assertEqual(
            a.academic_date("30 November 2026 (24:00 CET)").isoformat(),
            "2026-11-30T23:00:00+00:00",
        )
        self.assertEqual(a.academic_date("13 October 2026, 15:00 UTC").hour, 15)
        self.assertIsNone(a.academic_date("Applications for 2026/2027"))
        self.assertEqual(a.academic_date("17.03.2027").hour, 23)

    def test_saved_scholarship_source_filter_is_retained(self):
        import saved_searches as saved

        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = (
            0
        )
        db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "synthetic-saved-search"}
        ]
        with patch.object(saved, "supabase", db), patch.object(
            c, "query_catalogue", return_value={"jobs": []}
        ) as search:
            result = saved.save_search(
                saved.SavedSearch(
                    name="ScholSec notices",
                    filters={
                        "category": "scholarships",
                        "source": "scholarships-authority",
                        "availability": "all",
                    },
                    email_alert=False,
                ),
                user="synthetic-user",
            )
        self.assertTrue(result["saved"])
        self.assertEqual(search.call_args.args[0]["source"], "scholarships-authority")

    def test_ghana_origin_and_individual_programme_identity_are_required(self):
        with self.assertRaises(ValueError):
            a.parse_daad_index(soup(daad_card()))
        with self.assertRaises(ValueError):
            a.daad_url(
                "https://other.example/?origin=145&target=145&detail_to_show=12345678",
                detail=True,
            )
        with self.assertRaises(ValueError):
            a.daad_url("?origin=200&target=145&detail_to_show=12345678", detail=True)
        canonical = a.daad_url(
            "?origin=145&target=145&detail_to_show=0&detail_to_show=12345678&pg=2",
            detail=True,
        )
        self.assertIn("detail_to_show=12345678", canonical)
        self.assertIn("onlydaad=1", canonical)
        self.assertNotIn("pg=", canonical)

    def test_next_stated_round_is_not_the_old_round_or_selection_year(self):
        job = a.parse_daad_index(daad_index(daad_card()))[0]
        self.assertEqual(job["deadline"], "2027-03-17T23:59:59+00:00")
        self.assertEqual(job["listing_status"], "open")
        self.assertEqual(job["job_type"], "research-grant")
        self.assertEqual(job["category"], "scholarships")

    def test_explicit_annual_window_is_current_only_after_opening(self):
        card = daad_card(
            deadline="30 October of each year, 23:59 (Central European Time). Applications are possible from 01 September each year"
        )
        job = a.parse_daad_index(daad_index(card))[0]
        self.assertEqual(job["deadline"], "2026-10-30T22:59:00+00:00")
        with patch.object(
            c, "NOW", return_value=datetime(2027, 5, 1, tzinfo=timezone.utc)
        ):
            job = a.parse_daad_index(daad_index(card))[0]
            self.assertEqual(job["listing_status"], "closed")
        unknown = a.parse_daad_index(
            daad_index(daad_card(deadline="November each year"))
        )[0]
        self.assertEqual(unknown["listing_status"], "unconfirmed")
        self.assertFalse(unknown["can_apply"])

    async def test_complete_pagination_and_total_guard(self):
        first = daad_index(
            daad_card(),
            total=2,
            extra='<select><option value="?origin=145&target=145&pg=1&pg=2">2</option></select>',
        )
        second = daad_index(daad_card("12345679"), total=2)
        with patch.object(a, "page", AsyncMock(side_effect=[first, second])) as read:
            name, rows = await a.daad(None)
        self.assertEqual(name, "daad-ghana")
        self.assertEqual(len(rows), 2)
        self.assertIn("pg=2", read.call_args_list[1].args[1])
        with patch.object(
            a, "page", AsyncMock(return_value=daad_index(daad_card(), total=2))
        ):
            with self.assertRaisesRegex(ValueError, "incomplete"):
                await a.daad(None)

    async def test_primary_funder_controls_rolling_acceptance_and_application_url(self):
        notice = next(iter(a.PRIMARY_CALLS))
        job = a.make_academic(
            "knust-research",
            notice,
            "African Scholars Research Funding",
            "A research funding call.",
            rolling=True,
        )
        accepted = soup(
            "<h1>DigiFI Request for Proposals</h1><p>DigiFI is currently accepting proposals. This call is open to African scholars.</p>"
        )
        with patch.object(a, "page", AsyncMock(return_value=accepted)):
            fresh = await a.confirm_primary(None, job)
        self.assertTrue(fresh["can_apply"])
        self.assertEqual(fresh["url"], a.PRIMARY_CALLS[notice])
        closed = soup(
            "<h1>DigiFI Request for Proposals</h1><p>DigiFI is no longer accepting proposals.</p>"
        )
        with patch.object(a, "page", AsyncMock(return_value=closed)):
            fresh = await a.confirm_primary(None, job)
        self.assertFalse(fresh["can_apply"])

    def test_research_call_classification_and_offered_degree_come_from_the_award(self):
        self.assertEqual(
            a.opportunity_kind(
                "International Call for Projects", "A research grant for physicians."
            ),
            "research-grant",
        )
        self.assertEqual(a.opportunity_kind("Investigator Award"), "research-award")
        self.assertEqual(
            a.opportunity_kind(
                "Re-invitation Programme for Former Scholarship Holders"
            ),
            "fellowship",
        )
        node = ug_notice(
            "<p>Scholarships support MPhil students.</p><p>Eligibility</p><p>Applicants must hold a first degree.</p><p>Provide an undergraduate degree certificate.</p>",
            title="MPhil Scholarship",
        )
        job = a.parse_university(node, a.UG + "/node/1", "ug-research")
        self.assertEqual(job["study_levels"], ["mphil"])

    def test_grant_conditions_do_not_become_a_funded_phd_degree(self):
        job = a.parse_university(
            ug_notice(
                "<p>Both applicants must be at postdoctoral level or above and have an African university partner.</p>"
            ),
            a.UG + "/node/1",
            "ug-research",
        )
        self.assertEqual(job["job_type"], "research-grant")
        self.assertEqual(job["study_levels"], [])
        self.assertIn("postdoctoral", job["eligibility_note"])
        self.assertEqual(job["source"], a.SOURCE_INFO["ug-research"][0])
        self.assertNotIn("Scholsec", job["company"])

    def test_self_funded_and_foreign_only_notices_are_excluded(self):
        self.assertIsNone(
            a.parse_university(
                ug_notice(
                    "<p>Evidence of sufficient funds is needed for this stay.</p>",
                    title="Visiting Research Student",
                ),
                a.UG + "/node/1",
                "ug-research",
            )
        )
        self.assertIsNone(
            a.parse_university(
                ug_notice("<p>Applicants must be British citizens.</p>"),
                a.UG + "/node/1",
                "ug-research",
            )
        )

    def test_rolling_calls_are_not_given_a_fake_year_end_deadline(self):
        html = '<main><h1>African Scholars Research Funding</h1><div class="event-time"><time datetime="2026-12-31T23:59:00Z"></time></div><div class="event-discription"><p>Resident African Scholars at sub-Saharan African institutions can apply. Applications use rolling submissions and are reviewed every few weeks. A research partner and PhD may be required.</p></div></main>'
        job = a.parse_university(
            soup(html), a.KNUST + "/funding/research", "knust-research"
        )
        self.assertIsNone(job["deadline"])
        self.assertEqual(job["application_window"], "rolling")
        self.assertTrue(job["can_apply"])
        self.assertEqual(
            c.scholarship_state({**job, "source_status": "closed"}), "closed"
        )
        self.assertIsNone(
            a.parse_university(
                soup(html.replace("African Scholars Research", "DAAD Research")),
                a.KNUST + "/funding/research",
                "knust-research",
            )
        )

    async def test_university_php_pagination_and_scholarship_directory(self):
        first = soup(
            '<div id="block-views-block-applications-block-1"><div class="publication-content"><h4><a href="/node/1">One</a></h4></div><a rel="next" href="/index.php/call-for-applications?page=1">Next</a></div>'
        )
        second = soup(
            '<div id="block-views-block-applications-block-1"><div class="publication-content"><h4><a href="/node/2">Two</a></h4></div></div>'
        )
        directory = soup('<div id="block-orid-scholarships"></div>')
        detail = ug_notice(
            "<p>Funding is available for research applicants with institutional support.</p>"
        )
        with patch.object(
            a, "page", AsyncMock(side_effect=[first, second, directory, detail, detail])
        ) as read:
            _, rows = await a.university(None, "ug-research")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["source_urls"]), 2)
        self.assertEqual(
            read.call_args_list[1].args[1], a.UG + "/call-for-applications?page=1"
        )

    async def test_apply_uses_fresh_academic_status_and_failure_does_not_close_archive(
        self,
    ):
        job = a.make_academic(
            "ug-research",
            a.UG + "/node/1",
            "Research grant",
            "Source summary.",
            deadline=a.academic_date("30 November 2026"),
        )
        row = {
            "payload": job,
            "status": "active",
            "first_seen_at": NOW.isoformat(),
            "last_checked_at": NOW.isoformat(),
            "deadline": job["deadline"],
        }
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            row
        ]
        response = httpx.Response(
            200,
            text=str(
                ug_notice(
                    "<p>Applicants need an academic partner and a research proposal.</p>",
                    deadline="15 September 2026",
                )
            ),
            request=httpx.Request("GET", job["url"]),
        )
        client = AsyncMock()
        client.get.return_value = response
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)
        with patch.object(c, "supabase", db), patch.object(
            c.httpx, "AsyncClient", return_value=context
        ):
            fresh = await c.catalogue_details(job["id"], verify=True)
            self.assertFalse(fresh["can_apply"])
            self.assertEqual(fresh["listing_status"], "closed")
            client.get.return_value = httpx.Response(
                404, request=httpx.Request("GET", job["url"])
            )
            with self.assertRaises(c.HTTPException) as error:
                await c.catalogue_details(job["id"], verify=True)
            self.assertEqual(error.exception.status_code, 503)
        db.table.return_value.update.assert_not_called()
