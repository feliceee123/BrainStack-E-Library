import hmac
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator

from . import email_service, security
from .db import get_db
from .deps import GUEST_LIMIT, USER_LIMIT, current_principal, downloads_used, limit_for

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failed: dict[str, list[float]] = defaultdict(list)
MAX_FAILS, WINDOW = 5, 300
MAX_VERIFICATION_CODE_ATTEMPTS = 5


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    password: str = Field(min_length=8, max_length=128)

    @validator("email")
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v

    @validator("password")
    def _password(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain letters and numbers")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class VerifyEmailIn(BaseModel):
    email: Optional[str] = Field(default=None, max_length=120)
    code: Optional[str] = Field(default=None, min_length=6, max_length=6)
    token: Optional[str] = Field(default=None, min_length=1, max_length=200)

    @validator("email")
    def _email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Invalid email address")
        return v

    @validator("code")
    def _code(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"[0-9]{6}", v):
            raise ValueError("Verification code must contain six digits")
        return v


class ResendVerificationIn(BaseModel):
    email: str = Field(max_length=120)


def _issue_verification_code(db, user_id: int) -> str:
    code = security.create_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    with db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO email_verification_tokens (user_id, token_hash, expires_at, attempts)
            VALUES (%s, %s, %s, 0)
            ON CONFLICT (user_id) DO UPDATE SET
                token_hash = EXCLUDED.token_hash,
                expires_at = EXCLUDED.expires_at,
                created_at = NOW(),
                attempts = 0
            """,
            (user_id, security.hash_verification_code(code), expires_at),
        )
    return code


async def _send_verification(db, user) -> None:
    code = _issue_verification_code(db, user["id"])
    code_hash = security.hash_verification_code(code)
    db.commit()
    try:
        await email_service.send_verification_email(user["email"], user["full_name"], code)
    except HTTPException:
        with db.cursor() as cur:
            cur.execute(
                "DELETE FROM email_verification_tokens WHERE user_id = %s AND token_hash = %s",
                (user["id"], code_hash),
            )
        db.commit()
        raise


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
        "message": "Account created. Enter the verification code sent to your email before signing in.",
        "verification_required": True,
    }


@router.post("/verify-email")
def verify_email(data: VerifyEmailIn, db=Depends(get_db)):
    if data.code is not None:
        if not data.email:
            raise HTTPException(400, "Enter the email address used to register with the verification code.")
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT token.user_id, token.token_hash, token.attempts
                FROM email_verification_tokens AS token
                JOIN users ON users.id = token.user_id
                WHERE users.email = %s AND token.expires_at > NOW()
                FOR UPDATE OF token
                """,
                (data.email,),
            )
            verification = cur.fetchone()
            if not verification:
                raise HTTPException(400, "Verification code is invalid or expired.")
            attempts = verification.get("attempts", 0)
            if attempts >= MAX_VERIFICATION_CODE_ATTEMPTS:
                raise HTTPException(429, "Too many incorrect codes. Request a new verification code.")
            code_hash = security.hash_verification_code(data.code)
            if not hmac.compare_digest(code_hash, verification["token_hash"]):
                cur.execute(
                    "UPDATE email_verification_tokens SET attempts = attempts + 1 WHERE user_id = %s",
                    (verification["user_id"],),
                )
                db.commit()
                if attempts + 1 >= MAX_VERIFICATION_CODE_ATTEMPTS:
                    raise HTTPException(429, "Too many incorrect codes. Request a new verification code.")
                raise HTTPException(400, "Verification code is invalid or expired.")
            user_id = verification["user_id"]
            cur.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (user_id,))
            cur.execute("DELETE FROM email_verification_tokens WHERE user_id = %s", (user_id,))
    elif data.token and not data.email and len(data.token) >= 32 and not data.token.isdigit():
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
            user_id = token["user_id"]
            cur.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (user_id,))
            cur.execute("DELETE FROM email_verification_tokens WHERE user_id = %s", (user_id,))
    else:
        raise HTTPException(400, "Enter the six-digit verification code sent to your email.")
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
    return {"message": "If that account exists and needs verification, a code will be sent."}


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
