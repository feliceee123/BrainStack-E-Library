# Phase 1 Presentation Guide (November 7, 2026)

## A. What you must submit
- [ ] 5-slide PowerPoint (`ELibraryAI_Phase1_Presentation.pptx`) - exactly 5 slides
- [ ] Initial Android APK
- [ ] Working web prototype (URL or demo from your laptop)
- [ ] GitHub repository (this project)
- [ ] Initial technical documentation (`docs/TECHNICAL_DOCUMENTATION.md`; export to PDF/Word if your instructor wants that format)

## B. Step-by-step build order
1. **Run the backend + website locally** (README). Open http://localhost:8000, try guest, register, login, logout.
2. **Run `python -m pytest -q`** - you should see all tests pass.
3. **Android**: open `android/` in Android Studio, sync, run on emulator (backend must be running). Test guest, register, login, books, log out.
4. **Push to GitHub**
   ```bash
   cd elibrary-ai
   git init && git add . && git commit -m "Phase 1: auth, catalog, shared backend"
   git branch -M main
   git remote add origin https://github.com/<you>/elibrary-ai.git
   git push -u origin main
   ```
   Make several small, meaningful commits - the commit history is evidence of your work.
5. **Deploy the backend/website to Wasmer** (see `DEPLOYMENT.md`), then set `BASE_URL` in `android/gradle.properties`
   to the https URL and build the APK that you submit.
6. **Build the APK**: Android Studio > Build > Build Bundle(s)/APK(s) > Build APK(s). Install it on a real phone and test it.
7. **Take Android screenshots** (Welcome, Login/Register, Dashboard) and replace the three dashed boxes on slide 4.
8. **Fill the placeholders** on slide 5 (GitHub URL, Wasmer URL) and adjust "challenges" to what you really experienced.
9. **Rehearse twice** with a timer (target 7-8 minutes + demo).

## C. Speaking script (about 1-1.5 minutes per slide)
**Slide 1 - Overview.** "Good day. My project is E-Library AI, one digital library that runs on Android and the web and shares a single backend and database. Its goals are secure accounts, Guest Mode with 5 downloads, registered users with 10, server-enforced limits, only legally downloadable books, at least 200 of them, and an AI assistant embedded in both apps. Target users are students and readers; admins manage the catalog."

**Slide 2 - Stack.** "Android is Kotlin with Jetpack Compose and Retrofit. The website is plain HTML, CSS and JavaScript. The backend is FastAPI in Python because it validates input automatically and generates API docs. The database is SQLite for now and portable to PostgreSQL. Authentication uses JWT and hashed passwords. For AI I will use an LLM with tool calling in Phase 2. Hosting is Wasmer, as required."

**Slide 3 - Architecture.** "Both clients call the same REST API over HTTPS. The API handles authentication and reads and writes one shared database, which keeps accounts and downloads synchronized. The dashed boxes are Phase 2: an agent service inside the backend that calls tools like search_books and save_to_library against the real database and talks to an LLM."

**Slide 4 - Auth & interfaces (then LIVE DEMO).** Follow the demo script in section D.

**Slide 5 - Progress.** "Completed: guest, register, login, logout and dashboard on both platforms, 9 API endpoints, 5 database tables, 35 starter books, secure authentication. Testing: automated API tests and manual tests; I found and fixed a threading bug in database access. Challenges: sourcing 200 legal books and keeping both apps consistent. Next: expand to 200+ books, downloads with limits, My Library, the AI agent, admin dashboard, Docker and CI."

## D. Live demo script (3-4 minutes)
1. Website > **Continue as Guest** > dashboard shows "Guest" and limit 5.
2. Books > search `python` > filter **Technology**.
3. **Log out**. Show that going to `#/books` redirects to login (protected).
4. **Register** with a short password (shows validation error), then a valid one > dashboard shows limit 10.
5. Log out, log in again with the same account; try a wrong password (generic error).
6. Open `/docs` - "this is the REST API; both apps use these same endpoints."
7. Android: Guest > Books > Profile > Log out; then Register/Login.
8. Show GitHub: folders, README, commit history.
Backup: if the internet fails, run everything on localhost and the Android emulator; keep screenshots ready.

## E. Questions you may get (be ready to answer in your own words)
- *Why FastAPI / JWT / SQLite?* (see slide 2 and technical documentation sections 2 and 7)
- *How are passwords stored?* Salted PBKDF2-SHA256, 200,000 iterations - `backend/app/security.py`.
- *How does logout work with JWT?* The token id (`jti`) is stored in `revoked_tokens` and rejected afterwards - `/api/auth/logout` and `current_principal` in `main.py`.
- *How do guests work?* `/api/auth/guest` issues a short-lived token with role `guest`; the guest id will key the download count.
- *Where will the 5/10 limit be enforced?* In the backend by counting rows in `downloads` (Phase 2-3), never in the client.
- *How will the AI agent work?* See technical documentation section 6.
- *How do you prevent SQL injection / XSS?* Parameterized queries; `textContent` instead of `innerHTML`.
- *Which books are legal?* Public-domain (Project Gutenberg) and openly licensed technical books; each row stores license and source.

**Important (exam rule):** you must be able to explain every line of AI-assisted code. Before Nov 7, read through
`backend/app/main.py`, `security.py`, `web/app.js`, and the Android `Api.kt`, `AppViewModel.kt`, `Screens.kt`, and run
each feature yourself so you can explain it without notes.
