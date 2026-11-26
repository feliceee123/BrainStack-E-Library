-- E-Library AI – PostgreSQL schema (Phase 3)

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    full_name     TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin')),
    is_verified   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS books (
    id           SERIAL PRIMARY KEY,
    title        TEXT NOT NULL,
    author       TEXT NOT NULL,
    category     TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    cover_url    TEXT,
    license      TEXT NOT NULL,
    download_url TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (title, author)
);
CREATE INDEX IF NOT EXISTS idx_books_category ON books(category);
CREATE INDEX IF NOT EXISTS idx_books_title    ON books(title);
CREATE INDEX IF NOT EXISTS idx_books_author   ON books(author);

CREATE TABLE IF NOT EXISTS favorites (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, book_id)
);

-- Exactly one of user_id / guest_id is set. Backend counts rows to enforce 5 / 10 limits.
CREATE TABLE IF NOT EXISTS downloads (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    guest_id   TEXT,
    book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((user_id IS NOT NULL AND guest_id IS NULL) OR (user_id IS NULL AND guest_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_downloads_user  ON downloads(user_id);
CREATE INDEX IF NOT EXISTS idx_downloads_guest ON downloads(guest_id);

-- Server-side logout: tokens listed here are rejected.
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti        TEXT PRIMARY KEY,
    expires_at BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempts   SMALLINT NOT NULL DEFAULT 0
);

-- Optional: store AI conversation history (useful for multi-turn context)
CREATE TABLE IF NOT EXISTS ai_conversations (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    guest_id   TEXT,
    messages   JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_conversations_user
    ON ai_conversations(user_id) WHERE user_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_conversations_guest
    ON ai_conversations(guest_id) WHERE guest_id IS NOT NULL;
