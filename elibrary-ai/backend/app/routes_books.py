from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from .db import get_db
from .deps import GUEST_LIMIT, TARGET_BOOKS, USER_LIMIT, current_principal, downloads_used, limit_for

router = APIRouter(prefix="/api", tags=["books"])
PUBLIC_COLS = "id, title, author, category, description, license"


@router.get("/health", tags=["system"])
def health(db=Depends(get_db)):
    books = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    return {"status": "ok", "database": "connected", "books": books, "version": "0.2.0-phase2"}


@router.get("/categories")
def categories(p=Depends(current_principal), db=Depends(get_db)):
    rows = db.execute("SELECT category, COUNT(*) AS n FROM books GROUP BY category ORDER BY category").fetchall()
    return [{"name": r["category"], "count": r["n"]} for r in rows]


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
        where.append("(title LIKE ? OR author LIKE ?)")
        args += [f"%{q}%", f"%{q}%"]
    if category:
        where.append("category = ?")
        args.append(category)
    clause = ("WHERE " + " AND ".join(where)) if where else ""  # values are always bound parameters
    total = db.execute(f"SELECT COUNT(*) FROM books {clause}", args).fetchone()[0]
    rows = db.execute(f"SELECT {PUBLIC_COLS} FROM books {clause} ORDER BY title LIMIT ? OFFSET ?",
                      args + [page_size, (page - 1) * page_size]).fetchall()
    return {"total": total, "page": page, "page_size": page_size, "items": [dict(r) for r in rows]}


@router.get("/books/{book_id}")
def book_detail(book_id: int, p=Depends(current_principal), db=Depends(get_db)):
    row = db.execute(f"SELECT {PUBLIC_COLS} FROM books WHERE id = ?", (book_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Book not found")
    col, val = ("user_id", p["user_id"]) if p["user_id"] else ("guest_id", p["guest_id"])
    already = db.execute(f"SELECT 1 FROM downloads WHERE {col} = ? AND book_id = ?", (val, book_id)).fetchone() is not None
    used, limit = downloads_used(db, p), limit_for(p)
    return {**dict(row), "already_downloaded": already, "downloads_used": used, "download_limit": limit}


@router.post("/books/{book_id}/download")
def download_book(book_id: int, p=Depends(current_principal), db=Depends(get_db)):
    """Backend-enforced limits: 5 books per guest session, 10 per registered account.
    Re-downloading a book you already have does not use another slot."""
    book = db.execute("SELECT id, title, download_url FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        raise HTTPException(404, "Book not found")
    col, val = ("user_id", p["user_id"]) if p["user_id"] else ("guest_id", p["guest_id"])
    limit = limit_for(p)
    already = db.execute(f"SELECT 1 FROM downloads WHERE {col} = ? AND book_id = ?", (val, book_id)).fetchone() is not None
    used = downloads_used(db, p)
    if not already:
        if used >= limit:
            hint = " Register for a free account to get 10 downloads." if p["role"] == "guest" else ""
            raise HTTPException(403, f"Download limit reached ({limit} books).{hint}")
        db.execute(f"INSERT INTO downloads ({col}, book_id) VALUES (?, ?)", (val, book_id))
        used += 1
    return {"book_id": book["id"], "title": book["title"], "download_url": book["download_url"],
            "already_downloaded": already, "downloads_used": used, "download_limit": limit,
            "downloads_remaining": limit - used}


@router.get("/downloads")
def my_downloads(p=Depends(current_principal), db=Depends(get_db)):
    col, val = ("user_id", p["user_id"]) if p["user_id"] else ("guest_id", p["guest_id"])
    rows = db.execute(f"SELECT b.id, b.title, b.author, b.category, MIN(d.created_at) AS downloaded_at "
                      f"FROM downloads d JOIN books b ON b.id = d.book_id WHERE d.{col} = ? "
                      f"GROUP BY b.id ORDER BY downloaded_at DESC", (val,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/stats", tags=["system"])
def stats(p=Depends(current_principal), db=Depends(get_db)):
    return {"books": db.execute("SELECT COUNT(*) FROM books").fetchone()[0], "target_books": TARGET_BOOKS,
            "registered_users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
            "guest_download_limit": GUEST_LIMIT, "user_download_limit": USER_LIMIT}
