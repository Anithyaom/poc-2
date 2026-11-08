"""Turn the raw text of a textbook chapter's pages into numbered sections.

Pure functions only: the caller reads the PDF (see `scripts/extract_textbook.py`, which
uses pypdf, a dev-only dependency) and passes one string per page. Keeping PDF parsing
out of here lets the cleanup rules be unit-tested on plain strings.

What the NCERT layout gives us, and what each rule below relies on:
- Page 1 of a chapter has no running header; the chapter number and its title, in
  capitals and often split across lines ("FRACTIONS IN" / "DISGUISE1"), appear
  somewhere on it.
- Every later page opens with a running header (the book title or the chapter title)
  followed by the printed page number.
- Every page ends with print furniture: "Reprint 2026-27" or an InDesign slug
  ("01_Chapter 1.indd   1 20-12-2025 16:28:46").
- Sections are headed "<chapter>.<n> Title", numbered from 1. The book repeats a number
  once (Part I has two 2.5s), so a repeat of the previous number is also accepted.
- Part I chapter PDFs end with an answer key. Its pages cite the question they answer
  ("Page No. 22") and are numbered 1, 2, 3... on their own, so the key starts at the first
  page with a "Page No." line. It is kept apart from the sections.

Known, accepted losses: fractions and exponents flatten (3/4 becomes "3 4", 67³ becomes
"673") and diagram labels leave stray numbers. The output is LLM context, not a
reproduction of the book.
"""

import re
from collections import Counter

from pydantic import BaseModel

_BOOK_HEADER = re.compile(r"^Ganita Prakash \| Grade \d+( \| Part-I+)?$")
_PAGE_NUMBER = re.compile(r"^\d{1,3}$")
_FURNITURE = (
    re.compile(r"^Reprint \d{4}-\d{2}$"),
    re.compile(r"\.indd\s"),
)
_ANSWER_KEY = re.compile(r"(?m)^\s*Page No\.?\s*\d+")
_SECTION_HEADING = re.compile(r"^(\d{1,2})\.(\d{1,2})\s+([A-Z“‘\"'].{0,79})$")
# pypdf inserts a space before some punctuation ("sugar , while").
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([,.;:?!])(?=\s|$)")


class Section(BaseModel):
    number: str  # "1.2"
    title: str
    page_start: int  # printed book page numbers
    page_end: int
    text: str


class Chapter(BaseModel):
    part: int
    chapter: int
    title: str
    page_start: int
    page_end: int
    intro: str  # text before the first numbered section; may be empty
    sections: list[Section]
    answers: str  # the appended answer key (Part I only); empty when there is none


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _is_title_fragment(line: str, chapter: int, title_words: set[str]) -> bool:
    """A page-1 line that only spells part of the chapter's number/title banner."""
    stripped = line.strip()
    if stripped == str(chapter):
        return True
    if not stripped or stripped != stripped.upper():
        return False  # banner lines are all capitals; body text is not
    words = _norm(stripped.removesuffix(str(chapter))).split()
    return bool(words) and set(words) <= title_words


def clean_page(raw: str, *, index: int, chapter: int, title: str) -> tuple[list[str], int | None]:
    """Strip headers, page numbers and print furniture from one page.

    Returns the remaining lines and the printed page number, if the page shows one.
    """
    lines = [ln.rstrip() for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln.strip()]
    lines = [ln for ln in lines if not any(p.search(ln.strip()) for p in _FURNITURE)]

    page_number = None
    if index == 0:
        title_words = set(_norm(title).split())
        lines = [ln for ln in lines if not _is_title_fragment(ln, chapter, title_words)]
    else:
        # The header is usually line 1, but pypdf sometimes emits it mid-page.
        lines = [
            ln for ln in lines if not (_BOOK_HEADER.match(ln.strip()) or _norm(ln) == _norm(title))
        ]
        if lines and _PAGE_NUMBER.match(lines[0].strip()):
            page_number = int(lines[0].strip())
            lines = lines[1:]

    return [_SPACE_BEFORE_PUNCT.sub(r"\1", ln) for ln in lines], page_number


