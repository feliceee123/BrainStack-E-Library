"""Loads the book catalog (catalog.json).

Copy catalog.json from your Phase-2 project into this folder.
It contains 215+ public-domain / openly licensed works.
"""
import json
from pathlib import Path

_catalog_path = Path(__file__).with_name("catalog.json")
if _catalog_path.exists():
    BOOKS = json.loads(_catalog_path.read_text(encoding="utf-8"))
else:
    # Fallback minimal set so the server still starts
    BOOKS = [
        {
            "title": "Pride and Prejudice",
            "author": "Jane Austen",
            "category": "Classics",
            "description": "A classic novel of manners.",
            "license": "Public Domain",
            "download_url": "https://www.gutenberg.org/ebooks/1342",
        },
        {
            "title": "The Adventures of Sherlock Holmes",
            "author": "Arthur Conan Doyle",
            "category": "Mystery",
            "description": "Famous detective stories.",
            "license": "Public Domain",
            "download_url": "https://www.gutenberg.org/ebooks/1661",
        },
    ]
