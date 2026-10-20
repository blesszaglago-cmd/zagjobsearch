"""Authentication, reminder delivery and conservative source-fact regressions."""

import hashlib
import os
import types
import unittest
from datetime import date
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from starlette.requests import Request
import auth
import sessions
import security
import mailer
import reminders
import account_security
import workspace_api
from listing_quality import salary_facts, deduplicate, enrich


class AuthenticationTests(unittest.TestCase):
    def test_legacy_and_versioned_password_hashes(self):
        password = "test-password-123"
        salt = "test-salt"
        old = (
            salt
            + "$"
            + hashlib.pbkdf2_hmac(
                "sha256", password.encode(), salt.encode(), 100000
            ).hex()
        )
        self.assertTrue(auth.verify_password(password, old))
        new = auth.hash_password(password)
        self.assertTrue(new.startswith("pbkdf2_sha256$600000$"))
        self.assertTrue(auth.verify_password(password, new))
        self.assertFalse(auth.verify_password("wrong", new))
        self.assertFalse(auth.verify_password(password, "!google:unusable"))

    def test_age_terms_and_data_minimisation(self):
        fields = dict(
            full_name="Example User",
            email="EXAMPLE@example.com",
            password="test-password",
            confirm_password="test-password",
            accepted_terms=True,
            age_confirmed=True,
        )
        self.assertIsNone(auth.SignupRequest(**fields).date_of_birth)
        with self.assertRaises(ValueError):
            auth.SignupRequest(**{**fields, "age_confirmed": False})
        with self.assertRaises(ValueError):
            auth.SignupRequest(**{**fields, "accepted_terms": False})

    def test_revocation_rejects_a_copied_signed_token(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {"id": "owner", "session_version": 2}
        ]
        with patch.dict(os.environ, {"SESSION_SECRET": "test-secret"}), patch(
            "database.supabase_client.supabase", db
        ):
            token = sessions.issue_session("owner", 1)
            with self.assertRaises(HTTPException):
                sessions.current_user(
                    HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
                )
            self.assertEqual(
                sessions.current_user(
                    HTTPAuthorizationCredentials(
                        scheme="Bearer", credentials=sessions.issue_session("owner", 2)
                    )
                ),
                "owner",
            )

    def test_rate_limit_rejects_excessive_attempts(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = False
        with patch.object(security, "supabase", db):
            with self.assertRaises(HTTPException) as e:
                security.rate_limit(
                    Request(
                        {"type": "http", "headers": [], "client": ("127.0.0.1", 1)}
                    ),
                    "login",
                )
        self.assertEqual(e.exception.status_code, 429)

    def test_google_requires_a_verified_provider_identity(self):
        db = MagicMock()
        db.auth.get_user.return_value.user = types.SimpleNamespace(
            email="example@example.com",
            email_confirmed_at=None,
            app_metadata={"providers": ["google"]},
        )
        with patch.object(account_security, "supabase", db), patch.object(
            account_security, "rate_limit"
        ):
            with self.assertRaises(HTTPException):
                account_security.google(
                    account_security.GoogleRequest(access_token="x" * 30),
                    Request({"type": "http"}),
                )
        db.table.assert_not_called()

    def test_unconfigured_email_never_claims_delivery(self):
        with patch.object(account_security, "rate_limit"), patch.object(
            account_security, "email_enabled", return_value=False
        ):
            with self.assertRaises(HTTPException) as e:
                account_security.recovery(
                    account_security.EmailRequest(email="example@example.com"),
                    Request({"type": "http"}),
                )
        self.assertEqual(e.exception.status_code, 503)

    def test_google_keeps_existing_workspace_after_profile_email_changes(self):
        db = MagicMock()
        db.auth.get_user.return_value.user = types.SimpleNamespace(
            id="google-owner",
            email="original@example.com",
            email_confirmed_at="2026-10-20",
            app_metadata={"providers": ["google"]},
        )
        db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "workspace-owner",
                "email": "changed@example.com",
                "session_version": 3,
                "onboarding_complete": True,
            }
        ]
        with patch.object(account_security, "supabase", db), patch.object(
            account_security, "rate_limit"
        ), patch.object(account_security, "find_email") as find, patch.object(
            account_security, "issue_session", return_value="signed-session"
        ) as issue:
            result = account_security.google(
                account_security.GoogleRequest(access_token="x" * 30),
                Request({"type": "http"}),
            )
        find.assert_not_called()
        db.table.return_value.insert.assert_not_called()
        issue.assert_called_once_with("workspace-owner", 3)
        self.assertEqual(result["access_token"], "signed-session")


