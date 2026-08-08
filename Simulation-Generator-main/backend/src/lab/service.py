"""Shared lab reads.

A lab's human-readable title is derived, never stored: `plan_json.title` once a
plan exists, a truncation of the prose before that.
"""

from typing import Any

from src.lab.models import Lab
from src.lab.schemas import LabRead
from src.plan.models import PlanVersion
from src.simulation.models import MAIN_COMPONENT, Simulation

TITLE_FALLBACK_CHARS = 70


def derive_title(description: str, plan_json: dict[str, Any] | None) -> str:
    if plan_json and plan_json.get("title"):
        return str(plan_json["title"])
    text = " ".join(description.split())
    if len(text) <= TITLE_FALLBACK_CHARS:
        return text
    return text[:TITLE_FALLBACK_CHARS].rsplit(" ", 1)[0] + "…"


async def latest_plan(lab_id) -> PlanVersion | None:
    return await PlanVersion.filter(lab_id=lab_id).order_by("-version").first()


async def read_lab(lab: Lab) -> LabRead:
    """Assemble the lab detail payload the plan review screen renders from."""
    await lab.fetch_related("course")
    plan = await latest_plan(lab.id)
    plan_json = plan.plan_json if plan else None
    current = await Simulation.get_or_none(
        lab_id=lab.id, component_ref=MAIN_COMPONENT, is_current=True
    )

    return LabRead(
        id=lab.id,
        course_id=lab.course.id,
        course_title=lab.course.title,
        description=lab.description,
        audience=lab.audience,
        status=lab.status,
        title=derive_title(lab.description, plan_json),
        active_plan_id=lab.active_plan_id,
        latest_plan_id=plan.id if plan else None,
        latest_plan_version=plan.version if plan else None,
        latest_plan_json=plan_json,
        latest_plan_decision=plan.decision if plan else None,
        current_simulation_id=current.id if current else None,
        created_at=lab.created_at,
    )
