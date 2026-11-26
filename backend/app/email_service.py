"""Brevo delivery for account verification emails."""
from html import escape
import os
from urllib.parse import quote

import httpx
from fastapi import HTTPException


_BREVO_EMAIL_API = "https://api.brevo.com/v3/smtp/email"


async def send_verification_email(email: str, name: str, token: str) -> None:
    api_key = os.getenv("BREVO_API_KEY", "").strip()
    sender_email = os.getenv("BREVO_SENDER_EMAIL", "").strip()
    if not api_key or not sender_email:
        raise HTTPException(
            status_code=503,
            detail=(
                "Brevo email is not configured. Set BREVO_API_KEY and "
                "BREVO_SENDER_EMAIL, then resend the verification email."
            ),
        )

    sender_name = os.getenv("BREVO_SENDER_NAME", "BrainStack E-Library").strip()
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    verification_url = f"{base_url}/#/verify-email?token={quote(token)}"
    payload = {
        "sender": {"name": sender_name, "email": sender_email},
        "to": [{"email": email, "name": name}],
        "subject": "Verify your BrainStack E-Library account",
        "textContent": (
            f"Hello {name},\n\n"
            "Please verify your email address to activate your E-Library account.\n"
            f"Open this link to verify: {verification_url}\n\n"
            "This link expires in 24 hours. If you did not create this account, ignore this email."
        ),
        "htmlContent": (
            f"<p>Hello {escape(name)},</p>"
            "<p>Please verify your email address to activate your E-Library account.</p>"
            f'<p><a href="{verification_url}">Verify my email</a></p>'
            "<p>This link expires in 24 hours. If you did not create this account, ignore this email.</p>"
        ),
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                _BREVO_EMAIL_API,
                headers={"api-key": api_key, "accept": "application/json"},
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Brevo rejected the verification email (HTTP {exc.response.status_code}). "
                "Check the API key, verified sender, and Brevo account status."
            ),
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Brevo to send the verification email ({type(exc).__name__}).",
        ) from exc
