"""Extract the Ganita Prakash chapter PDFs into one JSON file of numbered sections.

A developer tool, run once after `data/fetch_ncert_pdfs.sh`. It needs no database and
no running stack. The output is NCERT text, so like the PDFs it is gitignored.

    cd backend
    uv run python scripts/extract_textbook.py
    uv run python scripts/extract_textbook.py --pdfs ../data/pdfs --out ../data/textbook
"""

import argparse
import json
import sys
from pathlib import Path

from pypdf import PdfReader

from src.textbook.catalog import BOOK_TITLE, CHAPTERS, GRADE, SECTION_TITLES, SOURCE
from src.textbook.extract import build_chapter

DATA = Path(__file__).resolve().parents[2] / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--pdfs", type=Path, default=DATA / "pdfs")
    parser.add_argument("--out", type=Path, default=DATA / "textbook")
    args = parser.parse_args()

    missing = [c.filename for c in CHAPTERS if not (args.pdfs / c.filename).is_file()]
    if missing:
        print(f"Missing in {args.pdfs}: {', '.join(missing)}", file=sys.stderr)
        print("Run data/fetch_ncert_pdfs.sh first.", file=sys.stderr)
        return 1

    chapters = []
    for src in CHAPTERS:
        reader = PdfReader(args.pdfs / src.filename)
        pages = [page.extract_text() or "" for page in reader.pages]
        titles = {
            num: t
            for (part, chap, num), t in SECTION_TITLES.items()
            if (part, chap) == (src.part, src.chapter)
        }
        ch = build_chapter(
            pages, part=src.part, chapter=src.chapter, title=src.title, section_titles=titles
        )
        chapters.append(ch.model_dump())
        words = sum(len(s.text.split()) for s in ch.sections) + len(ch.intro.split())
        print(
            f"Part {src.part} ch.{src.chapter:<2} {src.title:<36} "
            f"pp.{ch.page_start}-{ch.page_end}  {len(ch.sections)} sections  {words} words"
            + (f"  + answer key ({len(ch.answers.split())} words)" if ch.answers else "")
        )
        for s in ch.sections:
            print(f"    {s.number:<5} {s.title}  (pp.{s.page_start}-{s.page_end})")

    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "ganita_prakash_grade8.json"
    book = {"book": BOOK_TITLE, "grade": GRADE, "source": SOURCE, "chapters": chapters}
    out.write_text(json.dumps(book, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
