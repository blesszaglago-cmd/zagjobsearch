"""Availability failures remain fatal even with incomplete publisher checks."""

import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

spec = importlib.util.spec_from_file_location(
    "zag_public_healthcheck",
    Path(__file__).resolve().parents[2] / "scripts/healthcheck.py",
)
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class HealthcheckTests(unittest.TestCase):
    def setUp(self):
        self.listing = "a" * 32
        self.coverage = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_error": health.PARTIAL_REFRESH_MESSAGE,
        }
        self.catalogue = {
            "jobs": [{"id": self.listing, "title": "Engineer & Operations"}],
            "total": 10,
            "source_status": [
                {"source": "smart:AmaliTech", "state": "ok", "accepted": 10},
                {"source": "provider", "state": "unavailable", "accepted": 0},
            ],
        }
        self.responses = {
            health.API + "/health": {"status": "ok"},
            health.API + "/catalogue/coverage": self.coverage,
            health.API + "/catalogue?category=jobs": self.catalogue,
            health.SITE
            + "/jobs/"
            + self.listing: '<link rel="canonical"><p class="job-description-copy">Engineer &amp; Operations</p>',
            health.SITE
            + "/sitemap.xml": "<urlset><url>/jobs/"
            + self.listing
            + "</url></urlset>",
            health.SITE
            + "/robots.txt": "User-agent: *\nSitemap: https://site.example/sitemap.xml\n",
            health.API
            + "/auth/config": {
                "email_enabled": True,
                "google_enabled": False,
                "publishable_key": "test-only-public-key",
            },
        }
        for target, name, options in [
            (
                health,
                "get",
                {"side_effect": lambda url, as_json=True: self.responses[url]},
            ),
            (health, "expect_guest_denied", {}),
        ]:
            mocker = patch.object(target, name, **options)
            setattr(self, name, mocker.start())
            self.addCleanup(mocker.stop)
        env = patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": "", "GITHUB_ACTIONS": ""})
        env.start()
        self.addCleanup(env.stop)

    def run_main(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result = health.main()
        return result, output.getvalue()

    def test_partial_coverage_warns_and_still_checks_pages_discovery_and_both_gates(
        self,
    ):
        self.catalogue["source_status"][0].update(state="partial", failed_checks=2)
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
            result, output = self.run_main()
        self.assertTrue(result["site_healthy"])
        self.assertEqual(result["catalogue_status"], "degraded")
        self.assertEqual(len(result["source_issues"]), 2)
        self.assertIn("::warning title=Source coverage needs attention::", output)
        self.assertEqual(
            {c.args[0] for c in self.get.call_args_list}, set(self.responses)
        )
        self.assertEqual(
            self.expect_guest_denied.call_args_list[0].args[0],
            health.SITE + "/api/jobs/" + self.listing + "/apply",
        )
        self.assertEqual(
            self.expect_guest_denied.call_args_list[1].args[0],
            health.API + "/catalogue/" + self.listing + "?verify=true",
        )
        self.assertNotIn("test-only-public-key", output)

    def test_complete_coverage_has_no_source_warnings(self):
        self.coverage["last_error"] = None
        self.catalogue["source_status"] = self.catalogue["source_status"][:1]
        result, _ = self.run_main()
        self.assertEqual(result["catalogue_status"], "ok")
        self.assertEqual(result["source_issues"], [])

    def test_missing_stale_naive_and_future_refresh_timestamps_fail(self):
        now = datetime.now(timezone.utc)
        for stamp in [
            None,
            (now - timedelta(hours=25)).isoformat(),
            now.replace(tzinfo=None).isoformat(),
            (now + timedelta(hours=1)).isoformat(),
        ]:
            self.coverage["updated_at"] = stamp
            with self.subTest(stamp=stamp), self.assertRaises(RuntimeError):
                self.run_main()

    def test_real_importer_failure_is_not_downgraded_to_a_source_warning(self):
        self.coverage["last_error"] = (
            "Catalogue collection failed; automatic retry is due in 30 minutes"
        )
        with self.assertRaisesRegex(RuntimeError, "refresh failure"):
            self.run_main()

    def test_missing_source_results_or_total_source_failure_still_fail(self):
        for statuses in [
            [],
            [{"source": "provider", "state": "unavailable", "accepted": 0}],
            [
                {
                    "source": "provider",
                    "state": "partial",
                    "accepted": 0,
                    "failed_checks": 10,
                }
            ],
        ]:
            self.catalogue["source_status"] = statuses
            with self.subTest(statuses=statuses), self.assertRaisesRegex(
                RuntimeError, "No listing source"
            ):
                self.run_main()

    def test_no_current_ghana_jobs_still_fails(self):
        self.catalogue["jobs"] = []
        with self.assertRaisesRegex(RuntimeError, "No current Ghana jobs"):
            self.run_main()

    def test_broken_public_pages_or_discovery_still_fail_with_source_warnings(self):
        for url, invalid in [
            (health.SITE + "/jobs/" + self.listing, "<h1>Missing content</h1>"),
            (health.SITE + "/sitemap.xml", "<urlset/>"),
            (health.SITE + "/robots.txt", "Disallow: /\nSitemap: example"),
        ]:
            original = self.responses[url]
            self.responses[url] = invalid
            try:
                with self.subTest(url=url), self.assertRaises(RuntimeError):
                    self.run_main()
            finally:
                self.responses[url] = original

    def test_lost_apply_protection_still_fails_and_cli_exits_nonzero(self):
        self.expect_guest_denied.side_effect = RuntimeError(
            "Guest Apply protection did not return 401"
        )
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(health.run(), 1)
        self.assertIn("Guest Apply protection", errors.getvalue())

    def test_invalid_listing_ids_never_become_probe_urls(self):
        self.catalogue["jobs"][0]["id"] = "../api/reminders"
        with self.assertRaisesRegex(RuntimeError, "identifier"):
            self.run_main()
        self.assertFalse(
            any(c.args[0].startswith(health.SITE) for c in self.get.call_args_list)
        )

    def test_summary_lists_degraded_sources_and_escapes_workflow_values(self):
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "summary.md"
            with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(destination)}):
                self.run_main()
            text = destination.read_text()
        self.assertIn("**degraded**", text)
        self.assertIn("| provider | unavailable |", text)
        self.assertEqual(
            health.command_text("x%\r\n::error::bad"), "x%25%0D%0A::error::bad"
        )


