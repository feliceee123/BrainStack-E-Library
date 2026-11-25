"""Gmail SMTP delivery for account verification emails."""
import asyncio
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
import os
import smtplib
import ssl
from urllib.parse import quote

from fastapi import HTTPException


def _send_smtp_message(
    host: str,
    port: int,
    username: str,
    app_password: str,
    message: EmailMessage,
) -> None:
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.ehlo()
        server.starttls(context=ssl.create_default_context())
        server.ehlo()
        server.login(username, app_password)
        server.send_message(message)


async def send_verification_email(email: str, name: str, token: str) -> None:
    username = os.getenv("GMAIL_ADDRESS", "").strip()
    app_password = os.getenv("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if not username or not app_password:
        raise HTTPException(
            status_code=503,
            detail=(
                "The account was created but remains unverified because Gmail SMTP is not configured. "
                "Set GMAIL_ADDRESS and GMAIL_APP_PASSWORD, then resend the verification email."
            ),
        )

    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="SMTP_PORT must be a valid port number.") from exc

    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    from_name = os.getenv("EMAIL_FROM_NAME", "BrainStack E-Library").strip()
    base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    verification_url = f"{base_url}/#/verify-email?token={quote(token)}"

    message = EmailMessage()
    message["From"] = formataddr((from_name, username))
    message["To"] = email
    message["Subject"] = "Verify your BrainStack E-Library account"
    message.set_content(
        f"Hello {name},\n\n"
        "Please verify your email address to activate your E-Library account.\n"
        f"Open this link to verify: {verification_url}\n\n"
        "This link expires in 24 hours. If you did not create this account, ignore this email."
    )
    message.add_alternative(
        f"<p>Hello {escape(name)},</p>"
        "<p>Please verify your email address to activate your E-Library account.</p>"
        f'<p><a href="{verification_url}">Verify my email</a></p>'
        "<p>This link expires in 24 hours. If you did not create this account, ignore this email.</p>",
        subtype="html",
    )

    try:
        await asyncio.to_thread(
            _send_smtp_message,
            host,
            port,
            username,
            app_password,
            message,
        )
    except smtplib.SMTPAuthenticationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Gmail SMTP authentication failed. Use a Google App Password, not your Gmail password.",
        ) from exc
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gmail SMTP could not send the verification email ({type(exc).__name__}).",
        ) from exc
