"""PostgreSQL database layer (Phase 3).

Wasmer injects: DB_HOST, DB_PORT, DB_NAME, DB_USERNAME, DB_PASSWORD
Local development: set DATABASE_URL or the individual DB_* variables.
"""
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras
from psycopg2.extras import RealDictCursor

from . import security
from .seed_data import BOOKS

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _build_dsn() -> str:
    """Build a PostgreSQL DSN from environment variables."""
    # Prefer full DATABASE_URL if provided
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "elibrary")
    user = os.getenv("DB_USERNAME", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")

    # Wasmer requires SSL
    sslmode = os.getenv("DB_SSLMODE", "prefer")
    return (
        f"host={host} port={port} dbname={name} "
        f"user={user} password={password} sslmode={sslmode}"
    )


def connect() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(_build_dsn(), cursor_factory=RealDictCursor)
    conn.autocommit = False
    return conn


@contextmanager
def get_connection() -> Iterator[psycopg2.extensions.connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db():
    """FastAPI dependency – one connection per request."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema + seed
# ---------------------------------------------------------------------------

SCHEMA = Path(__file__).with_name("schema.sql")


def init_db() -> None:
    """Create tables (idempotent) and load/refresh the catalog."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA.read_text(encoding="utf-8"))

            # Upsert catalog
            for book in BOOKS:
                cur.execute(
                    """
                    INSERT INTO books (title, author, category, description, license, download_url)
                    VALUES (%(title)s, %(author)s, %(category)s, %(description)s, %(license)s, %(download_url)s)
                    ON CONFLICT (title, author) DO UPDATE SET
                        category     = EXCLUDED.category,
                        description  = EXCLUDED.description,
                        license      = EXCLUDED.license,
                        download_url = EXCLUDED.download_url
                    """,
                    book,
                )

            # Optional admin bootstrap
            ensure_admin(
                conn,
                os.getenv("ADMIN_EMAIL"),
                os.getenv("ADMIN_PASSWORD"),
                os.getenv("ADMIN_NAME", "Administrator"),
            )


def ensure_admin(conn, email: Optional[str], password: Optional[str], name: str = "Administrator") -> bool:
    if not email or not password:
        return False
    email = email.strip().lower()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE users SET role = 'admin', is_verified = TRUE WHERE id = %s", (row["id"],))
        else:
            cur.execute(
                """
                INSERT INTO users (full_name, email, password_hash, role, is_verified)
                VALUES (%s, %s, %s, 'admin', TRUE)
                """,
                (name, email, security.hash_password(password)),
            )
    return True
