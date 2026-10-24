"""Actionable source failures retain no raw provider, URL or credential text."""

import json
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import catalogue as c


class SourceDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    def test_failure_categories_are_safe_and_distinct(self):
        request = httpx.Request("GET", "https://provider.example/?token=secret-url")
        response = httpx.Response(503, text="secret-body", request=request)
        error = httpx.HTTPStatusError(
            "secret-error", request=request, response=response
        )
        self.assertEqual(c.source_failure(error), {"kind": "http", "status": 503})
        for failure, expected in [
            (TimeoutError("secret-timeout"), "timeout"),
            (httpx.ReadTimeout("secret-timeout"), "timeout"),
            (httpx.ConnectError("secret-connection"), "connection"),
            (ValueError("secret-validation"), "validation"),
            (KeyError("secret-reader"), "reader"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(c.source_failure(failure), {"kind": expected})
                self.assertNotIn("secret", json.dumps(c.source_failure(failure)))

    async def test_refresh_persists_failure_category_without_closing_missing_records(
        self,
    ):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = True
        result = c.CollectedSources(
            [("columbia-italian-academy", None)],
            failures={"columbia-italian-academy": {"kind": "http", "status": 503}},
        )
        with patch.object(c, "supabase", db), patch.object(
            c, "refresh_state", return_value={"archive_page": 9}
        ), patch.object(c, "catalogue_rows", return_value=[]), patch.object(
            c, "collect", new=AsyncMock(return_value=result)
        ):
            report = await c.refresh()
        source = report["sources"][0]
        self.assertEqual(source["state"], "unavailable")
        self.assertEqual(source["failure"], {"kind": "http", "status": 503})
        updates = [call.args[0] for call in db.table.return_value.update.call_args_list]
        self.assertTrue(
            any(update.get("summary") == report["sources"] for update in updates)
        )
        self.assertFalse(any(update.get("status") == "closed" for update in updates))

    def test_source_status_exposes_only_current_failures(self):
        now = datetime(2026, 10, 24, 22, tzinfo=timezone.utc)
        for age, expected in [
            (timedelta(hours=1), {"kind": "timeout"}),
            (timedelta(hours=49), None),
        ]:
            with self.subTest(age=age):
                db = MagicMock()
                db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
                    {
                        "completed_at": (now - age).isoformat(),
                        "summary": [
                            {
                                "source": "columbia-italian-academy",
                                "state": "unavailable",
                                "failure": {"kind": "timeout"},
                            }
                        ],
                    }
                ]
                with patch.object(c, "supabase", db), patch.object(
                    c, "NOW", return_value=now
                ):
                    source = next(
                        item
                        for item in c.catalogue_sources()["imported"]
                        if item["key"] == "columbia-italian-academy"
                    )
                self.assertEqual(source["failure"], expected)

    async def test_legacy_collection_results_without_diagnostics_still_refresh(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = True
        with patch.object(c, "supabase", db), patch.object(
            c, "refresh_state", return_value={}
        ), patch.object(c, "catalogue_rows", return_value=[]), patch.object(
            c, "collect", new=AsyncMock(return_value=[("test", None)])
        ):
            report = await c.refresh()
        self.assertIsNone(report["sources"][0]["failure"])
        self.assertEqual(report["sources"][0]["state"], "unavailable")
