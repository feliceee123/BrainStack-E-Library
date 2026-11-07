import os
import sqlite3
from pathlib import Path

from . import security
from .seed_data import BOOKS

DB_PATH = os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent.parent / "elibrary.db"))
SCHEMA = Path(__file__).with_name("schema.sql")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)  # one connection per request, used sequentially
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables, load/refresh the catalog, optionally bootstrap an admin (idempotent)."""
    conn = connect()
    try:
        conn.executescript(SCHEMA.read_text())
        # Remove the Phase-1 sample rows (they pointed to different sources)
        conn.execute("DELETE FROM books WHERE download_url LIKE 'https://www.gutenberg.org/ebooks/%'")
        conn.executemany(
            "INSERT INTO books (title, author, category, description, license, download_url)"
            " VALUES (:title, :author, :category, :description, :license, :download_url)"
            " ON CONFLICT(title, author) DO UPDATE SET category=excluded.category,"
            " description=excluded.description, license=excluded.license, download_url=excluded.download_url",
            BOOKS,
        )
        ensure_admin(conn, os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD"), os.getenv("ADMIN_NAME", "Administrator"))
        conn.commit()
    finally:
        conn.close()


def ensure_admin(conn, email, password, name="Administrator") -> bool:
    """Create the admin account if ADMIN_EMAIL/ADMIN_PASSWORD are provided; promote if it already exists."""
    if not email or not password:
        return False
    email = email.strip().lower()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (row["id"],))
    else:
        conn.execute("INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                     (name, email, security.hash_password(password)))
    return True


def get_db():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
