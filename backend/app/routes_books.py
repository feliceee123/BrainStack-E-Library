from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .db import get_db
from .deps import (
    GUEST_LIMIT,
    TARGET_BOOKS,
    USER_LIMIT,
    current_principal,
    downloads_used,
    limit_for,
)

router = APIRouter(prefix="/api", tags=["books"])
PUBLIC_COLS = "id, title, author, category, description, cover_url, license"


@router.get("/health", tags=["system"])
def health(db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM books")
        books = cur.fetchone()["c"]
    return {
        "status": "ok",
        "database": "postgresql",
        "books": books,
        "version": "0.3.0-phase3",
    }


@router.get("/categories")
def categories(p=Depends(current_principal), db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(
            "SELECT category AS name, COUNT(*) AS count FROM books GROUP BY category ORDER BY category"
        )
        return [dict(r) for r in cur.fetchall()]


@router.get("/books")
def list_books(
    q: Optional[str] = Query(None, max_length=100),
    category: Optional[str] = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    p=Depends(current_principal),
    db=Depends(get_db),
):
    where, args = [], []
    if q:
        where.append("(title ILIKE %s OR author ILIKE %s)")
        args += [f"%{q}%", f"%{q}%"]
    if category:
        where.append("category = %s")
        args.append(category)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    with db.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS c FROM books {clause}", args)
        total = cur.fetchone()["c"]
        cur.execute(
            f"SELECT {PUBLIC_COLS} FROM books {clause} ORDER BY title LIMIT %s OFFSET %s",
            args + [page_size, (page - 1) * page_size],
        )
        items = [dict(r) for r in cur.fetchall()]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/books/{book_id}")
def book_detail(book_id: int, p=Depends(current_principal), db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(f"SELECT {PUBLIC_COLS} FROM books WHERE id = %s", (book_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Book not found")

        if p["user_id"]:
            cur.execute(
                "SELECT 1 FROM downloads WHERE user_id = %s AND book_id = %s",
                (p["user_id"], book_id),
            )
        else:
            cur.execute(
                "SELECT 1 FROM downloads WHERE guest_id = %s AND book_id = %s",
                (p["guest_id"], book_id),
            )
        already = cur.fetchone() is not None

    used, limit = downloads_used(db, p), limit_for(p)
    return {
        **dict(row),
        "already_downloaded": already,
        "downloads_used": used,
        "download_limit": limit,
    }


@router.post("/books/{book_id}/download")
def download_book(book_id: int, p=Depends(current_principal), db=Depends(get_db)):
    """Backend-enforced limits: 5 books per guest session, 10 per registered account."""
    with db.cursor() as cur:
        cur.execute(
            "SELECT id, title, download_url FROM books WHERE id = %s", (book_id,)
        )
        book = cur.fetchone()
        if not book:
            raise HTTPException(404, "Book not found")

        limit = limit_for(p)
        if p["user_id"]:
            cur.execute(
                "SELECT 1 FROM downloads WHERE user_id = %s AND book_id = %s",
                (p["user_id"], book_id),
            )
            already = cur.fetchone() is not None
            used = downloads_used(db, p)
            if not already:
                if used >= limit:
                    raise HTTPException(
                        403,
                        f"Download limit reached ({limit} books).",
                    )
                cur.execute(
                    "INSERT INTO downloads (user_id, book_id) VALUES (%s, %s)",
                    (p["user_id"], book_id),
                )
                used += 1
        else:
            cur.execute(
                "SELECT 1 FROM downloads WHERE guest_id = %s AND book_id = %s",
                (p["guest_id"], book_id),
            )
            already = cur.fetchone() is not None
            used = downloads_used(db, p)
            if not already:
                if used >= limit:
                    raise HTTPException(
                        403,
                        f"Download limit reached ({limit} books). Register for a free account to get 10 downloads.",
                    )
                cur.execute(
                    "INSERT INTO downloads (guest_id, book_id) VALUES (%s, %s)",
                    (p["guest_id"], book_id),
                )
                used += 1

    return {
        "book_id": book["id"],
        "title": book["title"],
        "download_url": book["download_url"],
        "already_downloaded": already,
        "downloads_used": used,
        "download_limit": limit,
        "downloads_remaining": limit - used,
    }


@router.get("/downloads")
def my_downloads(p=Depends(current_principal), db=Depends(get_db)):
    with db.cursor() as cur:
        if p["user_id"]:
            cur.execute(
                """
                SELECT b.id, b.title, b.author, b.category, MIN(d.created_at) AS downloaded_at
                FROM downloads d JOIN books b ON b.id = d.book_id
                WHERE d.user_id = %s
                GROUP BY b.id ORDER BY downloaded_at DESC
                """,
                (p["user_id"],),
            )
        else:
            cur.execute(
                """
                SELECT b.id, b.title, b.author, b.category, MIN(d.created_at) AS downloaded_at
                FROM downloads d JOIN books b ON b.id = d.book_id
                WHERE d.guest_id = %s
                GROUP BY b.id ORDER BY downloaded_at DESC
                """,
                (p["guest_id"],),
            )
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# My Library (favorites)
# ---------------------------------------------------------------------------

@router.get("/library")
def my_library(p=Depends(current_principal), db=Depends(get_db)):
    if p["role"] == "guest":
        raise HTTPException(403, "Guests cannot use My Library. Please register.")
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT b.id, b.title, b.author, b.category, b.description, f.created_at AS saved_at
            FROM favorites f JOIN books b ON b.id = f.book_id
            WHERE f.user_id = %s
            ORDER BY f.created_at DESC
            """,
            (p["user_id"],),
        )
        return [dict(r) for r in cur.fetchall()]


@router.post("/library/{book_id}", status_code=201)
def save_to_library(book_id: int, p=Depends(current_principal), db=Depends(get_db)):
    if p["role"] == "guest":
        raise HTTPException(403, "Guests cannot save to My Library. Please register.")
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM books WHERE id = %s", (book_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Book not found")
        cur.execute(
            """
            INSERT INTO favorites (user_id, book_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (p["user_id"], book_id),
        )
    return {"message": "Book saved to My Library", "book_id": book_id}


@router.delete("/library/{book_id}")
def remove_from_library(book_id: int, p=Depends(current_principal), db=Depends(get_db)):
    if p["role"] == "guest":
        raise HTTPException(403, "Guests cannot use My Library.")
    with db.cursor() as cur:
        cur.execute(
            "DELETE FROM favorites WHERE user_id = %s AND book_id = %s",
            (p["user_id"], book_id),
        )
    return {"message": "Book removed from My Library"}


@router.get("/stats", tags=["system"])
def stats(p=Depends(current_principal), db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS c FROM books")
        books = cur.fetchone()["c"]
        cur.execute("SELECT COUNT(*) AS c FROM users")
        users = cur.fetchone()["c"]
    return {
        "books": books,
        "target_books": TARGET_BOOKS,
        "registered_users": users,
        "guest_download_limit": GUEST_LIMIT,
        "user_download_limit": USER_LIMIT,
    }
