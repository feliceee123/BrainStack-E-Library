"""E-Library AI - shared REST backend (Phase 2).

Serves both clients: the Android app and the website (static files in ../web).
Interactive API docs: /docs
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import routes_admin, routes_auth, routes_books
from .db import init_db


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="E-Library AI API", version="0.2.0-phase2", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for r in (routes_auth.router, routes_books.router, routes_admin.router):
    app.include_router(r)

# Website (mounted last so /api/* routes win)
WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
