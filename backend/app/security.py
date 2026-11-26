import hashlib
import hmac
import os
import secrets
import time
import uuid

import jwt

SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-change-me-use-a-long-random-secret-in-production")
ALGORITHM = "HS256"
USER_TOKEN_MINUTES = 60 * 24          # 24 hours
GUEST_TOKEN_MINUTES = 60 * 6          # 6 hours
_ITERATIONS = 200_000


def create_verification_token() -> str:
    return secrets.token_urlsafe(32)


def create_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_verification_code(code: str) -> str:
    return hmac.new(SECRET_KEY.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def create_token(sub: str, role: str, minutes: int) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "role": role,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + minutes * 60,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
