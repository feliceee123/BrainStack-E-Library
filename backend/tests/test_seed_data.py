from app.seed_data import BOOKS, _standard_ebooks_cover_url


def test_standard_ebooks_cover_url_points_to_source_artwork():
    assert _standard_ebooks_cover_url(
        "https://standardebooks.org/ebooks/charles-dickens/a-christmas-carol"
    ) == (
        "https://raw.githubusercontent.com/standardebooks/"
        "charles-dickens_a-christmas-carol/master/src/epub/images/cover.svg"
    )


def test_non_standard_ebooks_books_keep_the_fallback_cover():
    assert _standard_ebooks_cover_url("https://example.com/book") is None


def test_standard_ebooks_catalog_entries_receive_cover_urls():
    standard_books = [
        book
        for book in BOOKS
        if book["download_url"].startswith("https://standardebooks.org/ebooks/")
    ]

    assert standard_books
    assert all(book["cover_url"] for book in standard_books)
