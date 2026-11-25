# Phase 3 – PostgreSQL + Agentic AI (Backend)

This folder contains the updated backend that replaces SQLite with **PostgreSQL**
and adds a full **embedded Agentic AI** assistant.

## What changed from Phase 2

| Area              | Phase 2          | Phase 3                          |
|-------------------|------------------|----------------------------------|
| Database          | SQLite           | PostgreSQL (`psycopg2`)          |
| AI Assistant      | Empty tab        | Full tool-calling agent          |
| My Library        | Partial          | Full favorites endpoints         |
| Schema            | SQLite syntax    | PostgreSQL + `is_verified` flag  |
| Placeholders      | `?`              | `%s`                             |

## Tools the AI can call (real database operations)

1. `search_books(query, category?, limit?)`
2. `get_book_details(book_id)`
3. `compare_books(book_ids)`
4. `recommend_books(preferences?, category?, limit?)`
5. `save_to_my_library(book_id)` – **only after user confirmation**

## Start options

### Run with Docker Compose (Windows)

From the project root, copy the Docker-only database settings template and replace its sample password with your own local-only password using letters and numbers only:

```powershell
Copy-Item .env.docker.example .env.docker
notepad .env.docker
```

Keep your Gmail SMTP settings in `backend/.env`; Compose passes those to the API container and overrides `DATABASE_URL` to connect to the `db` service. Do not commit either `.env` file.

Start the application from the project root:

```powershell
docker compose --env-file .env.docker up --build
```

Open http://localhost:8000 and check http://localhost:8000/api/health. Press `Ctrl+C` to stop it, or run `docker compose --env-file .env.docker down` from the project root. The PostgreSQL data remains in its Docker volume.

### Run backend directly

#### 1. Create PostgreSQL database
```bash
# Ubuntu / WSL example
sudo -u postgres createdb elibrary
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
```

#### 2. Install dependencies
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 3. Configure environment
```bash
cp .env.example .env
# edit .env – at minimum set DATABASE_URL and JWT_SECRET
```

#### 4. Run
```bash
python run.py
# or: uvicorn app.main:app --reload --port 8000
```

- Website / API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- AI chat: `POST /api/ai/chat`

### Example AI request (curl)
```bash
# First get a guest token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/guest | jq -r .access_token)

curl -s -X POST http://localhost:8000/api/ai/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "recommend mystery books"}
    ]
  }' | jq
```

You will see `tool_calls_made` containing the real `recommend_books` call
and the actual books from your PostgreSQL catalog.

## AI behaviour

- If `OPENAI_API_KEY` is set → full LLM + tool calling (multi-turn).
- If no key → rule-based agent that **still calls the same real tools**.
  Perfect for the exam demo even without paying for an LLM.

## Gmail SMTP email verification

Enable 2-Step Verification on the Gmail account, create a Google App Password, then set `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, and `PUBLIC_BASE_URL` in `backend/.env`. Set SMTP to `smtp.gmail.com:587` (the defaults). Never use your regular Gmail password or commit the app password. Restart the backend. New registrations receive a verification link and cannot sign in until they open it. Links expire after 24 hours; the web and Android sign-in screens can request a resend.

Use the public HTTPS website URL for `PUBLIC_BASE_URL` outside local browser testing. Gmail SMTP has account sending limits and Google may restrict App Passwords for some account types.

## Next steps in this guide

1. ✅ PostgreSQL + AI
2. ✅ Gmail SMTP email verification
3. ⬜ Password reset
4. ⬜ Wasmer deployment files
