"""Employer feed regressions: Ghana eligibility, completeness and safe Apply checks."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException

import catalogue as c
import employer_sources as e


class EmployerSourceTests(unittest.IsolatedAsyncioTestCase):
    def posting(self, **updates):
        job_id = "00000000-0000-0000-0000-000000000001"
        return {
            "id": job_id,
            "title": "Software Engineer",
            "isListed": True,
            "location": "Accra",
            "address": {
                "postalAddress": {"addressLocality": "Accra", "addressCountry": "Ghana"}
            },
            "secondaryLocations": [],
            "descriptionPlain": "Maintain software services and support the engineering team. Work with Python and SQL to improve production systems.",
            "publishedAt": c.NOW().isoformat(),
            "employmentType": "FullTime",
            "jobUrl": f"https://jobs.ashbyhq.com/M-KOPA/{job_id}",
            "applyUrl": f"https://jobs.ashbyhq.com/M-KOPA/{job_id}/application",
            **updates,
        }

    def fido_index(self, country="Ghana"):
        return BeautifulSoup(
            '<div class="careers__career_list_wrapper"><div class="careers__career_list_item">'
            '<a class="careers__career_list_content_wrapper" href="/careers/test-role">Test role</a>'
            f'<div fs-cmsfilter-field="country">{country}</div></div></div>',
            "html.parser",
        )

    def fido_detail(
        self,
        country="Ghana",
        target="https://fidocredit.jh.frappe.cloud/apply?job=HR-OPN-2026-0182",
    ):
        return BeautifulSoup(
            '<h1 class="vacancies-heading1">Accounts Assistant - National Service</h1>'
            f'<div class="vacancies__location">{country}</div><div class="vacancies__rte">'
            "Support the finance team and prepare daily account reconciliations. Maintain records and learn reporting with a supervisor."
            f'</div><a href="{target}">Apply Now</a>',
            "html.parser",
        )

    def test_ashby_secondary_ghana_location_qualifies_without_foreign_regions(self):
        row = self.posting(
            location="Nairobi",
            address={"postalAddress": {"addressCountry": "Kenya"}},
            secondaryLocations=[
                {
                    "location": "Accra",
                    "address": {"addressCountry": "Ghana", "addressLocality": "Accra"},
                }
            ],
            isRemote=True,
            workplaceType="Remote",
        )
        job = e.parse_ashby(row, "M-KOPA")
        self.assertEqual(job["category"], "remote")
        self.assertEqual(job["regions"], ["Greater Accra"])
        self.assertNotIn("Nairobi", job["location"])
        self.assertEqual(job["date_kind"], "source_updated")

    def test_ashby_rejects_foreign_roles_even_when_title_mentions_ghana(self):
        row = self.posting(
            title="Ghana Market Lead",
            location="London",
            address={"postalAddress": {"addressCountry": "GBR"}},
        )
        self.assertIsNone(e.parse_ashby(row, "M-KOPA"))
        self.assertIsNone(e.parse_ashby(self.posting(isListed=False), "M-KOPA"))

    async def test_ashby_empty_feed_is_distinguished_from_changed_or_redirected_feed(
        self,
    ):
        client = AsyncMock()
        url = e.ashby_url("M-KOPA")
        client.get.return_value = httpx.Response(
            200, json={"apiVersion": "1", "jobs": []}, request=httpx.Request("GET", url)
        )
        self.assertEqual(await e.ashby(client, "M-KOPA"), ("ashby:M-KOPA", []))
        for body, returned_url in [
            ({"jobs": []}, url),
            ({"apiVersion": "1", "jobs": [None]}, url),
            ({"apiVersion": "1", "jobs": []}, "https://untrusted.example/feed"),
        ]:
            client.get.return_value = httpx.Response(
                200, json=body, request=httpx.Request("GET", returned_url)
            )
            with self.assertRaises(ValueError):
                await e.ashby(client, "M-KOPA")

    def test_hybrid_is_not_misrepresented_as_fully_remote(self):
        job = e.parse_ashby(
            self.posting(isRemote=True, workplaceType="Hybrid"), "M-KOPA"
        )
        self.assertFalse(job["remote"])
        self.assertEqual(job["category"], "jobs")

    def test_explicit_work_towns_in_title_cover_volta_and_oti(self):
        job = e.parse_ashby(
            self.posting(
                title="Sales Executive - Hohoe-Dambai",
                location="Ghana",
                address={"postalAddress": {"addressCountry": "Ghana"}},
            ),
            "M-KOPA",
        )
        self.assertEqual(job["regions"], ["Volta", "Oti"])
        self.assertEqual(
            c.classify("Senior Engineer (12 month FTC)", "Full-time"), "contract"
        )

    def test_posting_identity_and_application_host_must_match(self):
        for change in [
            {"applyUrl": "https://untrusted.example/apply"},
            {
                "applyUrl": "https://jobs.ashbyhq.com/M-KOPA/00000000-0000-0000-0000-000000000001-other/application"
            },
            {"id": "different-id"},
            {"descriptionPlain": "Incomplete"},
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                e.parse_ashby(self.posting(**change), "M-KOPA")

    def test_fido_uses_role_location_and_national_service_category(self):
        self.assertEqual(e.fido_cards(self.fido_index("South Africa")), [])
        links = e.fido_cards(self.fido_index("Ghana, Uganda, South Africa or Zambia"))
        self.assertEqual(links, ["https://gh.fido.money/careers/test-role"])
        job = e.parse_fido(self.fido_detail(), links[0])
        self.assertEqual(job["category"], "early")
        self.assertIsNone(job["created"])
        self.assertIsNone(job["deadline"])
        self.assertEqual(job["source_url"], links[0])
        self.assertTrue(
            job["url"].startswith("https://fidocredit.jh.frappe.cloud/apply?job=")
        )

    def test_fido_requires_complete_index_and_job_specific_application(self):
        for markup in [
            "<html>Unavailable</html>",
            '<div class="careers__career_list_wrapper"></div>',
        ]:
            with self.assertRaises(ValueError):
                e.fido_cards(BeautifulSoup(markup, "html.parser"))
        self.assertEqual(
            e.fido_cards(
                BeautifulSoup(
                    '<div class="careers__career_list_wrapper"><div class="w-dyn-empty">No items</div></div>',
                    "html.parser",
                )
            ),
            [],
        )
        for target in [
            "https://untrusted.example/apply?job=123",
            "https://fidocredit.jh.frappe.cloud/apply",
        ]:
            with self.assertRaises(ValueError):
                e.parse_fido(
                    self.fido_detail(target=target),
                    "https://gh.fido.money/careers/test-role",
                )

    async def test_apply_closes_only_after_a_complete_index_confirms_removal(self):
        job = e.parse_ashby(self.posting(), "M-KOPA")
        row = {
            "payload": job,
            "status": "active",
            "first_seen_at": c.NOW().isoformat(),
            "last_checked_at": c.NOW().isoformat(),
            "deadline": None,
        }
        for status, body, expected in [
            (200, {"apiVersion": "1", "jobs": []}, 410),
            (200, {"error": "changed format"}, 503),
            (404, {}, 503),
        ]:
            with self.subTest(status=status, expected=expected):
                db = MagicMock()
                db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    row
                ]
                response = MagicMock(status_code=status)
                response.json.return_value = body
                client = AsyncMock()
                client.get.return_value = response
                context = MagicMock()
                context.__aenter__ = AsyncMock(return_value=client)
                context.__aexit__ = AsyncMock(return_value=False)
                with patch.object(c, "supabase", db), patch.object(
                    c.httpx, "AsyncClient", return_value=context
                ):
                    with self.assertRaises(HTTPException) as error:
                        await c.catalogue_details(job["id"], verify=True)
                self.assertEqual(error.exception.status_code, expected)
                if expected == 410:
                    db.table.return_value.update.assert_called_once_with(
                        {"status": "closed"}
                    )
                else:
                    db.table.return_value.update.assert_not_called()

    async def test_fido_apply_rechecks_index_before_detail_and_uses_current_link(self):
        source = "https://gh.fido.money/careers/test-role"
        job = e.parse_fido(self.fido_detail(), source)
        response = MagicMock(text=str(self.fido_index()))
        client = AsyncMock()
        with patch.object(e, "page", return_value=self.fido_detail()) as detail:
            result = await e.recheck(client, job, response)
        self.assertEqual(result["id"], job["id"])
        detail.assert_awaited_once_with(client, source)
        response.text = str(self.fido_index("South Africa"))
        with patch.object(e, "page") as detail:
            self.assertIsNone(await e.recheck(client, job, response))
        detail.assert_not_called()
