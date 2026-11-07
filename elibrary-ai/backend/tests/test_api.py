from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

GOOD = {"full_name": "Juan Dela Cruz", "email": "Juan@Example.com", "password": "secret123"}


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_all():
    with TestClient(app) as c:
        # health + seeded DB
        h = c.get("/api/health").json()
        assert h["status"] == "ok" and h["books"] >= 200

        # protected without token
        assert c.get("/api/books").status_code == 401

        # register: validation + success + duplicate
        assert c.post("/api/auth/register", json={**GOOD, "password": "short"}).status_code == 422
        assert c.post("/api/auth/register", json={**GOOD, "password": "allletters"}).status_code == 422
        r = c.post("/api/auth/register", json=GOOD)
        assert r.status_code == 201 and r.json()["user"]["email"] == "juan@example.com"
        assert "password" not in r.text
        assert c.post("/api/auth/register", json=GOOD).status_code == 409

        # login: wrong then right
        assert c.post("/api/auth/login", json={"email": GOOD["email"], "password": "wrong1234"}).status_code == 401
        t = c.post("/api/auth/login", json={"email": GOOD["email"], "password": GOOD["password"]}).json()["access_token"]
        me = c.get("/api/auth/me", headers=auth(t)).json()
        assert me["role"] == "user" and me["download_limit"] == 10

        # books: search + filter
        assert c.get("/api/books", headers=auth(t)).json()["total"] >= 200
        assert c.get("/api/books?q=python", headers=auth(t)).json()["total"] >= 2
        tech = c.get("/api/books?category=Technology", headers=auth(t)).json()
        assert tech["total"] >= 4 and all(b["category"] == "Technology" for b in tech["items"])
        # SQL injection attempt is treated as plain text
        assert c.get("/api/books?q=' OR 1=1 --", headers=auth(t)).json()["total"] == 0

        # logout revokes the token on the server
        assert c.post("/api/auth/logout", headers=auth(t)).status_code == 200
        assert c.get("/api/books", headers=auth(t)).status_code == 401

        # guest mode
        g = c.post("/api/auth/guest").json()
        assert g["user"]["role"] == "guest" and g["download_limit"] == 5
        assert c.get("/api/books", headers=auth(g["access_token"])).status_code == 200
        assert c.get("/api/auth/me", headers=auth(g["access_token"])).json()["role"] == "guest"

        # tampered token rejected
        assert c.get("/api/books", headers=auth(g["access_token"] + "x")).status_code == 401


def test_login_throttle():
    with TestClient(app) as c:
        for _ in range(5):
            assert c.post("/api/auth/login", json={"email": "x@y.com", "password": "nope12345"}).status_code == 401
        assert c.post("/api/auth/login", json={"email": "x@y.com", "password": "nope12345"}).status_code == 429