def _book_page_numbers(printed: list[int | None]) -> list[int]:
    """Printed page number of every page, filling the ones that show none.

    Uses the most common offset between PDF index and printed number, so one misread
    number (a diagram label in the header position) cannot shift the whole chapter.
    """
    offsets = Counter(n - i for i, n in enumerate(printed) if n is not None)
    offset = offsets.most_common(1)[0][0] if offsets else 1
    return [i + offset for i in range(len(printed))]


def answer_key_start(pages: list[str]) -> int:
    """Index of the first answer-key page, or len(pages) if the chapter has none."""
    return next((i for i, raw in enumerate(pages) if i > 0 and _ANSWER_KEY.search(raw)), len(pages))


def _squash(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.lower())


def _consume_title_continuation(lines: list[str], start: int, seen: str, full: str) -> int:
    """Skip the lines that finish a wrapped heading; return the index after them."""
    remainder = _squash(full)
    if not remainder.startswith(_squash(seen)):
        return start
    remainder = remainder[len(_squash(seen)) :]
    i = start
    while remainder and i < len(lines):
        piece = _squash(lines[i])
        if not piece or not remainder.startswith(piece):
            break
        remainder = remainder[len(piece) :]
        i += 1
    return i


def _is_next_heading(match: re.Match[str] | None, chapter: int, sections: list[dict]) -> bool:
    if not match or int(match[1]) != chapter:
        return False
    n = int(match[2])
    if n == len(sections) + 1:
        return True
    # A repeated number, as printed in the book, but only with a different title.
    return (
        bool(sections)
        and n == int(sections[-1]["number"].split(".")[1])
        and (_norm(match[3]) != _norm(sections[-1]["title"]))
    )


def build_chapter(
    pages: list[str],
    *,
    part: int,
    chapter: int,
    title: str,
    section_titles: dict[str, str] | None = None,
) -> Chapter:
    """Split one chapter into intro, numbered sections and answer key.

    `section_titles` maps a section number to its full title, for headings that wrap
    onto a second line in the PDF; the continuation lines are dropped from the text.
    """
    section_titles = section_titles or {}
    split = answer_key_start(pages)
    body, key = pages[:split], pages[split:]

    cleaned = [clean_page(raw, index=i, chapter=chapter, title=title) for i, raw in enumerate(body)]
    book_pages = _book_page_numbers([num for _, num in cleaned])

    intro: list[str] = []
    sections: list[dict] = []
    for (lines, _), page in zip(cleaned, book_pages, strict=True):
        i = 0
        while i < len(lines):
            line = lines[i]
            i += 1
            match = _SECTION_HEADING.match(line.strip())
            if _is_next_heading(match, chapter, sections):
                number = f"{chapter}.{match[2]}"
                seen = match[3].strip()
                full = section_titles.get(number)
                if full:
                    i = _consume_title_continuation(lines, i, seen, full)
                sections.append(
                    {
                        "number": number,
                        "title": full or seen,
                        "page_start": page,
                        "page_end": page,
                        "lines": [],
                    }
                )
                continue
            if sections:
                sections[-1]["lines"].append(line)
                sections[-1]["page_end"] = page
            else:
                intro.append(line)

    answer_lines = [
        ln
        for raw in key
        for ln in (x.rstrip() for x in raw.splitlines())
        if ln.strip() and not any(p.search(ln.strip()) for p in _FURNITURE)
    ]

    return Chapter(
        part=part,
        chapter=chapter,
        title=title,
        page_start=book_pages[0] if book_pages else 1,
        page_end=book_pages[-1] if book_pages else 1,
        intro="\n".join(intro),
        sections=[
            Section(
                number=s["number"],
                title=s["title"],
                page_start=s["page_start"],
                page_end=s["page_end"],
                text="\n".join(s["lines"]),
            )
            for s in sections
        ],
        answers="\n".join(_SPACE_BEFORE_PUNCT.sub(r"\1", ln) for ln in answer_lines),
    )
