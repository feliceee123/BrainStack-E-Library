import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .db import get_db
from .deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class BookIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1, max_length=150)
    category: str = Field(min_length=1, max_length=60)
    description: str = Field(default="", max_length=2000)
    license: str = Field(min_length=1, max_length=100)
    download_url: str = Field(max_length=500)

    @field_validator("download_url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError("Download URL must start with http:// or https://")
        return v


COLS = "id, title, author, category, description, license, download_url"


@router.get("/stats")
def admin_stats(db=Depends(get_db)):
    one = lambda sql: db.execute(sql).fetchone()[0]
    return {
        "totals": {"books": one("SELECT COUNT(*) FROM books"), "users": one("SELECT COUNT(*) FROM users"),
                   "downloads": one("SELECT COUNT(*) FROM downloads"),
                   "guest_downloads": one("SELECT COUNT(*) FROM downloads WHERE guest_id IS NOT NULL")},
        "downloads_by_category": [dict(r) for r in db.execute(
            "SELECT b.category AS category, COUNT(*) AS count FROM downloads d JOIN books b ON b.id = d.book_id "
            "GROUP BY b.category ORDER BY count DESC").fetchall()],
        "top_books": [dict(r) for r in db.execute(
            "SELECT b.id, b.title, b.author, COUNT(*) AS downloads FROM downloads d JOIN books b ON b.id = d.book_id "
            "GROUP BY b.id ORDER BY downloads DESC, b.title LIMIT 5").fetchall()],
        "books_by_category": [dict(r) for r in db.execute(
            "SELECT category, COUNT(*) AS count FROM books GROUP BY category ORDER BY count DESC").fetchall()],
    }


@router.get("/users")
def list_users(db=Depends(get_db)):
    rows = db.execute("SELECT u.id, u.full_name, u.email, u.role, u.created_at, "
                      "(SELECT COUNT(*) FROM downloads d WHERE d.user_id = u.id) AS downloads "
                      "FROM users u ORDER BY u.id DESC LIMIT 100").fetchall()
    return [dict(r) for r in rows]


@router.get("/books")
def admin_books(db=Depends(get_db)):
    return [dict(r) for r in db.execute(f"SELECT {COLS} FROM books ORDER BY title").fetchall()]


@router.post("/books", status_code=201)
def create_book(b: BookIn, db=Depends(get_db)):
    try:
        cur = db.execute("INSERT INTO books (title, author, category, description, license, download_url) VALUES (?,?,?,?,?,?)",
                         (b.title.strip(), b.author.strip(), b.category.strip(), b.description.strip(), b.license.strip(), b.download_url))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "A book with this title and author already exists")
    return dict(db.execute(f"SELECT {COLS} FROM books WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.put("/books/{book_id}")
def update_book(book_id: int, b: BookIn, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(404, "Book not found")
    try:
        db.execute("UPDATE books SET title=?, author=?, category=?, description=?, license=?, download_url=? WHERE id=?",
                   (b.title.strip(), b.author.strip(), b.category.strip(), b.description.strip(), b.license.strip(), b.download_url, book_id))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "A book with this title and author already exists")
    return dict(db.execute(f"SELECT {COLS} FROM books WHERE id = ?", (book_id,)).fetchone())


@router.delete("/books/{book_id}")
def delete_book(book_id: int, db=Depends(get_db)):
    if not db.execute("SELECT 1 FROM books WHERE id = ?", (book_id,)).fetchone():
        raise HTTPException(404, "Book not found")
    db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    return {"message": "Book deleted"}