class ReminderTests(unittest.TestCase):
    def test_deadline_changes_update_automatic_reminders(self):
        record = workspace_api.Application(
            job_title="Analyst",
            company_name="Example",
            deadline=date(2026, 11, 20),
            reminder_date=date(2026, 10, 18),
        )
        self.assertEqual(record.record()["reminder_date"], "2026-11-18")
        self.assertEqual(
            record.model_copy(update={"reminder_auto": False}).record()[
                "reminder_date"
            ],
            "2026-10-18",
        )

    def test_delivery_failure_is_not_recorded_as_sent(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = [
            {
                "id": "delivery",
                "dedupe_key": "test:delivery",
                "recipient": "example@example.com",
                "subject": "Reminder",
                "body": "Test",
                "attempts": 1,
            }
        ]
        smtp = MagicMock()
        smtp.send_message.side_effect = RuntimeError("Offline")
        with patch.object(mailer, "supabase", db), patch.object(
            mailer, "email_enabled", return_value=True
        ), patch.dict(
            os.environ,
            {
                "SMTP_HOST": "example",
                "SMTP_FROM": "test@example.com",
                "SMTP_USER": "test",
                "SMTP_PASSWORD": "test",
            },
        ), patch.object(
            mailer.smtplib, "SMTP_SSL", return_value=smtp
        ):
            result = mailer.deliver()
        self.assertEqual(result["sent"], 0)
        self.assertEqual(result["failed"], 1)
        smtp.send_message.assert_called_once()
        self.assertNotIn(
            "sent",
            [
                call.args[0].get("status")
                for call in db.table.return_value.update.call_args_list
            ],
        )

    def test_expired_reminders_are_excluded_before_pagination(self):
        db = MagicMock()
        chain = (
            db.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.lte.return_value.is_.return_value.or_.return_value.order.return_value.range.return_value
        )
        chain.execute.return_value.data = []
        with patch.object(reminders, "supabase", db):
            self.assertEqual(reminders.queue_reminders(), 0)
        db.table.return_value.select.return_value.eq.return_value.eq.return_value.is_.return_value.lte.return_value.is_.return_value.or_.assert_called_once()

    def test_retired_cv_storage_rejects_new_text(self):
        with self.assertRaises(HTTPException) as e:
            workspace_api.save_profile(
                workspace_api.Profile(verified_text="old CV"), "owner"
            )
        self.assertEqual(e.exception.status_code, 410)

    def test_deleted_application_cancels_an_already_queued_email(self):
        db = MagicMock()
        db.rpc.return_value.execute.return_value.data = [
            {
                "id": "delivery",
                "dedupe_key": "deadline:application:2026-10-18",
                "application_id": "application",
                "recipient": "example@example.com",
                "subject": "Reminder",
                "body": "Test",
                "attempts": 1,
            }
        ]
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
            {
                "deleted_at": "2026-10-17T10:00:00Z",
                "status": "started",
                "email_reminder": True,
            }
        ]
        smtp = MagicMock()
        with patch.object(mailer, "supabase", db), patch.object(
            mailer, "email_enabled", return_value=True
        ), patch.dict(
            os.environ,
            {
                "SMTP_HOST": "example",
                "SMTP_FROM": "test@example.com",
                "SMTP_USER": "test",
                "SMTP_PASSWORD": "test",
            },
        ), patch.object(
            mailer.smtplib, "SMTP_SSL", return_value=smtp
        ):
            self.assertEqual(mailer.deliver()["sent"], 0)
        smtp.send_message.assert_not_called()
        self.assertIn(
            "cancelled",
            [
                call.args[0].get("status")
                for call in db.table.return_value.update.call_args_list
            ],
        )

    def test_inverted_salary_range_is_rejected(self):
        with self.assertRaises(ValueError):
            workspace_api.Application(
                job_title="Role",
                company_name="Example",
                salary_min=5000,
                salary_max=1000,
            )


class FactTests(unittest.TestCase):
    def test_salary_requires_source_currency_and_keeps_period(self):
        facts = salary_facts("Salary: GHS 2,400–3,000 gross per month")
        self.assertEqual(
            (
                facts["salary_min"],
                facts["salary_max"],
                facts["salary_currency"],
                facts["salary_period"],
            ),
            (2400, 3000, "GHS", "month"),
        )
        self.assertEqual(salary_facts("Five years experience. Salary negotiable."), {})

    def job(self, id, source="employer", summary=False, **kw):
        return {
            "id": id,
            "source_key": source,
            "source": "Test",
            "title": "Engineer",
            "company": "Example",
            "location": "Accra, Ghana",
            "category": "jobs",
            "url": f"https://example.com/{id}",
            "description_kind": "source_summary" if summary else "full",
            **kw,
        }

    def test_distinct_employer_requisitions_survive_deduplication(self):
        self.assertEqual(
            sum(
                not j.get("duplicate_of")
                for j in deduplicate([self.job("a"), self.job("b")])
            ),
            2,
        )

    def test_cross_source_merge_preserves_deadline_and_its_source(self):
        jobs = deduplicate(
            [self.job("a"), self.job("b", "board", True, deadline="2026-12-01")]
        )
        main = next(j for j in jobs if not j.get("duplicate_of"))
        self.assertEqual(main["deadline"], "2026-12-01")
        self.assertEqual(main["field_sources"]["deadline"], "https://example.com/b")

    def test_source_keywords_survive_shortened_descriptions(self):
        j = enrich(
            self.job("a", experience="unspecified"),
            "Maintain Python and PostgreSQL services. At least 2 years experience required.",
        )
        self.assertIn("Python", j["search_terms"])
        self.assertEqual(j["experience_years_min"], 2)
