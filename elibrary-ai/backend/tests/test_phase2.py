from fastapi.testclient import TestClient

from app.main import app

ADMIN = {"email": "admin@test.local", "password": "AdminPass123"}


def H(t):
    return {"Authorization": f"Bearer {t}"}


def guest(c):
    return c.post("/api/auth/guest").json()["access_token"]


def register(c, email):
    r = c.post("/api/auth/register", json={"full_name": "Test User", "email": email, "password": "secret123"})
    assert r.status_code == 201
    return r.json()["access_token"]


def test_catalog_has_200_unique_books_with_legal_sources():
    with TestClient(app) as c:
        t = guest(c)
        data = c.get("/api/books?page_size=100", headers=H(t)).json()
        assert data["total"] >= 200
        assert c.get("/api/health").json()["books"] >= 200
        from app.db import connect
        db = connect()
        rows = db.execute("SELECT title, author, license, download_url FROM books").fetchall()
        assert len({(r["title"], r["author"]) for r in rows}) == len(rows)       # unique
        assert all(r["license"] and r["download_url"].startswith("https://") for r in rows)
        db.close()


def test_book_detail_and_404():
    with TestClient(app) as c:
        t = guest(c)
        first = c.get("/api/books", headers=H(t)).json()["items"][0]
        d = c.get(f"/api/books/{first['id']}", headers=H(t)).json()
        assert d["title"] == first["title"] and d["already_downloaded"] is False and d["download_limit"] == 5
        assert "download_url" not in d                      # link only released through the download endpoint
        assert c.get("/api/books/999999", headers=H(t)).status_code == 404


def test_guest_download_limit_is_5_and_repeat_is_free():
    with TestClient(app) as c:
        t = guest(c)
        ids = [b["id"] for b in c.get("/api/books?page_size=10", headers=H(t)).json()["items"]]
        for i in ids[:5]:
            r = c.post(f"/api/books/{i}/download", headers=H(t))
            assert r.status_code == 200 and r.json()["download_url"].startswith("http")
        assert c.post(f"/api/books/{ids[0]}/download", headers=H(t)).json()["already_downloaded"] is True
        r = c.post(f"/api/books/{ids[5]}/download", headers=H(t))
        assert r.status_code == 403 and "Register" in r.json()["detail"]
        me = c.get("/api/auth/me", headers=H(t)).json()
        assert me["downloads_used"] == 5 and me["downloads_remaining"] == 0
        assert len(c.get("/api/downloads", headers=H(t)).json()) == 5
        # a different guest session has its own counter
        assert c.post(f"/api/books/{ids[5]}/download", headers=H(guest(c))).status_code == 200


def test_registered_limit_is_10_and_shared_across_logins():
    with TestClient(app) as c:
        t = register(c, "reader@test.local")
        ids = [b["id"] for b in c.get("/api/books?page_size=12", headers=H(t)).json()["items"]]
        for i in ids[:10]:
            assert c.post(f"/api/books/{i}/download", headers=H(t)).status_code == 200
        assert c.post(f"/api/books/{ids[10]}/download", headers=H(t)).status_code == 403
        # logging in again (e.g. from the other platform) sees the same counter
        t2 = c.post("/api/auth/login", json={"email": "reader@test.local", "password": "secret123"}).json()["access_token"]
        assert c.get("/api/auth/me", headers=H(t2)).json()["downloads_used"] == 10


def test_admin_access_control_and_crud():
    with TestClient(app) as c:
        user, g = register(c, "plain@test.local"), guest(c)
        for tok in (user, g):
            assert c.get("/api/admin/stats", headers=H(tok)).status_code == 403
            assert c.post("/api/admin/books", headers=H(tok), json={}).status_code in (403, 422)
        assert c.get("/api/admin/stats").status_code == 401

        a = c.post("/api/auth/login", json=ADMIN).json()
        assert a["user"]["role"] == "admin"
        t = a["access_token"]
        new = {"title": "Test Driven Book", "author": "Ada Tester", "category": "Technology", "description": "x",
               "license": "CC BY", "download_url": "https://example.com/book"}
        r = c.post("/api/admin/books", headers=H(t), json=new)
        assert r.status_code == 201
        bid = r.json()["id"]
        assert c.post("/api/admin/books", headers=H(t), json=new).status_code == 409           # duplicate
        assert c.post("/api/admin/books", headers=H(t), json={**new, "title": "T2", "download_url": "javascript:alert(1)"}).status_code == 422
        assert c.put(f"/api/admin/books/{bid}", headers=H(t), json={**new, "title": "Renamed Book"}).json()["title"] == "Renamed Book"
        assert c.get(f"/api/books/{bid}", headers=H(user)).json()["title"] == "Renamed Book"   # visible to everyone
        assert c.delete(f"/api/admin/books/{bid}", headers=H(t)).status_code == 200
        assert c.get(f"/api/books/{bid}", headers=H(user)).status_code == 404

        s = c.get("/api/admin/stats", headers=H(t)).json()
        assert s["totals"]["books"] >= 200 and s["totals"]["downloads"] >= 1
        assert s["downloads_by_category"] and s["top_books"]
        assert any(u["email"] == "plain@test.local" for u in c.get("/api/admin/users", headers=H(t)).json())
