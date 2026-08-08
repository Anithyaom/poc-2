from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

MIN_DESCRIPTION = 20


class LabCreate(BaseModel):
    """Intake: free-text prose plus one structured field.

    Prose is the primary signal — the model infers subject, topic, and objectives
    from it and echoes them back in the plan for confirmation.
    """

    description: str = Field(min_length=MIN_DESCRIPTION, max_length=4000)
    audience: str = Field(min_length=1, max_length=64)


class PlanGenerateRequest(BaseModel):
    """Optional edits applied before regenerating.

    A rejected plan returns the teacher to intake with the description pre-filled;
    sending the edited prose here is how that edit reaches the next generation.
    """

    description: str | None = Field(default=None, min_length=MIN_DESCRIPTION, max_length=4000)
    audience: str | None = Field(default=None, min_length=1, max_length=64)


class LabRead(BaseModel):
    id: UUID
    course_id: UUID
    course_title: str
    description: str
    audience: str
    status: str
    title: str
    active_plan_id: UUID | None = None
    latest_plan_id: UUID | None = None
    latest_plan_version: int | None = None
    latest_plan_json: dict[str, Any] | None = None
    latest_plan_decision: str | None = None
    # The simulation the workspace renders. Carried on the lab so the page does not
    # have to list every version just to find the one marked current.
    current_simulation_id: UUID | None = None
    created_at: datetime
