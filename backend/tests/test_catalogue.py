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
                await c.catalogue_details(job["id"])
        self.assertEqual(error.exception.status_code, 410)
        db.table.return_value.update.assert_called_with({"status": "closed"})

    def test_expired_rows_are_not_searchable(self):
        expired = self.job()
        expired["category"] = "jobs"
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        rows = [
            {
                "payload": expired,
                "first_seen_at": c.NOW().isoformat(),
                "deadline": (c.NOW() - timedelta(days=1)).isoformat(),
            }
        ]
        request = Request({"type": "http", "query_string": b"category=jobs"})
        with patch.object(c, "active_rows", return_value=rows), patch.object(
            c, "supabase", db
        ):
            r = c.search_catalogue(request)
        self.assertEqual(r["jobs"], [])

    async def test_failed_source_preserved_but_disappeared_listing_closed(self):
        job = self.job()
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = True
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {"id": "gone", "source_key": "test"},
            {"id": "keep", "source_key": "unavailable"},
        ]
        with patch.object(c, "supabase", db), patch.object(
            c,
            "collect",
            AsyncMock(return_value=[("test", [job]), ("unavailable", None)]),
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
