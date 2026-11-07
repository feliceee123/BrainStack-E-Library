# Phase 2 Presentation Guide (November 21, 2026)

## A. Submission checklist (from the exam)
- [ ] Updated 5-slide presentation (`ELibraryAI_Phase2_Presentation.pptx`)
- [ ] Updated Android APK (built with your final `BASE_URL`)
- [ ] Updated working website
- [ ] Updated GitHub repository (commit often; push before the presentation)
- [ ] Updated technical documentation (`docs/TECHNICAL_DOCUMENTATION.md`, `docs/TEST_REPORT.md`)
- [ ] Live demonstration of completed modules

## B. Preparation steps
1. Replace your Phase 1 code with this version (or copy the new files), delete the old `backend/elibrary.db` so the 215-book catalog loads.
2. Create the admin: `python create_admin.py admin@example.com "YourStrongPass123"`.
3. Run backend, open the website, test: guest, register, books, details, Download, AI, Admin. Run `python -m pytest -q`.
4. (Recommended) Get an LLM API key and start the server with `ANTHROPIC_API_KEY` set to show the "LLM agent" badge; keep offline mode as a backup.
5. Open `android/` in Android Studio, sync, run on the emulator, complete the checklist in `docs/TEST_REPORT.md`, take 3 screenshots, put them on slide 2.
6. Deploy to Wasmer if you can (`docs/DEPLOYMENT.md`) and rebuild the APK with the https `BASE_URL`.
7. Fill slide 5: GitHub URL, commit count, your own Android result; commit and push.
8. Rehearse the demo twice (total target: 8-10 minutes).

## C. Script (about 1.5 minutes per slide + demos)
1. **Progress** - what is done (catalog, details, downloads, admin, AI on both platforms), what is pending, honest status.
2. **Android** - screens and navigation; demo as in the strip.
3. **Web** - catalog, auth, admin functions; demo as admin and as a user.
4. **Backend & AI** - 6 tables, 19 endpoints, the 5 AI tools; explain the Dracula example with two connected tool calls; mention LLM mode vs offline mode.
5. **Testing & plan** - 13 API tests + 14 browser checks; issues you fixed; remaining work.

## D. Demo script
1. Website guest: books > search "python" > open book > Download (counter 4/5) > try to exceed 5 (limit message).
2. Register an account on the website. Log in with the same account on Android: same user, same downloads count (synchronization).
3. AI on web: "find books about python" > "tell me about the second one" > "compare the first two" > "something like Dracula". Point at the tool chips.
4. Android AI: "recommend a mystery" then tap a result to open details.
5. Admin: log in as admin > charts (downloads by category, AI tools used) > add a book > show it in the catalog > edit > delete.
6. `/docs` page and the GitHub commit history.
Backup plan: if the internet is down, run everything on localhost + emulator.

## E. Likely questions (answer in your own words)
- *How does the agent decide which tool to call?* LLM mode: the model returns a tool request, the backend runs it and sends the result back (loop, max 5). Offline mode: rules.
- *How do you stop the AI from inventing books?* Only tool results are used; every book in the reply is a database row; test checks every returned id exists.
- *Where are download limits enforced?* `routes_books.py` `download_book` counts rows in `downloads` (guest id or user id). The client cannot bypass it.
- *How do web and Android stay synchronized?* Same API and database; counters belong to the account.
- *How is the admin protected?* Role in the JWT and re-checked in the database (`require_admin`); the UI hides the menu but the API enforces it.
- *Where do the books come from?* Public-domain Standard Ebooks editions + open-licensed programming books; license and source stored per book.
- *What is not done yet?* My Library, AI save with confirmation, deployment, Docker, CI/CD.
**Exam rule:** you must be able to explain every line of AI-assisted code. Read `ai_tools.py`, `ai_agent.py`, `routes_books.py`, `routes_admin.py`, `web/app.js`, and the Android `Screens.kt`/`AppViewModel.kt` before presenting.
