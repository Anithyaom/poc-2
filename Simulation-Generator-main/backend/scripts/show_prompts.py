"""Print exactly what each LLM call receives, and optionally run call #2.

A developer tool for prompt iteration, not part of the application. Prompts are
assembled from several places — a shared runtime contract, a per-call preamble, a
user message built from database rows — so reading `prompts.py` top to bottom does
not tell you what the model actually sees. This does.

    cd backend

    # every prompt, with its sources and sizes
    PYTHONPATH=. uv run python scripts/show_prompts.py

    # call #2 as it would be sent for a real lab's accepted blueprint
    POSTGRES_HOST=localhost PYTHONPATH=. uv run python scripts/show_prompts.py --lab <uuid>

    # ...and actually generate it, gate it, and write the HTML somewhere openable
    POSTGRES_HOST=localhost PYTHONPATH=. uv run python scripts/show_prompts.py \\
        --lab <uuid> --generate --out /tmp/core.html

`--generate` costs a real API call and about 100 seconds. It writes nothing to the
database, so it is the loop to use while tuning the core contract: edit
`_CORE_RUNTIME_CONTRACT`, run this, open the file, repeat.
"""

import argparse
import asyncio
import json
import sys

from src.llm.prompts import (
    PLAN_SYSTEM_PROMPT,
    SIM_CORE_CONTRACT,
    plan_revision_user_prompt,
    plan_user_prompt,
    sim_core_user_prompt,
)
from src.llm.schemas import Plan, manifest_from_plan

WIDTH = 78


def rule(label: str = "") -> None:
    if not label:
        print("─" * WIDTH)
        return
    print(f"\n╭─ {label} " + "─" * max(0, WIDTH - len(label) - 4))


def block(label: str, source: str, text: str) -> None:
    """One message, with where it comes from and roughly what it costs."""
    rule(label)
    print(f"│  source: {source}")
    print(f"│  {len(text):,} chars ≈ {len(text) // 4:,} tokens")
    rule()
    print(text)


async def load_lab(lab_id: str) -> tuple[Plan, str, str]:
    """The accepted blueprint for a lab, straight from the database."""
    from tortoise import Tortoise

    from src.config.database import TORTOISE_ORM

    await Tortoise.init(config=TORTOISE_ORM)
    try:
        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(
            """
            SELECT p.plan_json, p.version, l.audience
              FROM labs l JOIN plan_versions p ON p.id = l.active_plan_id
             WHERE l.id = $1
            """,
            [lab_id],
        )
        if not rows:
            sys.exit(f"Lab {lab_id} has no accepted blueprint.")
        raw = rows[0]["plan_json"]
        data = json.loads(raw) if isinstance(raw, str) else raw
        try:
            plan = Plan(**data)
        except Exception as exc:  # noqa: BLE001
            sys.exit(f"That blueprint does not validate as a Plan — {exc}")
        return plan, f"v{rows[0]['version']}", rows[0]["audience"]
    finally:
        await Tortoise.close_connections()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lab", help="build call #2's prompt from this lab's accepted blueprint")
    parser.add_argument("--generate", action="store_true", help="actually run call #2")
    parser.add_argument("--out", default="core.html", help="where --generate writes the document")
    parser.add_argument("--call", choices=["1", "2"], help="show only this call")
    args = parser.parse_args()

    if args.call != "2":
        block(
            "CALL #1 · system — blueprint generation",
            "PLAN_SYSTEM_PROMPT",
            PLAN_SYSTEM_PROMPT,
        )
        block(
            "CALL #1 · user — a first draft",
            "plan_user_prompt(description, audience, course_title, course_subject)",
            plan_user_prompt(
                description="<the teacher's prose>",
                audience="<audience>",
                course_title="<course>",
                course_subject="<subject>",
            ),
        )
        block(
            "CALL #1 · user — a revision (same system prompt, same schema)",
            "plan_revision_user_prompt(plan, feedback, ...)",
            plan_revision_user_prompt(
                plan={"…": "the current blueprint, in full"},
                feedback="<the teacher's words>",
                audience="<audience>",
                course_title="<course>",
                course_subject="<subject>",
            ),
        )

    if args.call == "1":
        return

    block(
        "CALL #2 · system — simulation core",
        "SIM_CORE_CONTRACT = preamble + _CORE_RUNTIME_CONTRACT (shared with the spike)",
        SIM_CORE_CONTRACT,
    )

    if not args.lab:
        print("\nPass --lab <uuid> to see call #2's user message for a real blueprint.")
        return

    plan, version, audience = asyncio.run(load_lab(args.lab))
    manifest = manifest_from_plan(plan)
    user = sim_core_user_prompt(plan=plan.model_dump(), manifest=manifest.model_dump())

    block(
        f"CALL #2 · user — {plan.title!r} (blueprint {version}, {audience})",
        "sim_core_user_prompt(plan, manifest)",
        user,
    )

    if not args.generate:
        return

    import time

    from src.llm.client import LLMOutputError, structured_completion
    from src.llm.schemas import CORE_SCHEMA, CoreOutput
    from src.simulation.styles import inject_tokens
    from src.simulation.validate import validate_core

    rule("GENERATING")
    started = time.time()
    try:
        core, _ = structured_completion(
            system=SIM_CORE_CONTRACT,
            user=user,
            schema=CORE_SCHEMA,
            schema_name="simulation_core",
            model_cls=CoreOutput,
        )
    except LLMOutputError as exc:
        sys.exit(f"Call #2 failed: {exc}")

    html = core.core_html
    print(f"│  {time.time() - started:.0f}s · {len(html):,} chars ≈ {len(html) // 4:,} tokens")

    problems = validate_core(html, manifest)
    if problems:
        print("│  GATE REJECTED — the task would retry once with exactly these:")
        for problem in problems:
            print(f"│    - {problem}")
    else:
        print("│  gate passed")

    with open(args.out, "w") as handle:
        handle.write(inject_tokens(html))
    print(f"│  wrote {args.out}")
    print("│  NOTE: opened directly it has no host, so controls and readouts are inert.")
    print("│  It is for judging layout, palette, and the drawn scene.")


if __name__ == "__main__":
    main()
