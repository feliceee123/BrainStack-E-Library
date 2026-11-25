import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import email_service, security
from .db import get_db
from .deps import GUEST_LIMIT, USER_LIMIT, current_principal, downloads_used, limit_for

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failed: dict[str, list[float]] = defaultdict(list)
MAX_FAILS, WINDOW = 5, 300


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain letters and numbers")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class ResendVerificationIn(BaseModel):
    email: str = Field(max_length=120)


def _issue_verification_token(db, user_id: int) -> str:
    token = security.create_verification_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO email_verification_tokens (user_id, token_hash, expires_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                token_hash = EXCLUDED.token_hash,
                expires_at = EXCLUDED.expires_at,
                created_at = NOW()
            """,
            (user_id, security.hash_verification_token(token), expires_at),
        )
    return token


async def _send_verification(db, user) -> None:
    token = _issue_verification_token(db, user["id"])
    db.commit()
    await email_service.send_verification_email(user["email"], user["full_name"], token)


def _user_dict(row) -> dict:
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "role": row["role"],
        "is_verified": row.get("is_verified", True),
    }


def _auth_response(row) -> dict:
    token = security.create_token(str(row["id"]), row["role"], security.USER_TOKEN_MINUTES)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(row)}


@router.post("/register", status_code=201)
async def register(data: RegisterIn, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE email = %s", (data.email,))
        if cur.fetchone():
            raise HTTPException(409, "Email is already registered")
        cur.execute(
            """
            INSERT INTO users (full_name, email, password_hash, is_verified)
            VALUES (%s, %s, %s, FALSE)
            RETURNING *
            """,
            (data.full_name.strip(), data.email, security.hash_password(data.password)),
        )
        row = cur.fetchone()
    await _send_verification(db, row)
    return {
        "message": "Account created. Check your email for a verification link before signing in.",
        "verification_required": True,
    }


@router.post("/verify-email")
def verify_email(data: VerifyEmailIn, db=Depends(get_db)):
    token_hash = security.hash_verification_token(data.token)
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT user_id FROM email_verification_tokens
            WHERE token_hash = %s AND expires_at > NOW()
            """,
            (token_hash,),
        )
        token = cur.fetchone()
        if not token:
            raise HTTPException(400, "Verification link is invalid or expired.")
        cur.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (token["user_id"],))
        cur.execute("DELETE FROM email_verification_tokens WHERE user_id = %s", (token["user_id"],))
    return {"message": "Email verified. You can now sign in."}


@router.post("/resend-verification")
async def resend_verification(data: ResendVerificationIn, db=Depends(get_db)):
    email = data.email.strip().lower()
    send_email = False
    with db.cursor() as cur:
        cur.execute("SELECT id, email, full_name, is_verified FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
    if user and not user["is_verified"]:
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT created_at FROM email_verification_tokens
                WHERE user_id = %s AND created_at > NOW() - INTERVAL '1 minute'
                """,
                (user["id"],),
            )
            send_email = cur.fetchone() is None
        if send_email:
            await _send_verification(db, user)
    return {"message": "If that account exists and needs verification, an email will be sent."}


@router.post("/login")
def login(data: LoginIn, db=Depends(get_db)):
    email = data.email.strip().lower()
    now = time.time()
    _failed[email] = [t for t in _failed[email] if now - t < WINDOW]
    if len(_failed[email]) >= MAX_FAILS:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")

    with db.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

    if not user or not security.verify_password(data.password, user["password_hash"]):
        _failed[email].append(now)
        raise HTTPException(401, "Invalid email or password")
    if not user["is_verified"]:
        raise HTTPException(403, "Please verify your email before signing in. Check your inbox or resend the verification email.")
    _failed.pop(email, None)
    return _auth_response(user)


@router.post("/guest")
def guest():
    guest_id = "g_" + uuid.uuid4().hex[:16]
    token = security.create_token(guest_id, "guest", security.GUEST_TOKEN_MINUTES)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": None, "full_name": "Guest", "email": None, "role": "guest"},
        "download_limit": GUEST_LIMIT,
    }


@router.post("/logout")
def logout(p=Depends(current_principal), db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(
            "INSERT INTO revoked_tokens (jti, expires_at) VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (p["jti"], p["exp"]),
        )
        cur.execute("DELETE FROM revoked_tokens WHERE expires_at < %s", (int(time.time()),))
    return {"message": "Logged out"}


@router.get("/me")
def me(p=Depends(current_principal), db=Depends(get_db)):
    used, limit = downloads_used(db, p), limit_for(p)
    if p["role"] == "guest":
        return {
            "id": None,
            "full_name": "Guest",
            "email": None,
            "role": "guest",
            "download_limit": limit,
            "downloads_used": used,
            "downloads_remaining": limit - used,
        }
    with db.cursor() as cur:
        cur.execute("SELECT * FROM users WHERE id = %s", (p["user_id"],))
        row = cur.fetchone()
    if not row:
        raise HTTPException(401, "User no longer exists")
    return {
        **_user_dict(row),
        "download_limit": limit,
        "downloads_used": used,
        "downloads_remaining": limit - used,
    }
