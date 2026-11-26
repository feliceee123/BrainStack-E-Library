import asyncio

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import email_service, security
from app.routes_auth import LoginIn, RegisterIn, VerifyEmailIn, login, verify_email


class FakeCursor:
    def __init__(self, db):
        self.db = db
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, args=None):
        args = args or ()
        if "SELECT * FROM users WHERE email" in sql:
            self.result = self.db.user if args[0] == self.db.user["email"] else None
        elif "FROM email_verification_tokens AS token" in sql:
            if self.db.token_hash and args[0] == self.db.user["email"]:
                self.result = {
                    "user_id": self.db.user["id"],
                    "token_hash": self.db.token_hash,
                    "attempts": self.db.attempts,
                }
            else:
                self.result = None
        elif "SELECT user_id FROM email_verification_tokens" in sql:
            if self.db.token_hash and args[0] == self.db.token_hash:
                self.result = {"user_id": self.db.user["id"]}
            else:
                self.result = None
        elif "UPDATE email_verification_tokens SET attempts = attempts + 1" in sql:
            self.db.attempts += 1
        elif "UPDATE users SET is_verified = TRUE" in sql:
            self.db.user["is_verified"] = True
        elif "DELETE FROM email_verification_tokens" in sql:
            self.db.token_hash = None

    def fetchone(self):
        return self.result


class FakeDB:
    def __init__(self, user, token_hash=None):
        self.user = user
        self.token_hash = token_hash
        self.attempts = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        return None


def test_unverified_user_cannot_log_in(monkeypatch):
    user = {
        "id": 7,
        "email": "reader@example.com",
        "password_hash": "hashed",
        "role": "user",
        "is_verified": False,
    }
    db = FakeDB(user)
    monkeypatch.setattr(security, "verify_password", lambda password, stored: True)

    with pytest.raises(HTTPException) as error:
        login(LoginIn(email=user["email"], password="ValidPass123"), db)

    assert error.value.status_code == 403
    assert "verify your email" in error.value.detail.lower()


def test_registration_model_normalizes_email_and_checks_password():
    registration = RegisterIn(
        full_name="Reader",
        email=" Reader@Example.com ",
        password="ValidPass123",
    )

    assert registration.email == "reader@example.com"

    with pytest.raises(ValidationError, match="Password must contain letters and numbers"):
        RegisterIn(
            full_name="Reader",
            email="reader@example.com",
            password="letters-only",
        )


def test_verification_token_is_single_use():
    raw_token = security.create_verification_token()
    token_hash = security.hash_verification_token(raw_token)
    user = {"id": 7, "email": "reader@example.com", "is_verified": False}
    db = FakeDB(user, token_hash=token_hash)

    result = verify_email(VerifyEmailIn(token=raw_token), db)

    assert result["message"] == "Email verified. You can now sign in."
    assert user["is_verified"] is True
    assert db.token_hash is None

    with pytest.raises(HTTPException) as error:
        verify_email(VerifyEmailIn(token=raw_token), db)
    assert error.value.status_code == 400


def test_verification_code_is_six_digits():
    code = security.create_verification_code()

    assert len(code) == 6
    assert code.isascii() and code.isdigit()


def test_verification_code_is_single_use():
    code = "001234"
    user = {"id": 7, "email": "reader@example.com", "is_verified": False}
    db = FakeDB(user, token_hash=security.hash_verification_code(code))

    result = verify_email(VerifyEmailIn(email=user["email"], code=code), db)

    assert result["message"] == "Email verified. You can now sign in."
    assert user["is_verified"] is True
    assert db.token_hash is None


def test_verification_code_limits_incorrect_attempts():
    user = {"id": 7, "email": "reader@example.com", "is_verified": False}
    db = FakeDB(user, token_hash=security.hash_verification_code("654321"))

    for attempt in range(5):
        with pytest.raises(HTTPException) as error:
            verify_email(VerifyEmailIn(email=user["email"], code="123456"), db)
        assert error.value.status_code == (429 if attempt == 4 else 400)

    assert db.attempts == 5

    with pytest.raises(HTTPException) as error:
        verify_email(VerifyEmailIn(email=user["email"], code="123456"), db)
    assert error.value.status_code == 429


def test_verification_email_uses_configured_brevo_api(monkeypatch):
    sent = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, timeout):
            sent["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            sent.update(url=url, headers=headers, payload=json)
            return FakeResponse()

    monkeypatch.setenv("BREVO_API_KEY", "test-brevo-api-key")
    monkeypatch.setenv("BREVO_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setenv("BREVO_SENDER_NAME", "BrainStack")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://library.example.com")
    monkeypatch.setattr(email_service.httpx, "AsyncClient", FakeClient)

    asyncio.run(email_service.send_verification_email("reader@example.com", "Reader", "012345"))

    assert sent["url"] == "https://api.brevo.com/v3/smtp/email"
    assert sent["headers"]["api-key"] == "test-brevo-api-key"
    assert sent["timeout"] == 20.0
    payload = sent["payload"]
    assert payload["sender"] == {"name": "BrainStack", "email": "sender@example.com"}
    assert payload["to"] == [{"email": "reader@example.com", "name": "Reader"}]
    assert "https://library.example.com/#/verify-email?email=reader%40example.com&amp;code=012345" in payload["htmlContent"]
    assert "expires in 15 minutes" in payload["textContent"]


def test_verification_email_requires_brevo_configuration(monkeypatch):
    monkeypatch.delenv("BREVO_API_KEY", raising=False)
    monkeypatch.setenv("BREVO_SENDER_EMAIL", "sender@example.com")

    with pytest.raises(HTTPException) as error:
        asyncio.run(email_service.send_verification_email("reader@example.com", "Reader", "token"))

    assert error.value.status_code == 503
    assert "BREVO_API_KEY" in error.value.detail


def test_verification_email_reports_brevo_rejection_without_exposing_key(monkeypatch):
    class FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            request = email_service.httpx.Request("POST", url)
            response = email_service.httpx.Response(401, request=request)
            response.raise_for_status()

    monkeypatch.setenv("BREVO_API_KEY", "test-brevo-api-key")
    monkeypatch.setenv("BREVO_SENDER_EMAIL", "sender@example.com")
    monkeypatch.setattr(email_service.httpx, "AsyncClient", FakeClient)

    with pytest.raises(HTTPException) as error:
        asyncio.run(email_service.send_verification_email("reader@example.com", "Reader", "token"))

    assert error.value.status_code == 502
    assert "HTTP 401" in error.value.detail
    assert "test-brevo-api-key" not in error.value.detail
