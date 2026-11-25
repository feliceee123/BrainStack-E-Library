import pytest

from app import db


def test_connection_options_read_wasmer_database_variables(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "db.example")
    monkeypatch.setenv("DB_PORT", "6543")
    monkeypatch.setenv("DB_NAME", "library")
    monkeypatch.setenv("DB_USERNAME", "reader")
    monkeypatch.setenv("DB_PASSWORD", "test-password")
    monkeypatch.setenv("DB_SSLMODE", "require")

    options = db._connection_options()

    assert options == {
        "host": "db.example",
        "port": 6543,
        "database": "library",
        "user": "reader",
        "password": "test-password",
        "ssl_context": True,
    }


def test_connection_options_parse_database_url(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://reader%2Btest:p%40ss@db.example:6543/library?sslmode=disable",
    )

    options = db._connection_options()

    assert options == {
        "host": "db.example",
        "port": 6543,
        "database": "library",
        "user": "reader+test",
        "password": "p@ss",
        "ssl_context": False,
    }


def test_connection_options_reject_unsupported_sslmode(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_SSLMODE", "verify-full")

    with pytest.raises(ValueError, match="DB_SSLMODE"):
        db._connection_options()


class FakeCursor:
    description = (("id",), ("title",))

    def __init__(self):
        self.executed = None

    def execute(self, query, args):
        self.executed = (query, args)

    def fetchone(self):
        return (12, "A book")

    def fetchall(self):
        return [(12, "A book"), (13, "Another book")]

    def close(self):
        pass


def test_dict_cursor_maps_rows_and_forwards_parameters():
    raw_cursor = FakeCursor()
    cursor = db._DictCursor(raw_cursor)

    cursor.execute("SELECT id, title FROM books WHERE id = %s", (12,))

    assert raw_cursor.executed == ("SELECT id, title FROM books WHERE id = %s", (12,))
    assert cursor.fetchone() == {"id": 12, "title": "A book"}
    assert cursor.fetchall() == [
        {"id": 12, "title": "A book"},
        {"id": 13, "title": "Another book"},
    ]
