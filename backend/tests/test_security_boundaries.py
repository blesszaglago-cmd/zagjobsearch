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
import workspace_api as workspace
import account_security
import saved_searches
from sessions import current_user
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
    def test_invalid_pay_period_is_rejected_before_querying_database(self):
        with patch.object(catalogue, "supabase", MagicMock()) as database:
            with self.assertRaises(HTTPException) as error:
                catalogue.query_catalogue({"salary_period": "invalid"})
            self.assertEqual(error.exception.status_code, 400)
            database.rpc.assert_not_called()

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


class WorkspaceBoundaryTests(unittest.TestCase):
    def setUp(self):
        override = patch.dict(
            app.dependency_overrides, {current_user: lambda: "test-owner"}
        )
        override.start()
        self.addCleanup(override.stop)

    def test_blank_required_fields_and_nonfinite_pay_never_reach_database(self):
        client = TestClient(app)
        with patch.object(workspace, "supabase", MagicMock()) as database:
            for field, value in [("job_title", "  "), ("company_name", "\t\n")]:
                with self.subTest(field=field):
                    response = client.post(
                        "/account/applications",
                        json={
                            "job_title": "Analyst",
                            "company_name": "Example",
                            field: value,
                        },
                    )
                    self.assertEqual(response.status_code, 422)
            for value in ["Infinity", "NaN", "-Infinity"]:
                response = client.post(
                    "/account/applications",
                    content='{"job_title":"Analyst","company_name":"Example","salary_max":'
                    + value
                    + "}",
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(response.status_code, 422)
            database.table.assert_not_called()

    def test_names_are_trimmed_before_length_validation(self):
        for create in [
            lambda: account_security.Preferences(full_name="   "),
            lambda: saved_searches.SavedSearch(name="   ", filters={}),
        ]:
            with self.assertRaises(ValueError):
                create()
        application = workspace.Application(
            job_title="  Analyst  ",
            company_name=" Example ",
            source_url=" https://example.com/careers ",
        )
        self.assertEqual(application.job_title, "Analyst")
        self.assertEqual(application.company_name, "Example")
        self.assertEqual(application.source_url, "https://example.com/careers")

    def test_malformed_private_record_ids_are_validation_errors(self):
        client = TestClient(app)
        with patch.object(
            workspace, "supabase", MagicMock()
        ) as applications, patch.object(
            saved_searches, "supabase", MagicMock()
        ) as searches:
            for method, path, body in [
                (
                    "PUT",
                    "/account/applications/not-a-uuid",
                    {"job_title": "Test", "company_name": "Example"},
                ),
                ("DELETE", "/account/applications/not-a-uuid", None),
                ("POST", "/account/applications/not-a-uuid/restore", None),
                ("GET", "/account/applications/not-a-uuid/events", None),
                ("DELETE", "/account/saved-searches/not-a-uuid", None),
            ]:
                with self.subTest(path=path, method=method):
                    self.assertEqual(
                        client.request(method, path, json=body).status_code, 422
                    )
            applications.table.assert_not_called()
            searches.table.assert_not_called()

    def test_deleted_application_cannot_be_edited_or_read_without_restoring(self):
        requests = []

        def receive(request):
            requests.append(request)
            self.assertEqual(request.url.params.get("user_id"), "eq.test-owner")
            self.assertEqual(request.url.params.get("deleted_at"), "is.null")
            return httpx.Response(200, json=[])

        with httpx.Client(transport=httpx.MockTransport(receive)) as transport:
            database = SyncPostgrestClient(
                "https://database.example/rest/v1", http_client=transport
            )
            with patch.object(workspace, "supabase", database):
                for operation in [
                    lambda: workspace.update_application(
                        "00000000-0000-0000-0000-000000000001",
                        workspace.Application(
                            job_title="Analyst", company_name="Example"
                        ),
                        "test-owner",
                    ),
                    lambda: workspace.events(
                        "00000000-0000-0000-0000-000000000001", "test-owner"
                    ),
                ]:
                    with self.assertRaises(HTTPException) as error:
                        operation()
                    self.assertEqual(error.exception.status_code, 404)
        self.assertEqual([r.method for r in requests], ["GET", "GET"])

    def test_source_explicit_seniority_abbreviations(self):
        for title in [
            "Sr. Specialist, Long Term Planning",
            "Sr Engineer",
            "Snr Analyst",
        ]:
            self.assertEqual(catalogue.level(title), "senior")
        self.assertEqual(catalogue.level("Analyst"), "unspecified")
