"""Loads the book catalog (catalog.json).

215 public-domain works (Standard Ebooks editions, metadata read from their public GitHub repos)
plus 4 openly licensed programming books. Rebuild with `python tools/harvest.py && python tools/build_catalog.py`.
"""
import json
from pathlib import Path

BOOKS = json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))
