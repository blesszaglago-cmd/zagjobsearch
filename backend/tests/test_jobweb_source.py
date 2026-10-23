"""Board metadata contradictions must not become catalogue facts."""

import unittest
import sys
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
import httpx
from bs4 import BeautifulSoup
import catalogue as c
import jobweb_source as w
import employer_sources as e

NOW = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)


class SourceFactTests(unittest.TestCase):
    def setUp(self):
        self.module = patch.dict(sys.modules, {"catalogue": c})
        self.module.start()
        self.addCleanup(self.module.stop)
        self.clock = patch.object(c, "NOW", return_value=NOW)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def body(self, location="Hohoe, Ghana", ending="Closing Date: 30 October, 2026"):
        return BeautifulSoup(
            f'<p>Location: {location}</p><p>Support client operations and deliver training across the work area. The source gives no salary.</p><p>{ending}</p><script type="application/ld+json">{{"jobLocation":{{"address":{{"addressLocality":"Accra"}}}},"baseSalary":{{"currency":"GHS","value":5000}}}}</script>',
            "html.parser",
        )

    def test_readable_location_deadline_and_salary_override_template_metadata(self):
        job = w.from_body(
            "Operations Officer at Example Employer",
            self.body(),
            w.BASE + "/jobs/officer/",
            "22 October 2026",
        )
        self.assertEqual(job["regions"], ["Volta"])
        self.assertIsNone(job.get("salary_min"))
        self.assertEqual(job["deadline"], "2026-10-30T23:59:59+00:00")
        self.assertEqual(job["description_kind"], "source_summary")

    def test_expired_unknown_foreign_and_old_rolling_adverts_are_withheld(self):
        for location, ending, posted in [
            ("Hohoe, Ghana", "Closing Date: 1 October 2026", "22 October 2026"),
            ("Hohoe, Ghana", "No closing date supplied", "22 October 2026"),
            ("Lagos, Nigeria", "Closing Date: 30 October 2026", "22 October 2026"),
            (
                "Hohoe, Ghana",
                "Applications accepted on a rolling basis until the position is filled.",
                "1 September 2026",
            ),
        ]:
            with self.subTest(location=location, ending=ending):
                self.assertIsNone(
                    w.from_body(
                        "Officer at Employer",
                        self.body(location, ending),
                        w.BASE + "/jobs/officer/",
                        posted,
                    )
                )
        self.assertIsNotNone(
            w.from_body(
                "Officer at Employer",
                self.body(
                    ending="Applications accepted on a rolling basis until the position is filled."
                ),
                w.BASE + "/jobs/officer/",
                "22 October 2026",
            )
        )

    def test_employer_index_completeness_and_individual_application_links(self):
        index = BeautifulSoup(
            '<main>Showing 1 results<div name="card" id="jobs/example/officer" role="button"></div></main>',
            "html.parser",
        )
        self.assertEqual(
            e.mpharma_cards(index), ["https://erp.mpharma.com/jobs/example/officer"]
        )
        with self.assertRaises(ValueError):
            e.mpharma_cards(
                BeautifulSoup(
                    str(index).replace("Showing 1", "Showing 2"), "html.parser"
                )
            )
        html = (
            '<main><h1>Senior Officer</h1><div class="text-uppercase">Location</div><div>Accra, Ghana</div><div class="text-uppercase">Employment Type</div><div>Full-Time - Permanent Contract</div><div class="ql-editor">'
            + "Deliver healthcare services and support customer operations. " * 3
            + '</div><a href="/job_application/new?job_title=HR-2026-001">Apply Now</a></main>'
        )
        job = e.parse_mpharma(
            BeautifulSoup(html, "html.parser"),
            "https://erp.mpharma.com/jobs/example/officer",
        )
        self.assertEqual(job["job_type"], "permanent")
        self.assertIn("job_title=HR-2026-001", job["url"])
        self.assertIsNone(job["created"])
        with self.assertRaises(ValueError):
            e.parse_mpharma(
                BeautifulSoup(
                    html.replace(
                        "/job_application/new?",
                        "https://other.example/job_application/new?",
                    ),
                    "html.parser",
                ),
                "https://erp.mpharma.com/jobs/example/officer",
            )

    def test_graduate_management_trainee_belongs_to_early_careers(self):
        self.assertEqual(
            c.classify("Graduate Management Trainee - Company (Full Time)"), "graduate"
        )
        self.assertEqual(
            c.classify("Senior Engineer", "Bachelor or graduate degree required"),
            "unspecified",
        )
        self.assertEqual(c.classify("Head of Procurement & Contracts"), "unspecified")
        self.assertEqual(c.regions_for("Tumu, Ghana"), ["Upper West"])


class BoardCollectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_identical_reposts_are_one_opportunity_with_both_links(self):
        index = BeautifulSoup(
            '<ol class="jobs"><li><a href="/jobs/officer-company/">One</a><a href="/jobs/officer-company-2/">Repost</a></li></ol>',
            "html.parser",
        )
        detail = BeautifulSoup(
            '<div class="section_header"><div class="date"><strong>22 October 2026</strong></div><h1 class="title">Officer at Company</h1></div><div class="section single"><div class="section_content"><font><p>Location: Accra, Ghana</p><p>Support operations, prepare detailed records, communicate with customers and work with the local team.</p><p>Closing Date: 30 October 2026</p></font></div></div>',
            "html.parser",
        )

        async def read(client, url):
            return (
                detail
                if url.endswith(("officer-company/", "officer-company-2/"))
                else index
            )

        client = AsyncMock()
        client.get.return_value = httpx.Response(
            200,
            text="<rss><channel></channel></rss>",
            request=httpx.Request("GET", w.BASE + "/feed/"),
        )
        with patch.dict(sys.modules, {"catalogue": c}), patch.object(
            c, "NOW", return_value=NOW
        ), patch.object(w, "page", side_effect=read):
            _, rows = await w.collect(client)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["source_urls"]), 2)
