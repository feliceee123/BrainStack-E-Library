"""Shared constants and authentication dependencies (PostgreSQL version)."""
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import security
from .db import get_db

bearer = HTTPBearer(auto_error=False)
TARGET_BOOKS = 200
GUEST_LIMIT, USER_LIMIT = 5, 10


def current_principal(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db=Depends(get_db),
) -> dict:
    """Return the token claims plus user_id / guest_id, or raise 401."""
    if cred is None:
        raise HTTPException(401, "Not authenticated")
    try:
        claims = security.decode_token(cred.credentials)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")

    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM revoked_tokens WHERE jti = %s", (claims["jti"],))
        if cur.fetchone():
            raise HTTPException(401, "Token has been logged out")

    sub = claims["sub"]
    claims["user_id"] = int(sub) if claims["role"] in ("user", "admin") else None
    claims["guest_id"] = sub if claims["role"] == "guest" else None
    claims["actor"] = f"user:{sub}" if claims["user_id"] else f"guest:{sub}"
    return claims


def require_admin(p: dict = Depends(current_principal), db=Depends(get_db)) -> dict:
    if p["user_id"] is None:
        raise HTTPException(403, "Administrator access required")
    with db.cursor() as cur:
        cur.execute("SELECT role FROM users WHERE id = %s", (p["user_id"],))
        row = cur.fetchone()
    if not row or row["role"] != "admin":
        raise HTTPException(403, "Administrator access required")
    return p


def limit_for(p: dict) -> int:
    return GUEST_LIMIT if p["role"] == "guest" else USER_LIMIT


def downloads_used(db, p: dict) -> int:
    if p["user_id"]:
        with db.cursor() as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT book_id) AS c FROM downloads WHERE user_id = %s",
                (p["user_id"],),
            )
            return cur.fetchone()["c"]
    else:
        with db.cursor() as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT book_id) AS c FROM downloads WHERE guest_id = %s",
                (p["guest_id"],),
            )
            return cur.fetchone()["c"]
