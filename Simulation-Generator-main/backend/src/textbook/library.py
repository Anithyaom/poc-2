"""Read access to the extracted textbook, for the lab intake picker and (step 3) prompts.

The JSON is written by `scripts/extract_textbook.py` and is NCERT text, so it is never
in the image or the repo: compose mounts `data/textbook/` read-only at TEXTBOOK_DIR.
A missing file is a normal state (nobody ran the extraction yet), not an error: the
picker is simply empty and labs are created without a source.

A lab stores a section as a `source_ref` string, "gp8:p<part>:c<chapter>:s<index>",
where index is the section's 1-based position in its chapter. Position, not the printed
number, because the book prints "2.5" twice in Part I chapter 2.
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ValidationError

from src.config.settings import settings
from src.textbook.extract import Chapter

logger = logging.getLogger(__name__)

BOOK_ID = "gp8"
BOOK_FILE = "ganita_prakash_grade8.json"
_REF = re.compile(r"^(?P<book>[a-z0-9]+):p(?P<part>\d+):c(?P<chapter>\d+):s(?P<index>\d+)$")


class Book(BaseModel):
    book: str
    grade: int
    source: str
    chapters: list[Chapter]


class SourceSummary(BaseModel):
    """Where a lab's source section sits in the book — what the teacher is shown."""

    ref: str
    book: str
    grade: int
    part: int
    chapter: int
    chapter_title: str
    number: str
    title: str
    page_start: int
    page_end: int


class SourceSection(SourceSummary):
    """A source section with its text, for prompting."""

    text: str


# --- Outline served to the picker (no body text) -------------------------------------


class OutlineSection(BaseModel):
    ref: str
    number: str
    title: str
    page_start: int
    page_end: int


class OutlineChapter(BaseModel):
    part: int
    chapter: int
    title: str
    sections: list[OutlineSection]


class BookOutline(BaseModel):
    id: str
    title: str
    grade: int
    source: str
    chapters: list[OutlineChapter]


def make_ref(part: int, chapter: int, index: int, book_id: str = BOOK_ID) -> str:
    return f"{book_id}:p{part}:c{chapter}:s{index}"


def outline(book: Book, book_id: str = BOOK_ID) -> BookOutline:
    return BookOutline(
        id=book_id,
        title=book.book,
        grade=book.grade,
        source=book.source,
        chapters=[
            OutlineChapter(
                part=ch.part,
                chapter=ch.chapter,
                title=ch.title,
                sections=[
                    OutlineSection(
                        ref=make_ref(ch.part, ch.chapter, i, book_id),
                        number=s.number,
                        title=s.title,
                        page_start=s.page_start,
                        page_end=s.page_end,
                    )
                    for i, s in enumerate(ch.sections, start=1)
                ],
            )
            for ch in book.chapters
        ],
    )


def resolve(book: Book, ref: str, book_id: str = BOOK_ID) -> SourceSection | None:
    """The section a ref points at, or None if it does not exist in this book."""
    match = _REF.match(ref)
    if not match or match["book"] != book_id:
        return None
    part, chapter, index = int(match["part"]), int(match["chapter"]), int(match["index"])
    ch = next((c for c in book.chapters if (c.part, c.chapter) == (part, chapter)), None)
    if ch is None or not 1 <= index <= len(ch.sections):
        return None
    s = ch.sections[index - 1]
    return SourceSection(
        ref=ref,
        book=book.book,
        grade=book.grade,
        part=part,
        chapter=chapter,
        chapter_title=ch.title,
        number=s.number,
        title=s.title,
        page_start=s.page_start,
        page_end=s.page_end,
        text=s.text,
    )


@lru_cache(maxsize=1)
def _load(path: Path, mtime: float) -> Book | None:
    try:
        return Book.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, ValidationError) as exc:
        logger.error("Could not read textbook %s: %s", path, exc)
        return None


def load_book() -> Book | None:
    """The extracted book, or None if it has not been extracted/mounted.

    Cached on the file's mtime, so re-running the extraction is picked up without a
    restart.
    """
    path = Path(settings.textbook_dir) / BOOK_FILE
    try:
        mtime = path.stat().st_mtime
    except OSError:
        logger.info("No textbook at %s; the source picker will be empty.", path)
        return None
    return _load(path, mtime)


def resolve_ref(ref: str) -> SourceSection | None:
    book = load_book()
    return resolve(book, ref) if book else None