class GuestProbeTests(unittest.TestCase):
    def probe(self, code=401, headers=None, body=None):
        response = urllib.error.HTTPError(
            "https://site.example/apply",
            code,
            "Synthetic response",
            headers or {"Cache-Control": "private, no-store"},
            io.BytesIO(json.dumps(body or {"detail": "Log in"}).encode()),
        )
        opener = MagicMock()
        opener.open.side_effect = response
        with patch.object(
            health.urllib.request, "build_opener", return_value=opener
        ) as build:
            health.expect_guest_denied("https://site.example/apply")
        self.assertIsInstance(build.call_args.args[0], health.NoRedirect)

    def test_real_401_with_private_cache_control_is_expected(self):
        self.probe()

    def test_redirects_success_cacheable_denials_or_html_fail(self):
        for code, headers, body in [
            (302, None, None),
            (200, None, None),
            (401, {"Cache-Control": "public, max-age=60"}, None),
            (401, None, {"unexpected": True}),
        ]:
            with self.subTest(code=code, headers=headers, body=body), self.assertRaises(
                RuntimeError
            ):
                self.probe(code, headers, body)

    def test_redirect_handler_never_contacts_an_external_posting(self):
        self.assertIsNone(
            health.NoRedirect().redirect_request(
                None, None, 302, "Found", {}, "https://external.example/job"
            )
        )
