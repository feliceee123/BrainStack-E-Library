# E-Library AI  (IPT102 Final Practical Examination)

An integrated **Android + Web digital library** with a shared REST backend and database,
with an "AI Assistant" tab reserved in the navigation (currently empty).

**Phase 2 status (Nov 21, 2026):** 215-book catalog, search/filter, book details, download tracking (5 guest / 10 user),
administrator dashboard + book management.
Phase 1 (Nov 7): authentication, guest mode, shared backend.

```
elibrary-ai/
├─ backend/   FastAPI REST API + SQLite  (serves the website too)
├─ web/       Website (HTML/CSS/vanilla JS)
├─ android/   Android app (Kotlin + Jetpack Compose)
└─ docs/      Technical documentation + presentation guide
```

## Run the backend + website (local)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```
* Website:  http://localhost:8000/
* API docs: http://localhost:8000/docs
* Tests:    `python -m pytest -q`

## Run the Android app
1. Open the `android/` folder in **Android Studio** (Koala or newer, JDK 17) and let Gradle sync.
2. Emulator: keep `BASE_URL=http://10.0.2.2:8000/` in `android/gradle.properties` and keep the backend running.
   Real phone / submission APK: set `BASE_URL` to your deployed https URL.
3. Run, or build the APK: **Build > Build Bundle(s)/APK(s) > Build APK(s)**
   (output: `android/app/build/outputs/apk/debug/app-debug.apk`).

## Administrator account (web admin dashboard)
```powershell
cd backend
python create_admin.py admin@example.com "YourStrongPass123" "Admin Name"
```
Then sign in on the website with that account; an **Admin** menu appears. (Alternatively set `ADMIN_EMAIL` / `ADMIN_PASSWORD` before starting the server.)

## AI Assistant tab
The **AI Assistant** entry stays in the navigation bar (web and Android) but its page is intentionally empty. All AI code (agent, tools, chat endpoint) has been removed.

## Tests
```bash
cd backend && python -m pytest -q          # API tests
pip install playwright && playwright install chromium
python tests/e2e_web.py                    # browser end-to-end (server running with an admin account)
```

## Environment variables (backend)
| Variable | Purpose | Default |
|---|---|---|
| `JWT_SECRET` | Token signing key. **Set a long random value in production.** | dev placeholder |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Create/promote an administrator at startup | none |
| `DATABASE_PATH` | SQLite file location (point it at a persistent volume when deployed) | `backend/elibrary.db` |

See `docs/TECHNICAL_DOCUMENTATION.md` for architecture, database and API details.
