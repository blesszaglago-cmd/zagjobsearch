"""Owner-authorized, send-only Gmail transport with private failure diagnostics."""

import base64
import os
import time
from email import policy

import httpx

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


class GmailTransportError(Exception):
    """Only fixed categories and numeric status codes leave this transport."""

    def __init__(self, problem, http_status=None):
        super().__init__(problem)
        self.problem = problem
        self.http_status = http_status


class GmailTransport:
    def __init__(self):
        # Credentials must never follow a redirect or an environment proxy.
        self.client = httpx.Client(
            timeout=8.0, verify=True, follow_redirects=False, trust_env=False
        )
        self._access_token = None
        self._expires_at = 0

    def _post(self, url, problem, **kwargs):
        try:
            response = self.client.post(url, **kwargs)
        except httpx.TimeoutException:
            raise GmailTransportError("gmail_api_timeout") from None
        except httpx.HTTPError:
            raise GmailTransportError("gmail_api_connection_failed") from None
        if response.status_code != 200:
            raise GmailTransportError(problem, response.status_code)
        try:
            payload = response.json()
        except ValueError:
            raise GmailTransportError("gmail_api_invalid_response") from None
        if not isinstance(payload, dict):
            raise GmailTransportError("gmail_api_invalid_response")
        return payload

    def authenticate(self):
        if self._access_token and time.monotonic() < self._expires_at:
            return
        credentials = {
            name: os.getenv(key, "").strip()
            for name, key in (
                ("client_id", "GMAIL_OAUTH_CLIENT_ID"),
                ("client_secret", "GMAIL_OAUTH_CLIENT_SECRET"),
                ("refresh_token", "GMAIL_REFRESH_TOKEN"),
            )
        }
        if not all(credentials.values()):
            raise GmailTransportError("gmail_api_configuration_invalid")
        payload = self._post(
            TOKEN_URL,
            "gmail_api_authentication_failed",
            data={"grant_type": "refresh_token", **credentials},
        )
        token = payload.get("access_token")
        lifetime = payload.get("expires_in")
        scope = payload.get("scope")
        if (
            not isinstance(token, str)
            or not token
            or len(token) > 8192
            or not token.isascii()
            or not token.isprintable()
            or any(char.isspace() for char in token)
            or str(payload.get("token_type", "")).casefold() != "bearer"
            or not isinstance(lifetime, int)
            or isinstance(lifetime, bool)
            or lifetime <= 0
        ):
            raise GmailTransportError("gmail_api_invalid_response")
        # Google may omit scope on refresh; reject an explicitly different grant.
        if scope is not None and (
            not isinstance(scope, str) or set(scope.split()) != {SEND_SCOPE}
        ):
            raise GmailTransportError("gmail_api_scope_mismatch")
        self._access_token = token
        self._expires_at = time.monotonic() + max(1, min(lifetime, 3600) - 30)

    def send_message(self, message):
        self.authenticate()
        raw = base64.urlsafe_b64encode(message.as_bytes(policy=policy.SMTP)).decode(
            "ascii"
        )
        payload = self._post(
            SEND_URL,
            "gmail_api_send_rejected",
            headers={"Authorization": f"Bearer {self._access_token}"},
            json={"raw": raw},
        )
        if not isinstance(payload.get("id"), str) or not payload["id"].strip():
            raise GmailTransportError("gmail_api_invalid_response")

    def quit(self):
        self._access_token = None
        self._expires_at = 0
        self.client.close()
