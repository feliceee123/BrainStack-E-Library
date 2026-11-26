"""Loads the book catalog (catalog.json).

Copy catalog.json from your Phase-2 project into this folder.
It contains 215+ public-domain / openly licensed works.
"""
import json
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlparse

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


def _standard_ebooks_cover_url(download_url: str) -> Optional[str]:
    parsed = urlparse(download_url)
    if parsed.hostname not in {"standardebooks.org", "www.standardebooks.org"}:
        return None

    segments = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if len(segments) < 3 or segments[0] != "ebooks":
        return None

    repository = quote("_".join(segments[1:]), safe="-_")
    return (
        "https://raw.githubusercontent.com/standardebooks/"
        f"{repository}/master/src/epub/images/cover.svg"
    )


for book in BOOKS:
    book["cover_url"] = book.get("cover_url") or _standard_ebooks_cover_url(
        book.get("download_url", "")
    )
