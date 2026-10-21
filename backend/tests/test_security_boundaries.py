"""Non-destructive regressions for hostile inputs and private boundaries."""

import json
import os
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient
from postgrest import SyncPostgrestClient

import auth
import catalogue
import ghana_sources
import security
from main import app


class InjectionTransportTests(unittest.TestCase):
    def test_search_payload_remains_a_json_parameter(self):
        requests = []

        def receive(request):
            requests.append(request)
            return httpx.Response(
                200, json={"jobs": [], "total": 0, "page": 1, "has_more": False}
            )

        with httpx.Client(transport=httpx.MockTransport(receive)) as transport:
            database = SyncPostgrestClient(
                "https://database.example/rest/v1", http_client=transport
            )
            for payload in ["' OR '1'='1' --", "Accra),or(id.not.is.null)"]:
                with self.subTest(payload=payload), patch.object(
                    catalogue, "supabase", database
                ):
                    catalogue.query_catalogue({"q": payload})
                    request = requests[-1]
                    self.assertEqual(request.method, "POST")
                    self.assertEqual(
                        request.url.path, "/rest/v1/rpc/search_ghana_catalogue"
                    )
                    self.assertFalse(request.url.query)
                    self.assertEqual(
                        json.loads(request.content)["filters"]["q"], payload
                    )

    def test_email_input_cannot_add_rest_query_parameters(self):
        requests = []

        def receive(request):
            requests.append(request)
            return httpx.Response(200, json=[])

        with httpx.Client(transport=httpx.MockTransport(receive)) as transport:
            database = SyncPostgrestClient(
                "https://database.example/rest/v1", http_client=transport
            )
            with patch.object(auth, "supabase", database):
                self.assertIsNone(auth.find_email("a@example.com&or=(id.not.is.null)"))
            parameters = requests[0].url.params
            self.assertEqual(set(parameters), {"select", "email", "limit"})
            self.assertEqual(parameters["select"], "*")
            self.assertEqual(parameters["limit"], "1")
            self.assertTrue(parameters["email"].startswith("ilike.a@example.com&or="))


class RequestBoundaryTests(unittest.TestCase):
    def test_sql_shaped_login_is_rejected_before_authentication(self):
        with patch("main.login_user") as login:
            response = TestClient(app).post(
                "/login", json={"email": "' OR '1'='1' --", "password": "test-only"}
            )
        self.assertEqual(response.status_code, 422)
        login.assert_not_called()

    def test_validation_errors_do_not_echo_account_secrets(self):
        password = "test-only-private-password"
        confirmation = "different-test-only-password"
        with patch("main.validate_signup") as signup:
            response = TestClient(app).post(
                "/signup",
                json={
                    "full_name": "Test Account",
                    "email": "test-only@example.com",
                    "password": password,
                    "confirm_password": confirmation,
                    "age_confirmed": True,
                    "accepted_terms": True,
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertNotIn(password, response.text)
        self.assertNotIn(confirmation, response.text)
        self.assertNotIn("input", response.json()["detail"][0])
        self.assertEqual(response.headers["cache-control"], "no-store")
        signup.assert_not_called()

    def test_malformed_cron_auth_is_rejected_without_a_database_call(self):
        with patch.dict(
            os.environ, {"CRON_SECRET": "test-only-cron-secret"}
        ), patch.object(security, "supabase", MagicMock()) as database:
            with self.assertRaises(HTTPException) as error:
                security.require_cron("Bearer " + chr(233) * 28)
            self.assertEqual(error.exception.status_code, 401)
            database.rpc.assert_not_called()


class FeedBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_feed_rejects_declared_entities_before_reading_items(self):
        payload = '<!DOCTYPE rss [<!ENTITY sample "unsafe">]><rss><channel><item><title>&sample;</title></item></channel></rss>'
        client = types.SimpleNamespace(
            get=AsyncMock(
                return_value=types.SimpleNamespace(status_code=200, text=payload)
            )
        )
        with patch.object(ghana_sources, "parse_hire_item") as parse:
            with self.assertRaisesRegex(ValueError, "Agency feed unavailable"):
                await ghana_sources.hireghana(client)
            parse.assert_not_called()
