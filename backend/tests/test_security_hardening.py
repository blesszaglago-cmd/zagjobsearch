"""Adversarial inputs use synthetic identities and in-memory provider responses."""

import asyncio
import gzip
import hashlib
import hmac
import json
import os
import socket
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpcore
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import account_security
import auth
from main import app, auth_config
import public_http
import security
import sessions
import workspace_api
import saved_searches
from postgrest import SyncPostgrestClient


class PublicFetchTests(unittest.IsolatedAsyncioTestCase):
    async def test_apply_without_an_approved_verification_endpoint_fails_closed(self):
        import catalogue

        for check in [
            None,
            "https://attacker.example/",
            "http://api.smartrecruiters.com/",
        ]:
            job = {"id": "a" * 32, "category": "jobs", "check_url": check}
            row = {
                "payload": job,
                "status": "active",
                "deadline": None,
                "first_seen_at": catalogue.NOW().isoformat(),
                "last_checked_at": catalogue.NOW().isoformat(),
            }
            database = MagicMock()
            database.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                row
            ]
            with patch.object(catalogue, "supabase", database), patch.object(
                catalogue, "source_client"
            ) as source:
                with self.subTest(check=check), self.assertRaises(
                    HTTPException
                ) as error:
                    await catalogue.catalogue_details(job["id"], verify=True)
                self.assertEqual(error.exception.status_code, 503)
                source.assert_not_called()

    async def test_untrusted_destinations_are_rejected_before_transport(self):
        transport = MagicMock()
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport)
        ) as client:
            reader = public_http.PublicSourceClient(client)
            for target in [
                "http://api.smartrecruiters.com/",
                "https://127.0.0.1/",
                "https://169.254.169.254/latest/",
                "https://api.smartrecruiters.com.attacker.example/",
                "https://user:password@api.smartrecruiters.com/",
                "https://api.smartrecruiters.com:8443/",
                "https://api.smartrecruiters.com/#fragment",
                "https://api.smartrecruiters.com/\r\nX-Test:bad",
            ]:
                with self.subTest(target=target), self.assertRaises(ValueError):
                    await reader.get(target)
        transport.assert_not_called()

    async def test_redirect_to_internal_or_another_host_is_never_contacted(self):
        for destination in [
            "https://127.0.0.1/",
            "http://api.smartrecruiters.com/",
            "https://www.ug.edu.gh/",
            "https://attacker.example/",
        ]:
            requests = []

            def respond(request):
                requests.append(str(request.url))
                return httpx.Response(302, headers={"Location": destination})

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(respond), follow_redirects=True
            ) as client:
                with self.subTest(destination=destination), self.assertRaises(
                    ValueError
                ):
                    await public_http.PublicSourceClient(client).get(
                        "https://api.smartrecruiters.com/start"
                    )
            self.assertEqual(requests, ["https://api.smartrecruiters.com/start"])

    async def test_same_host_redirect_and_json_encoding_are_preserved(self):
        requests = []

        def respond(request):
            requests.append(str(request.url))
            if request.url.path == "/start":
                return httpx.Response(301, headers={"Location": "/result"})
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                stream=httpx.ByteStream(b'{"ok":true}'),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            response = await public_http.PublicSourceClient(client).get(
                "https://api.smartrecruiters.com/start"
            )
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(str(response.url), "https://api.smartrecruiters.com/result")
        self.assertEqual(len(requests), 2)

    async def test_redirect_loop_is_bounded(self):
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(302, headers={"Location": "/loop"})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            with self.assertRaisesRegex(ValueError, "redirect limit"):
                await public_http.PublicSourceClient(client).get(
                    "https://api.smartrecruiters.com/loop"
                )
        self.assertEqual(len(requests), 6)

    async def test_size_cap_applies_to_chunked_and_compressed_responses(self):
        for headers, content in [
            ({}, b"a" * 101),
            ({"content-length": "999999999"}, b"a"),
            ({"content-encoding": "gzip"}, gzip.compress(b"a" * 10000)),
        ]:

            def respond(request):
                return httpx.Response(
                    200, headers=headers, stream=httpx.ByteStream(content)
                )

            async with httpx.AsyncClient(
                transport=httpx.MockTransport(respond)
            ) as client:
                with self.subTest(headers=headers), self.assertRaisesRegex(
                    ValueError, "too large"
                ):
                    await public_http.PublicSourceClient(client, max_bytes=100).get(
                        "https://api.smartrecruiters.com/data"
                    )

    async def test_valid_gzip_is_decoded_once(self):
        def respond(request):
            return httpx.Response(
                200,
                headers={"content-encoding": "gzip"},
                stream=httpx.ByteStream(gzip.compress(b'{"title":"Analyst"}')),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            response = await public_http.PublicSourceClient(client).get(
                "https://api.smartrecruiters.com/data"
            )
        self.assertEqual(response.json(), {"title": "Analyst"})
        self.assertNotIn("content-encoding", response.headers)

    async def test_private_dns_answers_never_reach_tcp(self):
        for address in [
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "::1",
            "::ffff:127.0.0.1",
            "64:ff9b::a00:1",
        ]:
            backend = public_http.PublicNetworkBackend()
            backend.backend = AsyncMock()
            with patch.object(
                asyncio.get_running_loop(),
                "getaddrinfo",
                AsyncMock(
                    return_value=[
                        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
                    ]
                ),
            ):
                with self.subTest(address=address), self.assertRaises(
                    httpcore.ConnectError
                ):
                    await backend.connect_tcp("api.smartrecruiters.com", 443, timeout=1)
            backend.backend.connect_tcp.assert_not_called()

    async def test_connect_uses_the_validated_address_without_a_second_dns_lookup(self):
        backend = public_http.PublicNetworkBackend()
        backend.backend = AsyncMock()
        with patch.object(
            asyncio.get_running_loop(),
            "getaddrinfo",
            AsyncMock(
                return_value=[
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
                ]
            ),
        ) as resolve:
            await backend.connect_tcp("api.smartrecruiters.com", 443, timeout=1)
        resolve.assert_awaited_once()
        self.assertEqual(
            backend.backend.connect_tcp.call_args.args[:2], ("8.8.8.8", 443)
        )

    async def test_transport_keeps_original_tls_hostname_when_connecting_to_a_pinned_ip(
        self,
    ):
        class TLSStream(httpcore.AsyncMockStream):
            async def start_tls(self, ssl_context, server_hostname=None, timeout=None):
                self.server_hostname = server_hostname
                self.ssl_context = ssl_context
                return self

        stream = TLSStream(
            [b'HTTP/1.1 200 OK\r\nContent-Length: 11\r\n\r\n{"ok":true}']
        )
        backend = public_http.PublicNetworkBackend()
        backend.backend = AsyncMock()
        backend.backend.connect_tcp.return_value = stream
        with patch.object(
            asyncio.get_running_loop(),
            "getaddrinfo",
            AsyncMock(
                return_value=[
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))
                ]
            ),
        ):
            async with httpx.AsyncClient(
                transport=public_http.SourceTransport(backend)
            ) as client:
                response = await public_http.PublicSourceClient(client).get(
                    "https://api.smartrecruiters.com/data"
                )
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(stream.server_hostname, "api.smartrecruiters.com")
        self.assertTrue(stream.ssl_context.check_hostname)


