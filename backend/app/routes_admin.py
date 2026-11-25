from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .db import get_db
from .deps import require_admin

router = APIRouter(
    prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)]
)

COLS = "id, title, author, category, description, license, download_url"


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


@router.get("/stats")
def admin_stats(db=Depends(get_db)):
    with db.cursor() as cur:
        def one(sql):
            cur.execute(sql)
            return cur.fetchone()["c"]

        totals = {
            "books": one("SELECT COUNT(*) AS c FROM books"),
            "users": one("SELECT COUNT(*) AS c FROM users"),
            "downloads": one("SELECT COUNT(*) AS c FROM downloads"),
            "guest_downloads": one(
                "SELECT COUNT(*) AS c FROM downloads WHERE guest_id IS NOT NULL"
            ),
        }
        cur.execute(
            """
            SELECT b.category AS category, COUNT(*) AS count
            FROM downloads d JOIN books b ON b.id = d.book_id
            GROUP BY b.category ORDER BY count DESC
            """
        )
        downloads_by_category = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT b.id, b.title, b.author, COUNT(*) AS downloads
            FROM downloads d JOIN books b ON b.id = d.book_id
            GROUP BY b.id ORDER BY downloads DESC, b.title LIMIT 5
            """
        )
        top_books = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT category, COUNT(*) AS count FROM books GROUP BY category ORDER BY count DESC"
        )
        books_by_category = [dict(r) for r in cur.fetchall()]

    return {
        "totals": totals,
        "downloads_by_category": downloads_by_category,
        "top_books": top_books,
        "books_by_category": books_by_category,
    }


@router.get("/users")
def list_users(db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.full_name, u.email, u.role, u.created_at,
                   (SELECT COUNT(*) FROM downloads d WHERE d.user_id = u.id) AS downloads
            FROM users u ORDER BY u.id DESC LIMIT 100
            """
        )
        return [dict(r) for r in cur.fetchall()]


@router.get("/books")
def admin_books(db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(f"SELECT {COLS} FROM books ORDER BY title")
        return [dict(r) for r in cur.fetchall()]


@router.post("/books", status_code=201)
def create_book(b: BookIn, db=Depends(get_db)):
    with db.cursor() as cur:
        try:
            cur.execute(
                """
                INSERT INTO books (title, author, category, description, license, download_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    b.title.strip(),
                    b.author.strip(),
                    b.category.strip(),
                    b.description.strip(),
                    b.license.strip(),
                    b.download_url,
                ),
            )
            new_id = cur.fetchone()["id"]
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise HTTPException(409, "A book with this title and author already exists")
            raise
        cur.execute(f"SELECT {COLS} FROM books WHERE id = %s", (new_id,))
        return dict(cur.fetchone())


@router.put("/books/{book_id}")
def update_book(book_id: int, b: BookIn, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM books WHERE id = %s", (book_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Book not found")
        try:
            cur.execute(
                """
                UPDATE books SET title=%s, author=%s, category=%s, description=%s,
                                 license=%s, download_url=%s
                WHERE id=%s
                """,
                (
                    b.title.strip(),
                    b.author.strip(),
                    b.category.strip(),
                    b.description.strip(),
                    b.license.strip(),
                    b.download_url,
                    book_id,
                ),
            )
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise HTTPException(409, "A book with this title and author already exists")
            raise
        cur.execute(f"SELECT {COLS} FROM books WHERE id = %s", (book_id,))
        return dict(cur.fetchone())


@router.delete("/books/{book_id}")
def delete_book(book_id: int, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute("SELECT 1 FROM books WHERE id = %s", (book_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Book not found")
        cur.execute("DELETE FROM books WHERE id = %s", (book_id,))
    return {"message": "Book deleted"}
