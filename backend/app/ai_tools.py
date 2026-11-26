"""
Agentic AI tools that operate on the real E-Library database.

These tools are called by the LLM (or by the rule-based fallback agent).
Every tool receives a live database connection so results are always current.
"""
from typing import Any, Optional


def search_books(db, query: str, category: Optional[str] = None, limit: int = 8) -> list[dict]:
    """Search books by title or author. Optionally filter by category."""
    limit = max(1, min(limit, 20))
    args: list[Any] = [f"%{query}%", f"%{query}%"]
    sql = """
        SELECT id, title, author, category, description, cover_url
        FROM books
        WHERE (title ILIKE %s OR author ILIKE %s)
    """
    if category:
        sql += " AND category ILIKE %s"
        args.append(f"%{category}%")
    sql += " ORDER BY title LIMIT %s"
    args.append(limit)

    with db.cursor() as cur:
        cur.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]


def get_book_details(db, book_id: int) -> Optional[dict]:
    """Return full details for a single book."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT id, title, author, category, description, cover_url, license, download_url
            FROM books WHERE id = %s
            """,
            (book_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def compare_books(db, book_ids: list[int]) -> list[dict]:
    """Compare 2–5 books side-by-side."""
    if not book_ids or len(book_ids) > 5:
        return []
    placeholders = ",".join(["%s"] * len(book_ids))
    with db.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, title, author, category, description, cover_url, license
            FROM books WHERE id IN ({placeholders})
            ORDER BY title
            """,
            book_ids,
        )
        return [dict(r) for r in cur.fetchall()]


def recommend_books(
    db,
    preferences: str = "",
    category: Optional[str] = None,
    limit: int = 5,
) -> list[dict]:
    """Recommend books based on free-text preferences or a category."""
    limit = max(1, min(limit, 10))
    args: list[Any] = []
    sql = "SELECT id, title, author, category, description, cover_url FROM books WHERE 1=1"

    if category:
        sql += " AND category ILIKE %s"
        args.append(f"%{category}%")
    elif preferences:
        # Simple keyword match against title/author/description/category
        words = [w.strip() for w in preferences.lower().split() if len(w.strip()) > 2]
        if words:
            clauses = []
            for w in words[:6]:  # limit keywords
                clauses.append(
                    "(title ILIKE %s OR author ILIKE %s OR description ILIKE %s OR category ILIKE %s)"
                )
                args.extend([f"%{w}%"] * 4)
            sql += " AND (" + " OR ".join(clauses) + ")"

    # Prefer relevance and stable ordering over random results so repeated requests
    # are predictable and recommendations are easier to explain.
    if preferences and not category:
        words = [w.strip() for w in preferences.lower().split() if len(w.strip()) > 2][:6]
        score_parts = []
        score_args = []
        for word in words:
            score_parts.append("(CASE WHEN title ILIKE %s THEN 4 WHEN author ILIKE %s THEN 3 WHEN category ILIKE %s THEN 2 WHEN description ILIKE %s THEN 1 ELSE 0 END)")
            score_args.extend([f"%{word}%"] * 4)
        if score_parts:
            sql += " ORDER BY (" + " + ".join(score_parts) + ") DESC, title ASC"
            args.extend(score_args)
        else:
            sql += " ORDER BY title ASC"
    else:
        sql += " ORDER BY title ASC"
    sql += " LIMIT %s"
    args.append(limit)

    with db.cursor() as cur:
        cur.execute(sql, args)
        return [dict(r) for r in cur.fetchall()]


def save_to_my_library(db, user_id: int, book_id: int) -> dict:
    """Save a book to the authenticated user's My Library (favorites)."""
    with db.cursor() as cur:
        cur.execute("SELECT id, title FROM books WHERE id = %s", (book_id,))
        book = cur.fetchone()
        if not book:
            return {"success": False, "message": f"Book id {book_id} not found."}

        cur.execute(
            """
            INSERT INTO favorites (user_id, book_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (user_id, book_id),
        )
        return {
            "success": True,
            "message": f"'{book['title']}' has been saved to your My Library.",
            "book_id": book_id,
            "title": book["title"],
        }


# Tool schema descriptions that the LLM sees
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_books",
            "description": "Search the E-Library catalog by title or author. Use this when the user asks to find books.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keywords (title or author)"},
                    "category": {"type": "string", "description": "Optional category filter"},
                    "limit": {"type": "integer", "description": "Max results (default 8)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_book_details",
            "description": "Get full details of a single book by its numeric id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {"type": "integer", "description": "The book id"},
                },
                "required": ["book_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_books",
            "description": "Compare 2 to 5 books side-by-side using their ids.",
            "parameters": {
                "type": "object",
                "properties": {
                    "book_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of book ids to compare",
                    },
                },
                "required": ["book_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_books",
            "description": "Recommend books based on user preferences or a category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferences": {
                        "type": "string",
                        "description": "Free-text description of what the user likes",
                    },
                    "category": {"type": "string", "description": "Preferred category"},
                    "limit": {"type": "integer", "description": "How many recommendations"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_my_library",
            "description": (
                "Save a book to the user's My Library. "
                "ONLY call this after the user has explicitly confirmed they want to save the book."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "book_id": {"type": "integer", "description": "The book id to save"},
                },
                "required": ["book_id"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict, db, user_id: Optional[int] = None) -> Any:
    """Dispatch a tool call to the real function."""
    if name == "search_books":
        return search_books(
            db,
            query=arguments.get("query", ""),
            category=arguments.get("category"),
            limit=arguments.get("limit", 8),
        )
    if name == "get_book_details":
        return get_book_details(db, int(arguments["book_id"]))
    if name == "compare_books":
        return compare_books(db, [int(i) for i in arguments.get("book_ids", [])])
    if name == "recommend_books":
        return recommend_books(
            db,
            preferences=arguments.get("preferences", ""),
            category=arguments.get("category"),
            limit=arguments.get("limit", 5),
        )
    if name == "save_to_my_library":
        if not user_id:
            return {"success": False, "message": "Only registered users can save to My Library."}
        return save_to_my_library(db, user_id, int(arguments["book_id"]))
    return {"error": f"Unknown tool: {name}"}