class AccountBoundaryTests(unittest.TestCase):
    def test_cross_account_http_requests_cannot_read_edit_delete_or_restore_another_record(
        self,
    ):
        owner = "00000000-0000-0000-0000-000000000001"
        other_record = "00000000-0000-0000-0000-000000000002"
        requests = []

        def respond(request):
            requests.append(request)
            if request.url.path.endswith("/profiles"):
                self.assertEqual(request.url.params.get("id"), "eq." + owner)
                return httpx.Response(200, json=[{"id": owner, "session_version": 1}])
            self.assertEqual(request.url.params.get("user_id"), "eq." + owner)
            return httpx.Response(200, json=[])

        with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
            database = SyncPostgrestClient(
                "https://database.example/rest/v1", http_client=transport
            )
            with patch("database.supabase_client.supabase", database), patch.object(
                workspace_api, "supabase", database
            ), patch.object(saved_searches, "supabase", database), patch.object(
                security, "rate_limit"
            ):
                client = TestClient(app)
                headers = {"Authorization": "Bearer " + sessions.issue_session(owner)}
                for method, path, body in [
                    (
                        "PUT",
                        f"/account/applications/{other_record}",
                        {"job_title": "Role", "company_name": "Example"},
                    ),
                    ("DELETE", f"/account/applications/{other_record}", None),
                    ("POST", f"/account/applications/{other_record}/restore", None),
                    ("GET", f"/account/applications/{other_record}/events", None),
                    ("DELETE", f"/account/saved-searches/{other_record}", None),
                ]:
                    with self.subTest(path=path, method=method):
                        self.assertEqual(
                            client.request(
                                method, path, headers=headers, json=body
                            ).status_code,
                            404,
                        )
        self.assertEqual(len(requests), 10)

    def test_application_owner_is_taken_from_the_session_not_a_submitted_user_id(self):
        owner = "00000000-0000-0000-0000-000000000001"
        inserted = []

        def respond(request):
            if request.url.path.endswith("/profiles"):
                return httpx.Response(
                    200,
                    json=[
                        {"id": owner, "session_version": 1, "onboarding_complete": True}
                    ],
                )
            self.assertEqual(request.method, "POST")
            record = json.loads(request.content)
            inserted.append(record)
            return httpx.Response(201, json=[{"id": "synthetic-record", **record}])

        with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
            database = SyncPostgrestClient(
                "https://database.example/rest/v1", http_client=transport
            )
            with patch("database.supabase_client.supabase", database), patch.object(
                workspace_api, "supabase", database
            ), patch.object(security, "rate_limit"):
                response = TestClient(app).post(
                    "/account/applications",
                    headers={
                        "Authorization": "Bearer " + sessions.issue_session(owner)
                    },
                    json={
                        "job_title": "Role",
                        "company_name": "Example",
                        "user_id": "attacker-selected-owner",
                    },
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(inserted[0]["user_id"], owner)

    def test_recovery_delivery_failures_cannot_reveal_whether_an_address_exists(self):
        replies = []
        with patch.object(account_security, "rate_limit"), patch.object(
            account_security, "email_enabled", return_value=True
        ), patch.object(
            account_security,
            "send_account_link",
            side_effect=RuntimeError("private-provider-detail"),
        ):
            for result in [None, {"id": "synthetic-owner"}]:
                with patch.object(account_security, "find_email", return_value=result):
                    response = TestClient(app).post(
                        "/auth/recovery", json={"email": "owner@example.com"}
                    )
                self.assertEqual(response.status_code, 200)
                replies.append(response.json())
        self.assertEqual(replies[0], replies[1])
        self.assertNotIn("private-provider-detail", str(replies))

    def test_oversized_and_compressed_requests_never_reach_authentication(self):
        with patch("main.login_user") as login:
            client = TestClient(app)
            large = client.post(
                "/login",
                content=b"x" * 65537,
                headers={"content-type": "application/json"},
            )
            self.assertEqual(large.status_code, 413)
            chunked = client.post(
                "/login",
                content=iter([b"x" * 32000, b"y" * 34000]),
                headers={"content-type": "application/json"},
            )
            self.assertEqual(chunked.status_code, 413)
            compressed = client.post(
                "/login",
                content=gzip.compress(b"{}"),
                headers={
                    "content-type": "application/json",
                    "content-encoding": "gzip",
                },
            )
            self.assertEqual(compressed.status_code, 415)
            for response in [large, chunked, compressed]:
                self.assertEqual(response.headers["cache-control"], "no-store")
            login.assert_not_called()

    def test_forged_and_oversized_sessions_cannot_query_private_data(self):
        with patch("database.supabase_client.supabase") as database:
            client = TestClient(app)
            for token in [
                "not-a-session",
                "x" * 10000,
                sessions.issue_session("test-owner")[:-1] + "X",
            ]:
                response = client.get(
                    "/account/applications",
                    headers={"authorization": "Bearer " + token},
                )
                self.assertEqual(response.status_code, 401)
            database.table.assert_not_called()

    def test_signed_but_expired_wrong_audience_and_invalid_claims_are_rejected(self):
        for change in [
            {"exp": 1},
            {"aud": "another-app"},
            {"v": True},
            {"exp": "tomorrow"},
            {"iat": int(time.time()) + 3600},
        ]:
            claims = {
                "sub": "test-owner",
                "aud": "zagjobsearch",
                "v": 1,
                "iat": int(time.time()),
                "exp": int(time.time()) + 43200,
                **change,
            }
            payload = sessions.encode(json.dumps(claims).encode())
            signature = sessions.encode(
                hmac.new(
                    sessions.signing_key(), payload.encode(), hashlib.sha256
                ).digest()
            )
            with self.subTest(change=change), self.assertRaises(HTTPException):
                sessions.verify_session(payload + "." + signature)

    def test_administrative_key_cannot_escape_through_public_configuration(self):
        for key in [
            "sb_secret_test_only_private_administrative_key",
            sessions.encode(b"{}")
            + "."
            + sessions.encode(b'{"role":"service_role"}')
            + ".signature",
        ]:
            with patch.dict(
                os.environ,
                {"SUPABASE_PUBLISHABLE_KEY": key, "GOOGLE_AUTH_ENABLED": "true"},
            ):
                result = auth_config()
            self.assertEqual(result["publishable_key"], "")
            self.assertFalse(result["google_enabled"])

    def test_google_binding_uses_verified_server_identity_and_never_a_client_user_id(
        self,
    ):
        database = MagicMock()
        from types import SimpleNamespace

        database.auth.get_user.return_value.user = SimpleNamespace(
            id="provider-owner",
            email="owner@example.com",
            email_confirmed_at="2026-10-23",
            app_metadata={"providers": ["google"]},
            user_metadata={"full_name": "Owner"},
        )
        database.rpc.return_value.execute.return_value.data = {
            "id": "workspace-owner",
            "session_version": 2,
            "onboarding_complete": True,
        }
        with patch.object(account_security, "supabase", database), patch.object(
            account_security, "rate_limit"
        ), patch.object(
            account_security, "issue_session", return_value="session"
        ) as issue:
            account_security.google(
                account_security.GoogleRequest(access_token="x" * 30),
                Request({"type": "http"}),
            )
        function, fields = database.rpc.call_args.args
        self.assertEqual(function, "bind_google_account")
        self.assertEqual(
            (fields["provider_id"], fields["verified_email"]),
            ("provider-owner", "owner@example.com"),
        )
        self.assertRegex(fields["unusable_password_hash"], r"^!google:[a-f0-9]{64}$")
        database.table.assert_not_called()
        issue.assert_called_once_with("workspace-owner", 2)

    def test_forged_ip_headers_do_not_change_the_rate_limit_identity(self):
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/login",
                "headers": [
                    (b"x-forwarded-for", b"1.2.3.4"),
                    (b"x-vercel-forwarded-for", b"5.6.7.8"),
                    (b"x-zag-client-ip", b"9.8.7.6"),
                ],
                "client": ("127.0.0.2", 1),
            }
        )
        with patch.dict(
            os.environ, {"VERCEL": "", "INTERNAL_PROXY_SECRET": "test-only-secret"}
        ):
            self.assertEqual(security.client_address(request), ("127.0.0.2", False))

    def test_signed_ip_is_time_and_route_bound(self):
        secret, address, stamp = (
            "test-only-proxy-secret",
            "8.8.8.8",
            str(int(time.time())),
        )
        signature = hmac.new(
            secret.encode(),
            "\n".join(
                ["zagjobsearch/client-ip/v1", stamp, "POST", "/login", address]
            ).encode(),
            hashlib.sha256,
        ).hexdigest()
        for path, timestamp, expected in [
            ("/login", stamp, True),
            ("/signup", stamp, False),
            ("/login", "1", False),
        ]:
            request = Request(
                {
                    "type": "http",
                    "method": "POST",
                    "path": path,
                    "headers": [
                        (b"x-zag-client-ip", address.encode()),
                        (b"x-zag-client-time", timestamp.encode()),
                        (b"x-zag-client-signature", signature.encode()),
                    ],
                    "client": ("127.0.0.2", 1),
                }
            )
            with patch.dict(
                os.environ, {"INTERNAL_PROXY_SECRET": secret, "VERCEL": ""}
            ):
                self.assertEqual(security.client_address(request)[1], expected)

    def test_manual_links_cannot_embed_credentials_or_control_characters(self):
        for value in [
            "https://user:secret@example.com/",
            "https://example.com/\npath",
            "javascript:alert(1)",
            "https://example.com:bad/",
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                workspace_api.Application(
                    job_title="Role", company_name="Example", source_url=value
                )
