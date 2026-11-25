import pytest
from pydantic import ValidationError

from app.routes_ai import ChatMessage, ChatRequest, _fallback_agent


class FakeCursor:
    def __init__(self, owner):
        self.owner = owner

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, args=None):
        self.owner.sql = sql
        self.owner.args = args or []

    def fetchall(self):
        if "FROM books" in self.owner.sql and "WHERE" in self.owner.sql:
            return [
                {
                    "id": 12,
                    "title": "The Hound of the Baskervilles",
                    "author": "Arthur Conan Doyle",
                    "category": "Mystery",
                    "description": "A Sherlock Holmes mystery.",
                },
                {
                    "id": 45,
                    "title": "The Mystery of the Yellow Room",
                    "author": "Gaston Leroux",
                    "category": "Mystery",
                    "description": "A classic locked-room mystery.",
                },
            ]
        return []

    def fetchone(self):
        if "SELECT id, title FROM books" in self.owner.sql:
            return {"id": 12, "title": "The Hound of the Baskervilles"}
        if "FROM books WHERE id" in self.owner.sql:
            return {
                "id": 12,
                "title": "The Hound of the Baskervilles",
                "author": "Arthur Conan Doyle",
                "category": "Mystery",
                "description": "A Sherlock Holmes mystery.",
                "license": "Public Domain",
                "download_url": "https://example.com/book",
            }
        return None


class FakeDB:
    def __init__(self):
        self.sql = ""
        self.args = []

    def cursor(self):
        return FakeCursor(self)


def test_recommend_uses_real_tool_shape():
    db = FakeDB()
    reply, calls, books, confirmation, pending = _fallback_agent(
        "recommend mystery books",
        db,
        user_id=7,
    )

    assert "recommend" in reply.lower()
    assert calls[0]["tool"] == "recommend_books"
    assert len(books) == 2
    assert confirmation is False
    assert pending is None


def test_contextual_confirmation_can_save_recent_book():
    db = FakeDB()
    history = [
        {"role": "user", "content": "recommend mystery books"},
        {"role": "assistant", "content": "I found book 12"},
    ]
    reply, calls, _, confirmation, pending = _fallback_agent(
        "yes, save it",
        db,
        user_id=7,
        conversation_messages=history,
    )

    assert calls[0]["tool"] == "save_to_my_library"
    assert "saved" in reply.lower()
    assert confirmation is False
    assert pending is None


def test_guest_cannot_save():
    db = FakeDB()
    reply, calls, _, confirmation, pending = _fallback_agent(
        "save book 12",
        db,
        user_id=None,
    )

    assert "registered users" in reply
    assert calls == []
    assert confirmation is False
    assert pending is None


def test_chat_request_requires_at_least_one_message():
    with pytest.raises(ValidationError):
        ChatRequest(messages=[])

    assert ChatRequest(messages=[ChatMessage(role="user", content="hello")])
