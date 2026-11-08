"""A lab stores a section ref for good, so a ref must always point at the same section.

Refs use the section's position, not its printed number: the book prints "2.5" twice
in Part I chapter 2, and a number-based ref could not tell those apart.
"""

import json

from src.textbook import library
from src.textbook.library import Book, outline, resolve


def make_book() -> Book:
    def section(number: str, title: str, page: int) -> dict:
        return {
            "number": number,
            "title": title,
            "page_start": page,
            "page_end": page,
            "text": f"text of {title}",
        }

    return Book.model_validate(
        {
            "book": "Ganita Prakash",
            "grade": 8,
            "source": "NCERT",
            "chapters": [
                {
                    "part": 1,
                    "chapter": 2,
                    "title": "Power Play",
                    "page_start": 19,
                    "page_end": 47,
                    "intro": "",
                    "answers": "",
                    "sections": [
                        section("2.5", "Did You Ever Wonder?", 33),
                        section("2.5", "A Pinch of History", 42),
                    ],
                },
                {
                    "part": 2,
                    "chapter": 2,
                    "title": "Pythagoras",
                    "page_start": 33,
                    "page_end": 54,
                    "intro": "",
                    "answers": "",
                    "sections": [section("2.1", "Doubling a Square", 33)],
                },
            ],
        }
    )


def test_outline_refs_resolve_back_to_their_own_section():
    book = make_book()
    for chapter in outline(book).chapters:
        for s in chapter.sections:
            resolved = resolve(book, s.ref)
            assert resolved is not None
            assert (resolved.number, resolved.title) == (s.number, s.title)


def test_duplicate_printed_numbers_get_distinct_refs():
    book = make_book()
    refs = [s.ref for s in outline(book).chapters[0].sections]
    assert refs == ["gp8:p1:c2:s1", "gp8:p1:c2:s2"]
    assert resolve(book, "gp8:p1:c2:s2").title == "A Pinch of History"


def test_same_chapter_number_in_each_part_is_kept_apart():
    book = make_book()
    assert resolve(book, "gp8:p2:c2:s1").title == "Doubling a Square"
    assert resolve(book, "gp8:p2:c2:s1").text == "text of Doubling a Square"


def test_unknown_or_malformed_refs_resolve_to_none():
    book = make_book()
    for ref in ["gp8:p2:c2:s0", "gp8:p2:c2:s2", "gp8:p3:c1:s1", "xx9:p1:c2:s1", "2.5", ""]:
        assert resolve(book, ref) is None


def test_missing_textbook_file_means_no_book(tmp_path, monkeypatch):
    monkeypatch.setattr(library.settings, "textbook_dir", str(tmp_path))
    assert library.load_book() is None
    assert library.resolve_ref("gp8:p2:c2:s1") is None


def test_textbook_file_is_read_from_the_configured_dir(tmp_path, monkeypatch):
    (tmp_path / library.BOOK_FILE).write_text(json.dumps(make_book().model_dump()))
    monkeypatch.setattr(library.settings, "textbook_dir", str(tmp_path))
    assert library.resolve_ref("gp8:p2:c2:s1").title == "Doubling a Square"
