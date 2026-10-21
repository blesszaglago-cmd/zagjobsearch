"""Gmail HTTP boundary and queue safety, using synthetic credentials and mail."""

import base64
import json
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs

import httpx

import gmail_transport
import mailer


ENV = {
    "EMAIL_PROVIDER": "gmail_api",
    "EMAIL_FROM": "jobs.ac.ghana <sender@example.com>",
    "GMAIL_OAUTH_CLIENT_ID": "unit-client.apps.googleusercontent.com",
    "GMAIL_OAUTH_CLIENT_SECRET": "unit-client-secret",
    "GMAIL_REFRESH_TOKEN": "unit-refresh-token",
}


def token_response(**changes):
    return {
        "access_token": "unit-access-token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": gmail_transport.SEND_SCOPE,
        **changes,
    }


def queued(**changes):
    return {
        "id": "delivery-1",
        "dedupe_key": "search:search-1:run-1",
        "user_id": "owner-1",
        "recipient": "recipient@example.com",
        "subject": "New Ghana roles: école",
        "body": "Review your saved Accra search. Études and opportunities.",
        "attempts": 1,
        **changes,
    }


def database(items, **rows):
    data = {
        "profiles": [
            {"email": "recipient@example.com", "email_verified_at": "2026-01-01"}
        ],
        "saved_searches": [{"email_alert": True}],
        **rows,
    }
    db, updates, tables = MagicMock(), [], {}
    db.rpc.return_value.execute.return_value.data = items

    def table(name):
        if name not in tables:
            chain = MagicMock()
            for method in ("select", "eq", "in_"):
                getattr(chain, method).return_value = chain
            chain.execute.return_value = SimpleNamespace(data=data.get(name, []))

            def update(payload):
                updates.append((name, payload))
                return chain

            chain.update.side_effect = update
            tables[name] = chain
        return tables[name]

    db.table.side_effect = table
    return db, updates


