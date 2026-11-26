from app.seed_data import BOOKS


def test_standard_ebooks_catalog_uses_title_free_hero_art():
    standard_books = [
        book
        for book in BOOKS
        if book["download_url"].startswith("https://standardebooks.org/ebooks/")
    ]
    books_with_hero_art = [book for book in standard_books if book.get("cover_url")]

    assert standard_books
    assert books_with_hero_art
    assert all(book["cover_url"].endswith("/hero@2x.jpg") for book in books_with_hero_art)
    assert all(not book.get("cover_url") for book in standard_books if book not in books_with_hero_art)


def test_books_without_remote_artwork_use_the_local_fallback():
    fallback_titles = {
        "Automate the Boring Stuff with Python",
        "Eloquent JavaScript (4th Edition)",
        "Pro Git",
        "Think Python (2nd Edition)",
        "Lyrical Ballads",
    }

    books_without_artwork = {book["title"] for book in BOOKS if not book.get("cover_url")}

    assert fallback_titles <= books_without_artwork
