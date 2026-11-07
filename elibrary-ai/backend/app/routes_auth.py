import re
import time
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import security
from .db import get_db
from .deps import GUEST_LIMIT, USER_LIMIT, current_principal, downloads_used, limit_for

router = APIRouter(prefix="/api/auth", tags=["auth"])
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_failed: dict[str, list[float]] = defaultdict(list)  # naive login throttle
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


def _user_dict(row) -> dict:
    return {"id": row["id"], "full_name": row["full_name"], "email": row["email"], "role": row["role"]}


def _auth_response(row) -> dict:
    token = security.create_token(str(row["id"]), row["role"], security.USER_TOKEN_MINUTES)
    return {"access_token": token, "token_type": "bearer", "user": _user_dict(row)}


@router.post("/register", status_code=201)
def register(data: RegisterIn, db=Depends(get_db)):
    if db.execute("SELECT 1 FROM users WHERE email = ?", (data.email,)).fetchone():
        raise HTTPException(409, "Email is already registered")
    cur = db.execute("INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
                     (data.full_name.strip(), data.email, security.hash_password(data.password)))
    return _auth_response(db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.post("/login")
def login(data: LoginIn, db=Depends(get_db)):
    email = data.email.strip().lower()
    now = time.time()
    _failed[email] = [t for t in _failed[email] if now - t < WINDOW]
    if len(_failed[email]) >= MAX_FAILS:
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not security.verify_password(data.password, user["password_hash"]):
        _failed[email].append(now)
        raise HTTPException(401, "Invalid email or password")  # same message: no user enumeration
    _failed.pop(email, None)
    return _auth_response(user)


@router.post("/guest")
def guest():
    guest_id = "g_" + uuid.uuid4().hex[:16]
    token = security.create_token(guest_id, "guest", security.GUEST_TOKEN_MINUTES)
    return {"access_token": token, "token_type": "bearer",
            "user": {"id": None, "full_name": "Guest", "email": None, "role": "guest"},
            "download_limit": GUEST_LIMIT}


@router.post("/logout")
def logout(p=Depends(current_principal), db=Depends(get_db)):
    db.execute("INSERT OR IGNORE INTO revoked_tokens (jti, expires_at) VALUES (?, ?)", (p["jti"], p["exp"]))
    db.execute("DELETE FROM revoked_tokens WHERE expires_at < ?", (int(time.time()),))
    return {"message": "Logged out"}


@router.get("/me")
def me(p=Depends(current_principal), db=Depends(get_db)):
    used, limit = downloads_used(db, p), limit_for(p)
    if p["role"] == "guest":
        return {"id": None, "full_name": "Guest", "email": None, "role": "guest",
                "download_limit": limit, "downloads_used": used, "downloads_remaining": limit - used}
    row = db.execute("SELECT * FROM users WHERE id = ?", (p["user_id"],)).fetchone()
    if not row:
        raise HTTPException(401, "User no longer exists")
    return {**_user_dict(row), "download_limit": limit, "downloads_used": used, "downloads_remaining": limit - used}
