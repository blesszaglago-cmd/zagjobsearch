"""Source fixtures exercise eligibility and closures without external requests."""

import json
import unittest
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
import catalogue as c
import ghana_sources as g


class GhanaSourceTests(unittest.TestCase):
    def current_notice(self, location="Tamale", deadline=None):
        deadline = deadline or (c.NOW() + timedelta(days=3)).strftime("%d %B %Y")
        fields = {
            "Company": "Example Ghana",
            "Location": location,
            "Job status": "Full-Time",
            "Category": "Agriculture",
            "Experience": "2 years",
            "Job expires": deadline,
        }
        rows = "".join(
            f"<div class='row'><h4>{k}:</h4><h4>{v}</h4></div>"
            for k, v in fields.items()
        )
        return BeautifulSoup(
            f'<meta property="article:published_time" content="{c.NOW().isoformat()}"><div class="summary">{rows}</div><h3 class="special cat">Categories</h3><h3 class="special">Job Vacancy For Field Officer</h3><div class="content text-justify">Support farmers and prepare reports for the team in northern Ghana. Responsibilities include field visits and data collection. Closing Date: {deadline}</div>',
            "html.parser",
        )

    def glmis_notice(self, location="Tamale, Northern", posted="4 days ago"):
        return BeautifulSoup(
            f'<div><div><h2 id="jobTitle">Field Officer</h2></div><span id="employerName">Example Ghana</span><span><i class="fa-map-marker"></i>{location}</span><span><i class="fa-clock"></i>Full-time . On-Site</span><span><i class="fa-building"></i>Agriculture</span><div>Posted {posted}</div><div class="pt-2"><h5>Job Description</h5><p>Support local farmers and prepare reports. Coordinate the field team and collect information about farms in the region.</p></div></div>',
            "html.parser",
        )

    def test_board_metadata_is_summarised_and_expired_notices_are_removed(self):
        j = g.parse_current_jobs(
            self.current_notice(),
            "https://www.ghanacurrentjobs.com/job-vacancy-for-field-officer/",
        )
        self.assertEqual(j["title"], "Field Officer")
        self.assertEqual(j["regions"], ["Northern"])
        self.assertEqual(j["source"], "Ghana Current Jobs")
        self.assertEqual(j["description_kind"], "source_summary")
        self.assertNotIn("Responsibilities include field visits", j["description"])
        self.assertIsNone(
            g.parse_current_jobs(
                self.current_notice(deadline="10 January 2020"),
                "https://www.ghanacurrentjobs.com/job-vacancy-for-field-officer/",
            )
        )
        self.assertIsNone(
            g.parse_current_jobs(
                self.current_notice(location="Dubai"),
                "https://www.ghanacurrentjobs.com/job-vacancy-for-field-officer/",
            )
        )

    def test_ghana_agency_address_does_not_qualify_an_overseas_job(self):
        self.assertIsNone(
            g.parse_glmis(
                self.glmis_notice(
                    "United Arab Emirates, Ledzokuku Municipal Greater Accra"
                ),
                "https://www.glmis.gov.gh/JobPostings/JobDetails/1",
            )
        )
        self.assertIsNotNone(
            g.parse_glmis(
                self.glmis_notice(), "https://www.glmis.gov.gh/JobPostings/JobDetails/1"
            )
        )
        self.assertIsNone(
            g.parse_glmis(
                self.glmis_notice(posted="3 months ago"),
                "https://www.glmis.gov.gh/JobPostings/JobDetails/1",
            )
        )

    def test_agency_feed_dates_locations_and_anonymous_clients(self):
        item = ET.fromstring(
            f"<item><title>Spintex: Junior Accountant</title><link>https://hiregh.com/accountant/</link><pubDate>{format_datetime(c.NOW())}</pubDate><description>Prepare accurate accounts and reports. Support the finance team and maintain the accounting records for this employer.</description></item>"
        )
        j = g.parse_hire_item(item)
        self.assertEqual(j["company"], "Employer not disclosed (HIREghana)")
        self.assertEqual(j["regions"], ["Greater Accra"])
        item.find("pubDate").text = format_datetime(c.NOW() - timedelta(days=61))
        self.assertIsNone(g.parse_hire_item(item))
        item.find("pubDate").text = format_datetime(c.NOW())
        item.find("link").text = "https://example.com/accountant/"
        self.assertIsNone(g.parse_hire_item(item))

    def test_newmont_requires_open_status_and_matching_job_identity(self):
        detail = {
            "status": 200,
            "data": {
                "job": {
                    "postingStatus": "Open",
                    "country": "Ghana",
                    "jobId": "12",
                    "title": "Analyst",
                    "location": "Kenyasi, Ghana",
                    "postedDate": c.NOW().isoformat(),
                }
            },
        }
        schema = {
            "@type": "JobPosting",
            "identifier": {"value": "12"},
            "title": "Analyst",
            "description": "Analyse site systems and support the mining team. Maintain accurate records and coordinate day to day operations.",
            "employmentType": ["FULL_TIME"],
        }

        def soup():
            return BeautifulSoup(
                f'<script>var data={{"jobDetail":{json.dumps(detail)}}}</script><script type="application/ld+json">{json.dumps(schema)}</script><div hidden>The job is no longer available.</div>',
                "html.parser",
            )

        self.assertIsNotNone(
            g.parse_newmont(soup(), "https://jobs.newmont.com/us/en/job/12/Analyst")
        )
        detail["data"]["job"]["postingStatus"] = "Closed"
        self.assertIsNone(
            g.parse_newmont(soup(), "https://jobs.newmont.com/us/en/job/12/Analyst")
        )
        detail["data"]["job"]["postingStatus"] = "Open"
        schema["identifier"]["value"] = "999"
        self.assertIsNone(
            g.parse_newmont(soup(), "https://jobs.newmont.com/us/en/job/12/Analyst")
        )

    def test_telecel_keeps_only_published_recent_ghana_vacancies(self):
        row = {
            "Country": "Ghana",
            "Publish": True,
            "id": "1234",
            "Posting_Title": "Finance Intern",
            "City": "Accra",
            "Job_Description": "Support the finance team and learn financial reporting. Prepare reconciliations and maintain records with a supervisor.",
            "Date_Opened": c.NOW().isoformat(),
            "Job_Type": "Full time",
        }
        j = g.parse_telecel(row)
        self.assertEqual(j["category"], "early")
        self.assertIn("/1234/Finance-Intern", j["url"])
        self.assertIsNone(g.parse_telecel({**row, "Country": "Nigeria"}))
        self.assertIsNone(g.parse_telecel({**row, "Publish": False}))
        self.assertIsNotNone(
            g.parse_telecel(
                {**row, "Date_Opened": (c.NOW() - timedelta(days=61)).isoformat()}
            )
        )

    def test_duplicate_board_record_yields_to_direct_employer(self):
        base = {
            "company": "Telecel Ghana",
            "title": "Account Manager – High Value SME",
            "location": "Accra",
        }
        direct = {
            **base,
            "title": "Account Manager - High Value SME",
            "location": "Accra, Ghana",
        }
        self.assertEqual(c.job_identity(base), c.job_identity(direct))

    def test_database_pagination_does_not_silently_drop_larger_catalogues(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.side_effect = [
            MagicMock(data=[{"id": str(i)} for i in range(500)]),
            MagicMock(data=[{"id": "last"}]),
        ]
        with patch.object(c, "supabase", db):
            rows = c.catalogue_rows("id")
        self.assertEqual(len(rows), 501)
        self.assertEqual(rows[-1]["id"], "last")


class PartialSourceTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, removed=False):
        import httpx

        index = BeautifulSoup(
            '<div class="content"><a href="/job-vacancy-for-first/">First</a><a href="/job-vacancy-for-second/">Second</a></div>',
            "html.parser",
        )
        fixture = GhanaSourceTests().current_notice()

        async def page(client, url):
            if "job-vacancy-for-first" in url:
                return fixture
            if "job-vacancy-for-second" in url:
                if removed:
                    raise httpx.HTTPStatusError(
                        "Removed",
                        request=httpx.Request("GET", url),
                        response=httpx.Response(404),
                    )
                return BeautifulSoup("<main>New page format</main>", "html.parser")
            return index

        with patch.object(g, "page", side_effect=page):
            return await g.current_jobs(object())

    async def test_one_malformed_detail_is_not_reported_as_a_healthy_source(self):
        with self.assertRaises(ValueError):
            await self.collect()

    async def test_removed_detail_does_not_discard_other_current_jobs(self):
        source, jobs = await self.collect(removed=True)
        self.assertEqual(source, "ghana-current-jobs")
        self.assertEqual(len(jobs), 1)
