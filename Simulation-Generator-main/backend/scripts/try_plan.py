"""Run LLM call #1 and print the simulation blueprint as a teacher reads it.

A developer tool for prompt iteration, not part of the application. It needs no
database, no Celery, and no running stack — only OLLAMA_BASE_URL/OLLAMA_MODEL
reachable in the repo-root .env (plan generation runs against Ollama, same as
the real task). Milestone 1 replaces it with the real `generate_plan` task.

    cd backend
    PYTHONPATH=. uv run python scripts/try_plan.py
    PYTHONPATH=. uv run python scripts/try_plan.py "your prose here" --audience "Grade 11"
    PYTHONPATH=. uv run python scripts/try_plan.py --json > plan.json
    PYTHONPATH=. uv run python scripts/try_plan.py --from plan.json --feedback "..."
    PYTHONPATH=. uv run python scripts/try_plan.py "prose" --audience "Grade 8" \\
        --source gp8:p2:c2:s4          # ground it in a textbook section
    PYTHONPATH=. uv run python scripts/try_plan.py --source gp8:p2:c2:s4 --show-prompt
"""

import argparse
import json
import sys
import textwrap

from src.config.settings import settings
from src.llm.client import LLMOutputError, structured_completion
from src.llm.prompts import (
    PLAN_SYSTEM_PROMPT,
    plan_revision_user_prompt,
    plan_user_prompt,
    textbook_source_block,
)
from src.llm.schemas import PLAN_SCHEMA, Plan, manifest_from_plan
from src.textbook.library import load_book, outline, resolve_ref

DEFAULT_DESCRIPTION = (
    "I want students to see why a heavier ball and a lighter ball fall at the "
    "same rate, and what changes when there's air resistance."
)

WIDTH = 76


def _wrap(text: str, indent: str = "") -> str:
    return textwrap.fill(text, width=WIDTH, initial_indent=indent, subsequent_indent=indent)


def _rule(label: str = "") -> str:
    if not label:
        return "─" * WIDTH
    return f"── {label} " + "─" * max(0, WIDTH - len(label) - 4)


def render(plan: Plan) -> str:
    out: list[str] = []
    out.append(_rule())
    out.append(plan.title)
    out.append(f"{plan.inferred_subject} · {plan.inferred_topic}")
    out.append(_rule())

    out.append("\nCONCEPT")
    out.append(_wrap(plan.concept_summary, "  "))

    out.append("\nLEARNING OBJECTIVE")
    out.append(_wrap(plan.learning_objective, "  "))

    out.append("\nWHERE STUDENTS GO WRONG")
    out.append(_wrap(plan.misconception, "  "))

    out.append("\nWHAT STUDENTS SHOULD NOTICE")
    for observation in plan.expected_observations:
        out.append(_wrap(f"· {observation}", "  "))

    out.append("\nSIMULATION EXPERIENCE")
    out.append(_wrap(plan.simulation_experience.summary, "  "))
    out.append(_wrap(f"Opening view: {plan.simulation_experience.initial_state}", "  "))
    for item in plan.simulation_experience.student_actions:
        out.append(_wrap(f"· {item}", "  "))
    out.append(_wrap(f"End/reset: {plan.simulation_experience.completion_state}", "  "))

    out.append("\nSTUDENTS CAN CHANGE")
    for control in plan.controls:
        if control.type == "toggle":
            detail = f"on/off (default {control.default})"
        elif control.type == "dropdown":
            detail = f"{len(control.options or [])} options (default {control.default})"
        else:
            unit = f" {control.unit}" if control.unit else ""
            detail = f"{control.min}–{control.max}{unit}, step {control.step}"
        out.append(f"  {control.label}: {detail}")
        out.append(_wrap(control.rationale, "    "))

    out.append("\nVALUES DISPLAYED")
    for readout in plan.readouts:
        unit = f" ({readout.unit})" if readout.unit else ""
        out.append(_wrap(f"· {readout.label}{unit}: {readout.description}", "  "))

    # Collapsed behind one toggle on the review screen; printed last here to match.
    out.append("\n" + _rule("what the simulation will show and do"))

    out.append("\nVISUAL ELEMENTS")
    for element in plan.visual_elements:
        out.append(_wrap(f"· {element.name}: {element.description}", "  "))

    out.append("\nBEHAVIOR RULES")
    for rule in plan.behavior_rules:
        out.append(_wrap(f"· {rule}", "  "))

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("description", nargs="?", default=DEFAULT_DESCRIPTION)
    parser.add_argument("--audience", default="Grade 9")
    parser.add_argument("--course", default="Grade 9 Physics")
    parser.add_argument("--subject", default="Physics")
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead")
    parser.add_argument(
        "--from",
        dest="from_plan",
        metavar="PLAN.json",
        help="Revise this saved plan (pair with --feedback) instead of drafting a new one",
    )
    parser.add_argument("--feedback", help="Teacher's requested changes; implies a revision")
    parser.add_argument(
        "--source",
        metavar="REF",
        help="Ground in a textbook section, e.g. gp8:p2:c2:s4 ('list' prints every ref)",
    )
    parser.add_argument("--show-prompt", action="store_true", help="Print the user prompt and stop")
    args = parser.parse_args()

    if args.source == "list":
        book = load_book()
        if book is None:
            print(f"No textbook in {settings.textbook_dir}", file=sys.stderr)
            return 1
        for ch in outline(book).chapters:
            print(f"Part {ch.part} ch.{ch.chapter} {ch.title}")
            for s in ch.sections:
                print(f"  {s.ref:<14} {s.number} {s.title}  (pp.{s.page_start}-{s.page_end})")
        return 0

    textbook = None
    if args.source:
        section = resolve_ref(args.source)
        if section is None:
            print(f"Unknown section {args.source!r}; try --source list", file=sys.stderr)
            return 2
        textbook = textbook_source_block(section, max_words=settings.textbook_excerpt_max_words)

    if bool(args.from_plan) != bool(args.feedback):
        print("--from and --feedback must be used together", file=sys.stderr)
        return 2

    if args.feedback:
        with open(args.from_plan) as handle:
            source = json.load(handle)
        user = plan_revision_user_prompt(
            plan=source,
            feedback=args.feedback,
            audience=args.audience,
            course_title=args.course,
            course_subject=args.subject,
            source=textbook,
        )
    else:
        user = plan_user_prompt(
            description=args.description,
            audience=args.audience,
            course_title=args.course,
            course_subject=args.subject,
            source=textbook,
        )

    if args.show_prompt:
        print(user)
        print(f"\n[{len(user.split())} words in the user prompt]", file=sys.stderr)
        return 0

    try:
        plan, raw = structured_completion(
            system=PLAN_SYSTEM_PROMPT,
            user=user,
            schema=PLAN_SCHEMA,
            schema_name="plan",
            model_cls=Plan,
            provider="ollama",
        )
    except LLMOutputError as exc:
        print(f"Generation failed: {exc}", file=sys.stderr)
        if exc.raw:
            print(f"\nRaw response:\n{exc.raw[:4000]}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(raw, indent=2))
        return 0

    print(render(plan))

    # The manifest is projected from the plan, not generated — show exactly what
    # would ship if the teacher accepted this plan unchanged.
    manifest = manifest_from_plan(plan)
    print("\n" + _rule("manifest that would ship"))
    print(json.dumps(manifest.model_dump(), indent=2)[:1800])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
