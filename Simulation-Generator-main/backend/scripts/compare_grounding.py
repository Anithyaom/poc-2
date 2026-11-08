"""Draft each case twice, without and with its textbook section, and write a report.

Step 4 of textbook grounding: does the section actually change the blueprint? Each
case runs through the production path (`_with_retry`: schema validation, the coherence
check, one retry) against the plan model in the repo-root .env (Ollama by default).
Nothing touches the database. Expect a few minutes per draft on a local model.

    cd backend
    PYTHONPATH=. uv run python scripts/compare_grounding.py              # default cases
    PYTHONPATH=. uv run python scripts/compare_grounding.py --dry-run    # prompts only
    PYTHONPATH=. uv run python scripts/compare_grounding.py \\
        --case gp8:p1:c1:s1 "Students explore which numbers are perfect squares."

The report lands in data/grounding_runs/<timestamp>/ (gitignored: it quotes the book).
Read the two blueprints for each case side by side. "Book terms" is only a hint: the
distinctive words of the section that each blueprint uses, which the teacher's
description did not already supply.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from scripts.try_plan import render
from src.config.settings import settings
from src.llm.client import LLMOutputError
from src.llm.prompts import (
    PLAN_SYSTEM_PROMPT,
    plan_user_prompt,
    strip_diagram_labels,
    textbook_source_block,
)
from src.llm.schemas import Plan
from src.tasks.plan import _with_retry
from src.textbook.library import resolve_ref

OUT = Path(__file__).resolve().parents[2] / "data" / "grounding_runs"

# Sections picked because a simulation suits them, across both parts of the book.
DEFAULT_CASES = [
    (
        "gp8:p2:c2:s4",
        "Let students rearrange squares to see why the two smaller squares on a right "
        "triangle fill the big one.",
    ),
    (
        "gp8:p1:c1:s1",
        "Help students see which numbers are perfect squares and how square numbers grow.",
    ),
    (
        "gp8:p2:c7:s1",
        "Students should discover that shapes with the same area can look very different.",
    ),
]

RETRY_NOTE = (
    "Return a simulation blueprint that matches the schema exactly. Every control "
    "must be coherent for its type, and no control or readout id may be reused."
)

_WORD = re.compile(r"[A-Za-zĀ-ſ]{5,}|\d{2,}")


def _terms(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text)}


def book_terms(plan: Plan, excerpt: str, already_given: str) -> list[str]:
    """Distinctive section words the blueprint uses that the prompt did not supply."""
    used = _terms(json.dumps(plan.model_dump(), ensure_ascii=False))
    return sorted((used & _terms(excerpt)) - _terms(already_given))


def _draft(user: str) -> tuple[Plan | None, str | None, float]:
    start = time.monotonic()
    try:
        plan, _ = _with_retry(user=user, retry_note=RETRY_NOTE)
        return plan, None, time.monotonic() - start
    except LLMOutputError as exc:
        return None, str(exc), time.monotonic() - start
    except Exception as exc:  # noqa: BLE001 — one failed draft must not stop the run
        return None, f"{type(exc).__name__}: {exc}", time.monotonic() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--case",
        nargs=2,
        action="append",
        metavar=("REF", "DESCRIPTION"),
        help="A section ref and the teacher's description; repeatable",
    )
    parser.add_argument("--audience", default="Grade 8")
    parser.add_argument("--course", default="Maths 8")
    parser.add_argument("--subject", default="Mathematics")
    parser.add_argument("--dry-run", action="store_true", help="Build prompts, call nothing")
    args = parser.parse_args()

    cases = [tuple(c) for c in args.case] if args.case else DEFAULT_CASES
    sections = {}
    for ref, _ in cases:
        section = resolve_ref(ref)
        if section is None:
            print(f"Unknown section {ref!r} (or no textbook in {settings.textbook_dir})")
            return 2
        sections[ref] = section

    run_dir = OUT / datetime.now().strftime("%Y%m%d-%H%M%S")
    if not args.dry_run:
        run_dir.mkdir(parents=True)

    report = [
        "# Textbook grounding comparison\n",
        f"Model: `{settings.ollama_model}` at `{settings.ollama_base_url}` · excerpt cap "
        f"{settings.textbook_excerpt_max_words} words · audience {args.audience}\n",
    ]
    context = dict(audience=args.audience, course_title=args.course, course_subject=args.subject)

    for n, (ref, description) in enumerate(cases, start=1):
        section = sections[ref]
        block = textbook_source_block(section, max_words=settings.textbook_excerpt_max_words)
        excerpt = strip_diagram_labels(section.text)
        prompts = {
            "ungrounded": plan_user_prompt(description=description, **context),
            "grounded": plan_user_prompt(description=description, source=block, **context),
        }
        heading = (
            f"## {n}. §{section.number} {section.title} — Part {section.part}, "
            f"Ch. {section.chapter} {section.chapter_title} (pp. {section.page_start}–"
            f"{section.page_end})\n\n**Teacher:** {description}\n"
        )
        report.append(heading)
        print(heading.splitlines()[0].removeprefix("## "))

        for label, user in prompts.items():
            words = len(PLAN_SYSTEM_PROMPT.split()) + len(user.split())
            print(f"  {label:<10} prompt {words} words (system + user)", end="", flush=True)
            if args.dry_run:
                print()
                continue
            plan, error, seconds = _draft(user)
            print(f"  -> {'ok' if plan else 'FAILED'} in {seconds:.0f}s")
            stem = f"{n}_{label}"
            report.append(f"### {label.capitalize()} ({seconds:.0f}s)\n")
            if plan is None:
                report.append(f"Failed:\n\n```\n{error}\n```\n")
                continue
            (run_dir / f"{stem}.json").write_text(
                json.dumps(plan.model_dump(), ensure_ascii=False, indent=2) + "\n"
            )
            terms = book_terms(plan, excerpt, description + PLAN_SYSTEM_PROMPT)
            report.append(f"Book terms ({len(terms)}): {', '.join(terms) or '—'}\n")
            report.append(f"```\n{render(plan)}\n```\n")

    if args.dry_run:
        return 0
    path = run_dir / "report.md"
    path.write_text("\n".join(report), encoding="utf-8")
    print(f"\nWrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
