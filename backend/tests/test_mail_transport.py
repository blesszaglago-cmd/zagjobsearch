"""Real transport boundaries: TLS, credential formatting and private diagnostics."""

import os
import smtplib
import ssl
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import mailer
import operations


class MailTransportTests(unittest.TestCase):
    def test_google_grouped_password_uses_verified_tls(self):
        smtp = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_PORT": "465",
                "SMTP_USER": "sender@example.com",
                "SMTP_PASSWORD": "abcd efgh ijkl mnop\n",
            },
        ), patch.object(mailer.smtplib, "SMTP_SSL", return_value=smtp) as factory:
            self.assertIs(mailer.open_smtp(), smtp)
        smtp.login.assert_called_once_with("sender@example.com", "abcdefghijklmnop")
        context = factory.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_other_provider_password_spaces_are_preserved(self):
        smtp = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.example.com",
                "SMTP_USER": "sender@example.com",
                "SMTP_PASSWORD": "abcd efgh ijkl mnop",
            },
        ), patch.object(mailer.smtplib, "SMTP_SSL", return_value=smtp):
            mailer.open_smtp()
        smtp.login.assert_called_once_with("sender@example.com", "abcd efgh ijkl mnop")

    def test_auth_failure_exposes_code_without_provider_reply(self):
        smtp = MagicMock()
        smtp.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b"provider response with confidential-value"
        )
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_USER": "sender@example.com",
                "SMTP_PASSWORD": "abcdefghijklmnop",
                "SMTP_FROM": "sender@example.com",
            },
        ), patch.object(mailer.smtplib, "SMTP_SSL", return_value=smtp):
            result = mailer.check_email_connection()
        self.assertEqual(
            result,
            {
                "configured": True,
                "authenticated": False,
                "problem": "smtp_authentication_failed",
                "error_type": "SMTPAuthenticationError",
                "smtp_code": 535,
            },
        )
        smtp.close.assert_called_once()
        smtp.send_message.assert_not_called()

    def test_successful_check_does_not_send_mail(self):
        smtp = MagicMock()
        with patch.object(mailer, "email_enabled", return_value=True), patch.object(
            mailer, "open_smtp", return_value=smtp
        ):
            self.assertTrue(mailer.check_email_connection()["authenticated"])
        smtp.send_message.assert_not_called()
        smtp.quit.assert_called_once()

    def test_network_failure_retains_errno_without_raw_error(self):
        with patch.object(mailer, "email_enabled", return_value=True), patch.object(
            mailer,
            "open_smtp",
            side_effect=ConnectionRefusedError(111, "private detail"),
        ):
            result = mailer.check_email_connection()
        self.assertEqual(result["error_type"], "ConnectionRefusedError")
        self.assertEqual(result["errno"], 111)
        self.assertNotIn("private detail", str(result))

    def test_starttls_must_succeed_before_credentials_are_sent(self):
        smtp = MagicMock()
        smtp.starttls.side_effect = smtplib.SMTPNotSupportedError("No TLS")
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_USER": "sender@example.com",
                "SMTP_PASSWORD": "abcdefghijklmnop",
            },
        ), patch.object(mailer.smtplib, "SMTP", return_value=smtp):
            with self.assertRaises(smtplib.SMTPNotSupportedError):
                mailer.open_smtp(587)
        smtp.login.assert_not_called()
        smtp.close.assert_called_once()

    def test_starttls_uses_verified_tls_before_login(self):
        smtp = MagicMock()
        with patch.dict(
            os.environ,
            {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_USER": "sender@example.com",
                "SMTP_PASSWORD": "abcdefghijklmnop",
            },
        ), patch.object(mailer.smtplib, "SMTP", return_value=smtp):
            mailer.open_smtp(587)
        context = smtp.starttls.call_args.kwargs["context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(
            [call[0] for call in smtp.method_calls],
            ["ehlo", "starttls", "ehlo", "login"],
        )

    def test_public_request_cannot_probe_email_credentials(self):
        app = FastAPI()
        app.include_router(operations.router)
        with patch.object(operations, "check_email_connection") as probe:
            response = TestClient(app).get("/cron/email-status")
        self.assertEqual(response.status_code, 401)
        probe.assert_not_called()

    def test_authorized_check_accepts_only_the_supported_tls_ports(self):
        app = FastAPI()
        app.include_router(operations.router)
        with patch.object(operations, "require_cron"), patch.object(
            operations, "check_email_connection", return_value={"authenticated": True}
        ) as probe:
            client = TestClient(app)
            self.assertEqual(client.get("/cron/email-status?port=587").status_code, 200)
            probe.assert_called_once_with(587)
            probe.reset_mock()
            self.assertEqual(client.get("/cron/email-status?port=25").status_code, 422)
            probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
