"""PostgreSQL database layer (Phase 3).

Wasmer injects: DB_HOST, DB_PORT, DB_NAME, DB_USERNAME, DB_PASSWORD
Local development: set DATABASE_URL or the individual DB_* variables.
"""
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional
from urllib.parse import parse_qs, unquote, urlparse

import pg8000.dbapi

from . import security
from .seed_data import BOOKS

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _ssl_context(sslmode: str) -> Optional[bool]:
    mode = sslmode.strip().lower()
    if mode == "disable":
        return False
    if mode == "require":
        return True
    if mode == "prefer":
        return None
    raise ValueError("DB_SSLMODE must be one of: disable, prefer, require")


def _connection_options() -> dict[str, Any]:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in ("postgres", "postgresql"):
            raise ValueError("DATABASE_URL must use the postgres or postgresql scheme")
        query = parse_qs(parsed.query)
        sslmode = query.get("sslmode", [os.getenv("DB_SSLMODE", "prefer")])[0]
        options = {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 5432,
            "database": unquote(parsed.path.lstrip("/")) or "elibrary",
            "user": unquote(parsed.username or "postgres"),
            "password": unquote(parsed.password or os.getenv("DB_PASSWORD", "postgres")),
        }
    else:
        sslmode = os.getenv("DB_SSLMODE", "prefer")
        options = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "database": os.getenv("DB_NAME", "elibrary"),
            "user": os.getenv("DB_USERNAME", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres"),
        }
    options["ssl_context"] = _ssl_context(sslmode)
    return options


class _DictCursor:
    def __init__(self, cursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def execute(self, query: str, args=None):
        self._cursor.execute(query, () if args is None else args)
        return self

    def _as_dict(self, row):
        if row is None:
            return None
        columns = self._cursor.description
        if not columns:
            return row
        return {column[0]: value for column, value in zip(columns, row)}

    def fetchone(self):
        return self._as_dict(self._cursor.fetchone())

    def fetchall(self):
        return [self._as_dict(row) for row in self._cursor.fetchall()]

    def close(self):
        self._cursor.close()


class _DictConnection:
    def __init__(self, connection) -> None:
        self._connection = connection

    def cursor(self) -> _DictCursor:
        return _DictCursor(self._connection.cursor())

    def __getattr__(self, name):
        return getattr(self._connection, name)


def connect() -> _DictConnection:
    connection = pg8000.dbapi.connect(**_connection_options())
    connection.autocommit = False
    return _DictConnection(connection)


@contextmanager
def get_connection() -> Iterator[_DictConnection]:
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
                    INSERT INTO books (title, author, category, description, cover_url, license, download_url)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (title, author) DO UPDATE SET
                        category     = EXCLUDED.category,
                        description  = EXCLUDED.description,
                        cover_url    = EXCLUDED.cover_url,
                        license      = EXCLUDED.license,
                        download_url = EXCLUDED.download_url
                    """,
                    (
                        book["title"],
                        book["author"],
                        book["category"],
                        book["description"],
                        book.get("cover_url"),
                        book["license"],
                        book["download_url"],
                    ),
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
