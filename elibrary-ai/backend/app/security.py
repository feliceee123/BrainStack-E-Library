import hashlib
import hmac
import os
import time
import uuid

import jwt

SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-change-me-use-a-long-random-secret-in-production")  # set JWT_SECRET in production!
ALGORITHM = "HS256"
USER_TOKEN_MINUTES = 60 * 24
GUEST_TOKEN_MINUTES = 60 * 6
_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def create_token(sub: str, role: str, minutes: int) -> str:
    now = int(time.time())
    payload = {"sub": sub, "role": role, "jti": uuid.uuid4().hex, "iat": now, "exp": now + minutes * 60}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
