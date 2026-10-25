"""Restart, publisher politeness, private state and exact-removal regressions."""

import json
import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import catalogue as c
from ghana_sources import CheckedListings
from listing_quality import clean_description, deduplicate
from public_http import PublicSourceClient
from source_progress import (
    SourceProgress,
    SourceBudgetExceeded,
    board_url,
    failure_counts,
    retry_after_time,
)

BASE = "https://www.ghanacurrentjobs.com/job-vacancy-for-"


def http_error(status):
    request = httpx.Request("GET", BASE + "test/?token=private")
    return httpx.HTTPStatusError(
        "private message",
        request=request,
        response=httpx.Response(status, request=request, text="private body"),
    )


class ProgressTests(unittest.IsolatedAsyncioTestCase):
    def test_restart_retains_unfinished_work_and_admits_new_urls(self):
        p = SourceProgress()
        urls, overflow = p.order("ghana-current-jobs", [BASE + "a/", BASE + "b/"])
        p.finish("ghana-current-jobs", urls, [{"id": "ok"}, SourceBudgetExceeded()])
        restarted = SourceProgress(json.loads(json.dumps(p.snapshot({}))))
        ordered, overflow = restarted.order("ghana-current-jobs", [BASE + "c/"])
        self.assertEqual(set(ordered), {BASE + "b/", BASE + "c/"})
        self.assertEqual(overflow, 0)

    def test_only_retryable_work_stays_pending(self):
        p = SourceProgress()
        urls = [BASE + f"role-{i}/" for i in range(5)]
        p.finish(
            "ghana-current-jobs",
            urls,
            [None, {}, http_error(404), http_error(410), http_error(503)],
        )
        self.assertEqual(p.pending["ghana-current-jobs"], [urls[-1]])
        with self.assertRaises(ValueError):
            p.finish("ghana-current-jobs", urls, [])

    def test_saved_or_discovered_urls_cannot_expand_network_access(self):
        bad = [
            "http://www.ghanacurrentjobs.com/job-vacancy-for-x/",
            BASE + "x/?secret=x",
            BASE + "x/#y",
            "https://localhost/job-vacancy-for-x/",
            "https://user:pass@www.ghanacurrentjobs.com/job-vacancy-for-x/",
            BASE + "x/\\",
            BASE + "x/\n",
            "https://www.ghanacurrentjobs.com:8443/job-vacancy-for-x/",
            "https://www.ghanacurrentjobs.com/other/",
        ]
        for url in bad:
            self.assertIsNone(board_url("ghana-current-jobs", url))
        p = SourceProgress({"version": 1, "pending": {"ghana-current-jobs": bad}})
        self.assertEqual(p.order("ghana-current-jobs", bad), ([], 0))

    def test_queue_bound_is_explicit(self):
        p = SourceProgress()
        urls, overflow = p.order(
            "ghana-current-jobs", [BASE + f"role-{i}/" for i in range(650)]
        )
        self.assertEqual((len(urls), overflow), (640, 10))
        p.finish("ghana-current-jobs", urls, [TimeoutError()] * 640)
        self.assertEqual(len(p.pending["ghana-current-jobs"]), 640)

    def test_failure_diagnostics_contain_no_exception_text_or_urls(self):
        failures = failure_counts(
            [
                http_error(429),
                SourceBudgetExceeded(),
                httpx.ReadTimeout("private"),
                httpx.ConnectError("private"),
                ValueError("private"),
                KeyError("private"),
                {},
            ]
        )
        self.assertEqual(
            failures,
            {
                "http_429": 1,
                "budget": 1,
                "timeout": 1,
                "connection": 1,
                "validation": 1,
                "reader": 1,
            },
        )
        self.assertNotIn("private", json.dumps(failures))

    def test_retry_after_is_not_shortened(self):
        now = datetime(2026, 10, 25, tzinfo=timezone.utc)
        self.assertEqual(retry_after_time("86400", now), now + timedelta(days=1))
        self.assertEqual(
            retry_after_time("Mon, 26 Oct 2026 00:00:00 GMT", now),
            now + timedelta(days=1),
        )
        self.assertIsNone(retry_after_time("nonsense", now))
        self.assertEqual(retry_after_time("9" * 30, now).year, 9999)

    async def test_429_pauses_waiting_requests_and_survives_restart(self):
        calls = []

        async def respond(request):
            calls.append(str(request.url))
            return httpx.Response(
                429,
                headers={"Retry-After": "86400"},
                stream=httpx.ByteStream(b""),
                request=request,
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = PublicSourceClient(http)
            self.assertEqual((await client.get(BASE + "a/")).status_code, 429)
            with self.assertRaises(httpx.HTTPStatusError):
                await client.get(BASE + "b/")
            resumed = PublicSourceClient(
                http, deferred_hosts=client.deferred_snapshot()
            )
            with self.assertRaises(httpx.HTTPStatusError):
                await resumed.get(BASE + "c/")
        self.assertEqual(len(calls), 1)

    async def test_503_pause_preserves_status_and_ignores_unapproved_hosts(self):
        until = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    503,
                    headers={"Retry-After": "86400"},
                    stream=httpx.ByteStream(b""),
                    request=request,
                )
            )
        ) as http:
            client = PublicSourceClient(
                http, deferred_hosts={"evil.example": {"until": until, "status": 429}}
            )
            self.assertEqual((await client.get(BASE + "a/")).status_code, 503)
            with self.assertRaises(httpx.HTTPStatusError) as error:
                await client.get(BASE + "b/")
            self.assertEqual(error.exception.response.status_code, 503)
            self.assertNotIn("evil.example", client.deferred_snapshot())

    async def test_concurrent_shorter_retry_reply_cannot_shorten_existing_delay(self):
        both_started = asyncio.Event()

        async def get(target, **kwargs):
            if str(target).endswith("long/"):
                await both_started.wait()
                delay = "86400"
            else:
                both_started.set()
                await asyncio.sleep(0)
                delay = "60"
            return httpx.Response(
                429,
                headers={"Retry-After": delay},
                request=httpx.Request("GET", target),
            )

        client = PublicSourceClient(None)
        client._get = get
        await asyncio.gather(client.get(BASE + "long/"), client.get(BASE + "short/"))
        until = datetime.fromisoformat(
            client.deferred_snapshot()["www.ghanacurrentjobs.com"]["until"]
        )
        self.assertGreater(until, datetime.now(timezone.utc) + timedelta(hours=23))

    async def test_only_confirmed_matching_removed_details_close(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = True
        gone = {
            "id": "gone",
            "source_key": "ghana-current-jobs",
            "check_url": BASE + "gone/",
        }
        kept = {"id": "kept", "source_key": "jobweb-ghana", "check_url": BASE + "gone/"}
        result = c.CollectedSources(
            [
                (
                    "ghana-current-jobs",
                    CheckedListings(
                        [],
                        failed_checks=1,
                        diagnostics={"timeout": 1},
                        queued_checks=1,
                        removed_urls=[BASE + "gone/"],
                    ),
                )
            ],
            progress={"version": 1, "pending": {"secret": []}, "hosts": {}},
        )
        with patch.object(c, "supabase", db), patch.object(
            c, "refresh_state", return_value={}
        ), patch.object(c, "collect", AsyncMock(return_value=result)), patch.object(
            c,
            "catalogue_rows",
            side_effect=[
                [{"payload": gone}, {"payload": kept}],
                [
                    {"id": "gone", "source_key": "ghana-current-jobs"},
                    {"id": "kept", "source_key": "jobweb-ghana"},
                ],
            ],
        ):
            report = await c.refresh()
        db.table.return_value.update.return_value.in_.assert_called_once_with(
            "id", ["gone"]
        )
        updates = [call.args[0] for call in db.table.return_value.update.call_args_list]
        self.assertTrue(
            any(update.get("source_progress") == result.progress for update in updates)
        )
        self.assertNotIn("secret", json.dumps(report))

    def test_public_refresh_state_does_not_select_private_queue(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = (
            []
        )
        with patch.object(c, "supabase", db):
            c.refresh_state()
        self.assertNotIn(
            "source_progress", db.table.return_value.select.call_args.args[0]
        )

    def test_description_cleanup_preserves_application_facts_and_documents(self):
        source = "Salary GHS 5,000.\n[https://example.org/logo.png?x=1]\n![Team](https://example.org/team.jpg)\nApply: https://example.org/apply\n[https://example.org/requirements.pdf]"
        cleaned = clean_description(source)
        self.assertNotIn("logo.png", cleaned)
        self.assertNotIn("team.jpg", cleaned)
        for fact in [
            "Salary GHS 5,000.",
            "Team",
            "https://example.org/apply",
            "https://example.org/requirements.pdf",
        ]:
            self.assertIn(fact, cleaned)

    def test_exact_canonical_duplicates_keep_both_ids_for_refresh_upserts(self):
        job = {
            "id": "first",
            "title": "Engineer",
            "company": "Test",
            "location": "Accra",
            "url": "https://example.org/jobs/123?utm_source=board",
            "source_key": "test",
        }
        result = deduplicate(
            [job, {**job, "id": "second", "url": "https://example.org/jobs/123"}]
        )
        self.assertEqual({j["id"] for j in result}, {"first", "second"})
        self.assertEqual(result[1]["duplicate_of"], "first")
