"""Public browsing, authenticated Apply checks and safe account continuations."""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

import account_security
import auth
import catalogue
import sessions
from main import app


class ApplyAccountTests(TestCase):
    def setUp(self):
        self.listing_id = "a" * 32
        self.path = "/jobs/" + self.listing_id
        self.database = MagicMock()
        self.database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {
                "payload": {
                    "id": self.listing_id,
                    "category": "jobs",
                    "title": "Test role",
                },
                "status": "active",
                "deadline": None,
                "first_seen_at": datetime.now(timezone.utc).isoformat(),
                "last_checked_at": datetime.now(timezone.utc).isoformat(),
            }
        ]

    def test_guests_can_read_details_without_authentication(self):
        with patch.object(catalogue, "supabase", self.database), patch.object(
            sessions, "current_user"
        ) as authenticate, TestClient(app) as client:
            response = client.get("/catalogue/" + self.listing_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.listing_id)
        authenticate.assert_not_called()

    def test_guest_and_forged_apply_checks_stop_before_source_or_catalogue_access(self):
        with patch.object(catalogue, "supabase", self.database), patch.object(
            catalogue, "source_client"
        ) as source, TestClient(app) as client:
            for headers in [{}, {"Authorization": "Bearer e30." + "a" * 43}]:
                response = client.get(
                    "/catalogue/" + self.listing_id + "?verify=true", headers=headers
                )
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["cache-control"], "no-store")
                self.assertIn("Authorization", response.headers["vary"])
        self.database.table.assert_not_called()
        source.assert_not_called()

    def test_authenticated_apply_reaches_existing_source_validation(self):
        with patch.object(catalogue, "supabase", self.database), patch.object(
            sessions, "current_user", return_value="synthetic-owner"
        ) as authenticate, patch("security.rate_limit"), TestClient(app) as client:
            response = client.get(
                "/catalogue/" + self.listing_id + "?verify=true",
                headers={"Authorization": "Bearer test-only-session"},
            )
        authenticate.assert_called_once()
        self.assertEqual(
            authenticate.call_args.args[0].credentials, "test-only-session"
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("approved source check", response.json()["detail"])
        self.database.table.assert_called_once_with("job_catalogue")

    def test_only_internal_listing_paths_survive_account_forms(self):
        for value in [
            self.path,
            "https://untrusted.example/",
            "//untrusted.example/",
            "/api/reminders",
            "/jobs/" + self.listing_id + "?next=https://untrusted.example/",
            "/jobs/..\\untrusted",
        ]:
            expected = self.path if value == self.path else ""
            self.assertEqual(auth.application_return_path(value), expected)
            request = account_security.EmailRequest(
                email="owner@example.com", next_path=value
            )
            self.assertEqual(request.next_path, expected)

    def test_verification_email_preserves_only_a_safe_listing_path(self):
        for value in [self.path, "https://untrusted.example/"]:
            with patch.object(account_security, "supabase"), patch.object(
                account_security, "email_enabled", return_value=True
            ), patch.object(
                account_security, "enqueue", return_value="test-delivery"
            ) as enqueue, patch.object(
                account_security, "deliver", return_value={"sent": 1}
            ), patch.dict(
                "os.environ", {"FRONTEND_URL": "https://site.example"}
            ):
                account_security.send_account_link(
                    {
                        "id": "synthetic-owner",
                        "email": "owner@example.com",
                        "session_version": 1,
                    },
                    "verify",
                    next_path=value,
                )
            body = enqueue.call_args.args[3]
            link = next(
                line
                for line in body.splitlines()
                if line.startswith("https://site.example/verify-email")
            )
            parsed = urlsplit(link)
            self.assertEqual(
                parse_qs(parsed.query).get("next"),
                [self.path] if value == self.path else None,
            )
            self.assertEqual(parse_qs(parsed.fragment)["purpose"], ["verify"])
            self.assertNotIn("untrusted.example", body)
