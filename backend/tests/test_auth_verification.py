import asyncio

import pytest
from fastapi import HTTPException

from app import email_service, security
from app.routes_auth import LoginIn, VerifyEmailIn, login, verify_email


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
        elif "SELECT user_id FROM email_verification_tokens" in sql:
            if self.db.token_hash and args[0] == self.db.token_hash:
                self.result = {"user_id": self.db.user["id"]}
            else:
                self.result = None
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

    def cursor(self):
        return FakeCursor(self)


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


def test_verification_email_uses_configured_gmail_smtp(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent.update(host=host, port=port, timeout=timeout)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def ehlo(self):
            return None

        def starttls(self, context):
            sent["tls_context"] = context

        def login(self, username, password):
            sent.update(username=username, password=password)

        def send_message(self, message):
            sent["message"] = message

    monkeypatch.setenv("GMAIL_ADDRESS", "sender@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "test-app-password")
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://library.example.com")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSMTP)

    asyncio.run(email_service.send_verification_email("reader@example.com", "Reader", "one-time-token"))

    assert sent["host"] == "smtp.gmail.com"
    assert sent["port"] == 587
    assert sent["username"] == "sender@gmail.com"
    assert sent["password"] == "test-app-password"
    assert sent["tls_context"] is not None
    message = sent["message"]
    assert message["From"].endswith("sender@gmail.com>")
    assert message["To"] == "reader@example.com"
    assert "https://library.example.com/#/verify-email?token=one-time-token" in message.get_body(preferencelist=("html",)).get_content()