class GmailTransportTests(unittest.TestCase):
    @contextmanager
    def transport(self, handler=None):
        requests = []

        def respond(request):
            requests.append(request)
            if handler:
                response = handler(request)
                if response is not None:
                    return response
            if str(request.url) == gmail_transport.TOKEN_URL:
                return httpx.Response(200, json=token_response())
            self.assertEqual(str(request.url), gmail_transport.SEND_URL)
            return httpx.Response(200, json={"id": "accepted-message"})

        client = httpx.Client(transport=httpx.MockTransport(respond))
        with patch.dict(os.environ, ENV), patch.object(
            gmail_transport.httpx, "Client", return_value=client
        ) as factory, patch.object(mailer, "open_smtp") as smtp:
            try:
                yield requests, factory, smtp
            finally:
                client.close()

    def test_authentication_probe_refreshes_privately_without_sending(self):
        with self.transport() as (requests, factory, smtp):
            self.assertEqual(
                mailer.check_email_connection(),
                {"configured": True, "authenticated": True},
            )
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), gmail_transport.TOKEN_URL)
        self.assertEqual(
            parse_qs(requests[0].content.decode()),
            {
                "grant_type": ["refresh_token"],
                "client_id": [ENV["GMAIL_OAUTH_CLIENT_ID"]],
                "client_secret": [ENV["GMAIL_OAUTH_CLIENT_SECRET"]],
                "refresh_token": [ENV["GMAIL_REFRESH_TOKEN"]],
            },
        )
        self.assertNotIn("authorization", requests[0].headers)
        self.assertTrue(factory.call_args.kwargs["verify"])
        self.assertFalse(factory.call_args.kwargs["follow_redirects"])
        self.assertFalse(factory.call_args.kwargs["trust_env"])
        self.assertEqual(factory.call_args.kwargs["timeout"], 8.0)
        smtp.assert_not_called()

    def test_authentication_probe_reports_only_allowlisted_oauth_errors(self):
        private = " ".join(ENV.values()) + " unit-access-token"
        cases = [
            (
                httpx.Response(
                    400,
                    json={"error": "invalid_grant", "error_description": private},
                ),
                "invalid_grant",
            ),
            (
                httpx.Response(
                    401,
                    json={"error": "invalid_client", "error_description": private},
                ),
                "invalid_client",
            ),
            (httpx.Response(400, json={"error": private}), None),
            (
                httpx.Response(
                    400, json={"error": {"code": "invalid_grant", "detail": private}}
                ),
                None,
            ),
            (httpx.Response(400, json=["invalid_grant", private]), None),
            (httpx.Response(400, text=private), None),
        ]
        for response, code in cases:
            with self.subTest(status=response.status_code, code=code):
                with self.transport(lambda request: response) as (requests, _, smtp):
                    result = mailer.check_email_connection()
                expected = {
                    "configured": True,
                    "authenticated": False,
                    "problem": "gmail_api_authentication_failed",
                    "error_type": "GmailTransportError",
                    "http_status": response.status_code,
                }
                if code:
                    expected["oauth_error"] = code
                self.assertEqual(result, expected)
                self.assertEqual(
                    [str(request.url) for request in requests],
                    [gmail_transport.TOKEN_URL],
                )
                for secret in (
                    ENV["GMAIL_OAUTH_CLIENT_SECRET"],
                    ENV["GMAIL_REFRESH_TOKEN"],
                    "unit-access-token",
                ):
                    self.assertNotIn(secret, json.dumps(result))
                smtp.assert_not_called()

    def test_unicode_mime_and_token_reuse_for_two_accepted_queue_messages(self):
        first, second = queued(), queued(id="delivery-2")
        db, updates = database([first, second])
        with self.transport() as (requests, _, smtp), patch.object(
            mailer, "supabase", db
        ):
            self.assertEqual(
                mailer.deliver(), {"sent": 2, "failed": 0, "configured": True}
            )
        self.assertEqual(len(requests), 3)
        self.assertEqual(
            sum(str(r.url) == gmail_transport.TOKEN_URL for r in requests), 1
        )
        for request, item in zip(requests[1:], [first, second]):
            self.assertEqual(request.headers["authorization"], "Bearer unit-access-token")
            payload = json.loads(request.content)
            message = BytesParser(policy=policy.default).parsebytes(
                base64.urlsafe_b64decode(payload["raw"])
            )
            self.assertEqual(str(message["To"]), item["recipient"])
            self.assertEqual(message["From"].addresses[0].addr_spec, "sender@example.com")
            self.assertEqual(message["From"].addresses[0].display_name, "jobs.ac.ghana")
            self.assertEqual(str(message["Subject"]), item["subject"])
            self.assertEqual(str(message["Message-ID"]), f"<{item['id']}@jobs-ac-ghana>")
            self.assertEqual(message.get_content().strip(), item["body"])
        self.assertEqual(
            [p["status"] for name, p in updates if name == "email_outbox"],
            ["sent", "sent"],
        )
        smtp.assert_not_called()

    def test_provider_errors_are_redacted_and_never_marked_sent(self):
        cases = [
            (
                gmail_transport.TOKEN_URL,
                httpx.Response(400, json={"error": "private-provider-detail"}),
                "gmail_api_authentication_failed",
            ),
            (
                gmail_transport.SEND_URL,
                httpx.Response(403, json={"error": "private-provider-detail"}),
                "gmail_api_send_rejected",
            ),
            (
                gmail_transport.SEND_URL,
                httpx.Response(429, text="private-provider-detail"),
                "gmail_api_send_rejected",
            ),
            (
                gmail_transport.SEND_URL,
                httpx.Response(503, text="private-provider-detail"),
                "gmail_api_send_rejected",
            ),
            (
                gmail_transport.TOKEN_URL,
                httpx.Response(302, headers={"Location": "https://example.com/leak"}),
                "gmail_api_authentication_failed",
            ),
            (
                gmail_transport.SEND_URL,
                httpx.Response(200, json={}),
                "gmail_api_invalid_response",
            ),
        ]
        for url, response, expected in cases:
            with self.subTest(url=url, status=response.status_code):
                def handler(request):
                    return response if str(request.url) == url else None

                db, updates = database([queued()])
                with self.transport(handler) as (requests, _, smtp), patch.object(
                    mailer, "supabase", db
                ), self.assertLogs(level="WARNING") as logs:
                    result = mailer.deliver()
                self.assertEqual(result["sent"], 0)
                self.assertEqual(result["failed"], 1)
                self.assertEqual(updates[-1][1]["status"], "failed")
                self.assertIn(expected, updates[-1][1]["last_error"])
                self.assertNotIn("sent_at", updates[-1][1])
                safe = json.dumps([result, updates, logs.output])
                for private in [
                    ENV["GMAIL_OAUTH_CLIENT_SECRET"],
                    ENV["GMAIL_REFRESH_TOKEN"],
                    "unit-access-token",
                    "private-provider-detail",
                    queued()["body"],
                ]:
                    self.assertNotIn(private, safe)
                self.assertTrue(
                    all(
                        str(r.url)
                        in {gmail_transport.TOKEN_URL, gmail_transport.SEND_URL}
                        for r in requests
                    )
                )
                smtp.assert_not_called()

    def test_malformed_token_responses_and_broader_scopes_fail_closed(self):
        payloads = [
            [],
            token_response(access_token=""),
            token_response(access_token="bad\r\ntoken"),
            token_response(expires_in=True),
            token_response(expires_in=0),
            token_response(token_type="other"),
            token_response(
                scope=gmail_transport.SEND_SCOPE
                + " https://www.googleapis.com/auth/gmail.readonly"
            ),
        ]
        for payload in payloads:
            with self.subTest(payload=payload), self.transport(
                lambda request: httpx.Response(200, json=payload)
            ) as (requests, _, smtp):
                result = mailer.check_email_connection()
                self.assertFalse(result["authenticated"])
                self.assertEqual(len(requests), 1)
                smtp.assert_not_called()

    def test_non_json_and_network_failures_are_private(self):
        for failure, expected in [
            (
                httpx.Response(200, text="private-provider-detail"),
                "gmail_api_invalid_response",
            ),
            (httpx.ReadTimeout("private-provider-detail"), "gmail_api_timeout"),
            (
                httpx.ConnectError("private-provider-detail"),
                "gmail_api_connection_failed",
            ),
        ]:
            def handler(request):
                if isinstance(failure, Exception):
                    raise failure
                return failure

            with self.subTest(expected=expected), self.transport(handler):
                result = mailer.check_email_connection()
            self.assertEqual(result["problem"], expected)
            self.assertNotIn("private-provider-detail", str(result))

    def test_missing_credentials_unknown_provider_and_smtp_port_never_fall_back(self):
        for changed in [
            {"GMAIL_REFRESH_TOKEN": " "},
            {"GMAIL_OAUTH_CLIENT_SECRET": ""},
            {"EMAIL_PROVIDER": "misspelled"},
        ]:
            db = MagicMock()
            with (
                self.subTest(changed=changed),
                self.transport() as (requests, _, smtp),
                patch.dict(os.environ, changed),
                patch.object(mailer, "supabase", db),
            ):
                self.assertFalse(mailer.email_enabled())
                self.assertFalse(mailer.deliver()["configured"])
                self.assertFalse(mailer.check_email_connection()["authenticated"])
                self.assertEqual(requests, [])
                db.rpc.assert_not_called()
                smtp.assert_not_called()
        with self.transport() as (requests, _, smtp):
            self.assertEqual(
                mailer.check_email_connection(587)["problem"],
                "gmail_api_smtp_port_not_applicable",
            )
            self.assertEqual(requests, [])
            smtp.assert_not_called()

    def test_obsolete_or_unconsented_queue_items_are_cancelled_without_sending(self):
        cases = [
            (queued(expires_at="2000-01-01T00:00:00Z"), {}),
            (queued(expires_at="invalid"), {}),
            (
                queued(dedupe_key="account:hash"),
                {
                    "account_tokens": [
                        {"used_at": None, "expires_at": "2000-01-01T00:00:00Z"}
                    ]
                },
            ),
            (
                queued(dedupe_key="account:hash"),
                {
                    "account_tokens": [
                        {"used_at": "2026-01-01", "expires_at": "2099-01-01T00:00:00Z"}
                    ]
                },
            ),
            (
                queued(application_id="application-1"),
                {"applications": [{"deleted_at": "2026-01-01"}]},
            ),
            (
                queued(),
                {
                    "profiles": [
                        {"email": "recipient@example.com", "email_verified_at": None}
                    ]
                },
            ),
            (
                queued(),
                {
                    "profiles": [
                        {"email": "changed@example.com", "email_verified_at": "2026-01-01"}
                    ]
                },
            ),
            (queued(), {"saved_searches": [{"email_alert": False}]}),
        ]
        for item, rows in cases:
            db, updates = database([item], **rows)
            with (
                self.subTest(item=item, rows=rows),
                self.transport() as (requests, _, _),
                patch.object(mailer, "supabase", db),
            ):
                self.assertEqual(
                    mailer.deliver(), {"sent": 0, "failed": 0, "configured": True}
                )
            self.assertTrue(
                all(str(r.url) == gmail_transport.TOKEN_URL for r in requests)
            )
            self.assertEqual(updates[-1][1]["status"], "cancelled")

    def test_link_expiring_during_queue_checks_is_cancelled(self):
        before = datetime.now(timezone.utc)
        after = before + timedelta(seconds=2)
        db, updates = database(
            [queued(expires_at=(before + timedelta(seconds=1)).isoformat())]
        )
        with (
            self.transport() as (requests, _, _),
            patch.object(mailer, "supabase", db),
            patch.object(mailer, "datetime", wraps=datetime) as clock,
        ):
            clock.now.side_effect = [before, after]
            self.assertEqual(mailer.deliver()["sent"], 0)
        self.assertEqual(len(requests), 1)
        self.assertEqual(updates[-1][1]["status"], "cancelled")

    def test_access_token_refreshes_before_expiry_without_storing_a_token_file(self):
        now, refreshes = [0], [0]

        def handler(request):
            if str(request.url) == gmail_transport.TOKEN_URL:
                refreshes[0] += 1
                return httpx.Response(
                    200,
                    json=token_response(
                        access_token=f"unit-access-{refreshes[0]}", expires_in=31
                    ),
                )
            now[0] += 2
            return None

        message = EmailMessage()
        message["To"] = "recipient@example.com"
        message["From"] = ENV["EMAIL_FROM"]
        message.set_content("Synthetic test")
        with self.transport(handler) as (requests, _, _), patch.object(
            gmail_transport.time, "monotonic", side_effect=lambda: now[0]
        ):
            connection = gmail_transport.GmailTransport()
            connection.send_message(message)
            connection.send_message(message)
            connection.quit()
            self.assertIsNone(connection._access_token)
        self.assertEqual(refreshes[0], 2)
        self.assertEqual(
            [
                r.headers["authorization"]
                for r in requests
                if str(r.url) == gmail_transport.SEND_URL
            ],
            ["Bearer unit-access-1", "Bearer unit-access-2"],
        )


if __name__ == "__main__":
    unittest.main()
