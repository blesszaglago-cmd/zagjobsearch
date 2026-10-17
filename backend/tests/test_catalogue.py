"""Regression checks for Ghana eligibility, stale listings, category semantics and closure."""

import sys, types, unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
from starlette.requests import Request

fake = types.ModuleType("database.supabase_client")
fake.supabase = MagicMock()
with patch.dict(sys.modules, {"database.supabase_client": fake}):
    import catalogue as c


class CatalogueTests(unittest.IsolatedAsyncioTestCase):
    def job(self, **kw):
        args = dict(
            source="test",
            key="1",
            title="Junior analyst",
            company="Test",
            location="Accra, Ghana",
            body="Analyse reports and support a team. " * 10,
            url="https://example.com/jobs/1",
            posted=c.NOW().isoformat(),
        )
        args.update(kw)
        return c.make_job(**args)

    def test_expired_closed_and_old_are_withheld(self):
        self.assertIsNone(self.job(deadline=c.NOW() - timedelta(seconds=1)))
        self.assertIsNone(self.job(body="This position has been filled. " * 10))
        self.assertIsNone(self.job(posted=(c.NOW() - timedelta(days=61)).isoformat()))
        self.assertIsNotNone(
            self.job(
                posted=(c.NOW() - timedelta(days=61)).isoformat(),
                deadline=c.NOW() + timedelta(days=1),
            )
        )

    def test_categories_and_unspecified_values(self):
        self.assertEqual(self.job(title="Finance Intern")["category"], "early")
        self.assertEqual(
            self.job(title="Software Engineer", remote=True)["category"], "remote"
        )
        self.assertEqual(
            self.job(title="Software Engineer")["experience"], "unspecified"
        )
        self.assertEqual(c.classify("Analyst (Full Time)"), "full-time")
        self.assertEqual(c.level("Junior analyst"), "junior")
        self.assertEqual(c.classify("Graduate trainee"), "graduate")

    def test_regions_do_not_misclassify_kasoa_or_north(self):
        self.assertEqual(c.regions_for("Kasoa, Ghana"), ["Central"])
        self.assertEqual(c.regions_for("Bibiani, Western North"), ["Western North"])
        self.assertEqual(c.regions_for("Techiman, Bono East"), ["Bono East"])

    def test_explicit_deadline_parsing(self):
        self.assertEqual(c.closing("Deadline: 28th October 2026").day, 28)
        self.assertIsNone(c.closing("Programme 2026. Interviews 28 October 2026."))
        self.assertEqual(c.date("2026-10-28").hour, 23)
        self.assertEqual(c.date("Sat Oct 24 00:00:00 UTC 2026").hour, 0)

    async def test_no_ghana_inference_from_worldwide_or_africa(self):
        client = AsyncMock()
        response = MagicMock()
        client.get.return_value = response
        response.json.return_value = {
            "jobs": [
                {"location": {"name": "Worldwide"}, "title": "Engineer"},
                {"location": {"name": "Africa"}, "title": "Engineer"},
            ]
        }
        _, jobs = await c.greenhouse(client, "jumia")
        self.assertEqual(jobs, [])

    async def test_source_missing_closes_details_instead_of_applying(self):
        job = self.job(
            check_url="https://boards-api.greenhouse.io/v1/boards/jumia/jobs/1"
        )
        row = {
            "payload": job,
            "first_seen_at": c.NOW().isoformat(),
            "last_checked_at": c.NOW().isoformat(),
            "deadline": None,
            "status": "active",
        }
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            row
        ]
        client = AsyncMock()
        client.get.return_value = MagicMock(status_code=404)
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)
        with patch.object(c, "supabase", db), patch.object(
            c.httpx, "AsyncClient", return_value=context
        ):
            with self.assertRaises(HTTPException) as error:
                await c.catalogue_details(job["id"], verify=True)
        self.assertEqual(error.exception.status_code, 410)
        db.table.return_value.update.assert_called_with({"status": "closed"})

    def test_search_validates_input_and_preserves_database_pagination(self):
        with self.assertRaises(HTTPException):
            c.query_catalogue({"category": "unrelated"})
        with self.assertRaises(HTTPException):
            c.query_catalogue({"salary_min": "NaN"})
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = {
            "jobs": [],
            "total": 1200,
            "page": 51,
            "has_more": True,
        }
        with patch.object(c, "supabase", db):
            result = c.query_catalogue({"page": "51"})
        self.assertEqual(result["page"], 51)
        self.assertEqual(db.rpc.call_args.args[1]["filters"]["page"], "51")

    async def test_failed_source_preserved_but_disappeared_listing_closed(self):
        job = self.job()
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = True
        db.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value.data = [
            {"id": "gone", "source_key": "test"},
            {"id": "keep", "source_key": "unavailable"},
            {"id": "window", "source_key": "glmis"},
        ]
        with patch.object(c, "supabase", db), patch.object(
            c,
            "collect",
            AsyncMock(
                return_value=[("test", [job]), ("unavailable", None), ("glmis", [])]
            ),
        ):
            result = await c.refresh()
        self.assertTrue(result["refreshed"])
        db.table.return_value.update.return_value.in_.assert_called_once_with(
            "id", ["gone"]
        )

    async def test_overlapping_refresh_does_not_download_sources(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = False
        collector = AsyncMock()
        with patch.object(c, "supabase", db), patch.object(c, "collect", collector):
            self.assertFalse((await c.refresh())["refreshed"])
        collector.assert_not_awaited()


class ScholsecTests(unittest.IsolatedAsyncioTestCase):
    def notice(
        self,
        title="Scholarship for Ghanaian students",
        deadline="Not specified",
        body="Ghanaian students may apply. Check eligibility with the Authority.",
        status="Official notice",
    ):
        from bs4 import BeautifulSoup

        return BeautifulSoup(
            f'<main><h1>{title}</h1><div class="opportunity-meta-card"><span>Deadline</span><strong>{deadline}</strong></div><div class="opportunity-meta-card"><span>Status</span><strong>{status}</strong></div><div class="opportunity-meta-card"><span>Published</span><strong>April 10, 2026</strong></div><div class="opportunity-article-body"><p>{body}</p></div></main>',
            "html.parser",
        )

    def test_closed_notice_is_retained_and_cannot_apply(self):
        j = c.parse_scholarship(
            self.notice(deadline="September 21, 2026", status="Open"),
            "https://scholarships.gov.gh/opportunities/algeria",
        )
        self.assertEqual(j["listing_status"], "closed")
        self.assertFalse(j["can_apply"])

    def test_unknown_deadline_never_becomes_open(self):
        j = c.parse_scholarship(
            self.notice(status="Open"),
            "https://scholarships.gov.gh/opportunities/unknown",
        )
        self.assertEqual(j["listing_status"], "unconfirmed")
        self.assertFalse(j["can_apply"])

    def test_body_deadline_and_local_window_are_recognised(self):
        self.assertEqual(
            c.scholarship_deadline(
                {},
                "Application Deadline All applications must be submitted on or before 26th June 2026.",
            ).day,
            26,
        )
        self.assertEqual(
            c.scholarship_deadline(
                {},
                "The effective opening date for applications is Friday, April 10 th , 2026 to Friday May 15 th 2026.",
            ).isoformat(),
            "2026-05-15T23:59:59+00:00",
        )

    async def test_all_pages_are_followed_without_external_links(self):
        from bs4 import BeautifulSoup

        base = "https://scholarships.gov.gh"
        first = BeautifulSoup(
            '2 Total notices<a href="/opportunities/one">One</a><a href="/opportunities?page=2">Next</a><a href="https://evil.example/opportunities?page=3">Ignore</a>',
            "html.parser",
        )
        second = BeautifulSoup(
            '<a href="/opportunities/two">Two</a><a href="/opportunities?page=2">2</a>',
            "html.parser",
        )

        async def read(client, url):
            if url == base + "/opportunities":
                return first
            if url == base + "/opportunities?page=2":
                return second
            return self.notice()

        fetch = AsyncMock(side_effect=read)
        with patch.object(c, "html_get", fetch):
            source, jobs = await c.scholarships(None)
        self.assertEqual(source, "scholarships-authority")
        self.assertEqual(len(jobs), 2)
        self.assertEqual(fetch.await_count, 4)

    def test_open_default_filter_is_sent_to_database(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = {
            "jobs": [],
            "total": 0,
            "page": 1,
            "has_more": False,
        }
        with patch.object(c, "supabase", db), patch.object(
            c, "refresh_state", return_value={}
        ):
            result = c.search_catalogue(
                Request({"type": "http", "query_string": b"category=scholarships"})
            )
        self.assertEqual(result["jobs"], [])
        sent = db.rpc.call_args.args[1]["filters"]
        self.assertEqual(sent["category"], "scholarships")
        self.assertNotEqual(sent.get("availability"), "all")
