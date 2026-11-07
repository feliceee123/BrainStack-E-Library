"""Optional browser end-to-end test (needs: pip install playwright && playwright install chromium).

Start the server first with an admin account, e.g. (PowerShell):
  $env:ADMIN_EMAIL="admin@example.com"; $env:ADMIN_PASSWORD="AdminPass123"; python -m uvicorn app.main:app --port 8000
Then:  python tests/e2e_web.py
Screenshots are saved in ./screenshots
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

BASE = os.getenv("BASE_URL", "http://localhost:8000")
ADMIN = (os.getenv("ADMIN_EMAIL", "admin@example.com"), os.getenv("ADMIN_PASSWORD", "AdminPass123"))
os.makedirs("screenshots", exist_ok=True)
errors, checks = [], []


def ok(name, cond):
    checks.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name)


with sync_playwright() as p:
    browser = p.chromium.launch()

    def new_page():
        pg = browser.new_context(viewport={"width": 1280, "height": 760}).new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" and not any(c in m.text for c in ("401", "403", "409", "422")) else None)
        return pg

    # ---------- guest ----------
    pg = new_page()
    pg.goto(BASE); pg.click("text=Continue as Guest"); pg.wait_for_url("**#/dashboard"); pg.wait_for_selector(".stat")
    ok("guest dashboard shows 0 / 5", "0 / 5" in pg.inner_text("#view"))
    pg.click("nav >> text=Books"); pg.wait_for_selector(".book")
    ok("catalog shows 200+ books", int(pg.inner_text("#view p").split()[0]) >= 200)
    pg.click(".chip:has-text('Technology')"); pg.wait_for_timeout(500)
    ok("category filter", pg.locator(".book").count() == 4)
    pg.screenshot(path="screenshots/web_books.png")
    pg.click(".book >> nth=0"); pg.wait_for_selector(".detail")
    pg.screenshot(path="screenshots/web_detail.png")
    pg.click("button:has-text('Download')"); pg.wait_for_selector(".msg.ok")
    ok("download works and shows remaining", "4 of 5" in pg.inner_text(".msg.ok"))
    pg.screenshot(path="screenshots/web_download.png")
    pg.click("nav >> text=AI Assistant"); pg.wait_for_timeout(300)
    ok("AI Assistant page is empty", pg.inner_text("#view").strip() == "")
    pg.click("text=Log out"); pg.wait_for_timeout(400)
    pg.goto(BASE + "/#/admin"); pg.wait_for_timeout(400)
    ok("protected page redirects to login after logout", "login" in pg.url)

    # ---------- register + validation ----------
    pg = new_page(); pg.goto(BASE + "/#/register")
    pg.fill("#name", "Maria Clara"); pg.fill("#email", f"maria{int(time.time())}@example.com"); pg.fill("#password", "short")
    pg.click("button[type=submit]"); pg.wait_for_selector(".msg.err")
    ok("weak password rejected", "8 characters" in pg.inner_text(".msg.err"))
    pg.fill("#password", "secret123"); pg.click("button[type=submit]"); pg.wait_for_url("**#/dashboard"); pg.wait_for_selector(".stat")
    ok("registered dashboard shows 0 / 10", "0 / 10" in pg.inner_text("#view"))
    pg.goto(BASE + "/#/admin"); pg.wait_for_timeout(500)
    ok("normal user cannot open admin", "Administrator access required" in pg.inner_text("#view") or "dashboard" in pg.url)

    # ---------- admin ----------
    pg = new_page(); pg.goto(BASE + "/#/login")
    pg.fill("#email", ADMIN[0]); pg.fill("#password", ADMIN[1]); pg.click("button[type=submit]")
    pg.wait_for_url("**#/admin"); pg.wait_for_selector(".bars")
    ok("admin dashboard loads stats", "Downloads by category" in pg.inner_text("#view"))
    pg.click("button:has-text('+ Add book')")
    for label, val in [("Title", "E2E Test Book"), ("Author", "Test Author"), ("Category", "Technology"), ("License", "CC BY"), ("Download URL", "https://example.com/e2e")]:
        pg.locator(f".form label:has-text('{label}') + input").first.fill(val)
    pg.click("button:has-text('Add book') >> nth=-1"); pg.wait_for_selector("td:has-text('E2E Test Book')")
    ok("admin added a book", True)
    pg.screenshot(path="screenshots/web_admin.png", full_page=False)
    pg.once("dialog", lambda d: d.accept())
    pg.locator("tr:has-text('E2E Test Book') button:has-text('Delete')").click(); pg.wait_for_timeout(800)
    ok("admin deleted the book", pg.locator("td:has-text('E2E Test Book')").count() == 0)
    browser.close()

ok("no browser console/page errors", not errors)
if errors:
    print(errors)
failed = [n for n, c in checks if not c]
print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
sys.exit(1 if failed else 0)
