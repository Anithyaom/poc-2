from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.llm.schemas import Plan


class PlanVersionRead(BaseModel):
    id: UUID
    lab_id: UUID
    version: int
    plan_json: dict[str, Any]
    decision: str
    revision_feedback: str | None = None
    created_at: datetime


class PlanRevisionRequest(BaseModel):
    """Revise the current blueprint from the teacher's own words.

    `edits` is optional and carries the whole edited plan, exactly as
    `PlanDecisionRequest` does — so on-screen section edits can be sent together
    with a feedback request instead of forcing the teacher to choose. The route
    persists them as their own pending version before the model runs, so a failed
    revision cannot lose them.
    """

    feedback_text: str = Field(min_length=4, max_length=4000)
    edits: Plan | None = None


class PlanDecisionRequest(BaseModel):
    """Accept, accept an edited copy, or reject.

    `edits` is the **whole edited plan**, not a patch. For the POC that is both
    simpler and safer: the edited document is re-validated by the same `Plan` model
    the LLM output goes through, so a teacher cannot save a plan the generator
    could not have produced — including the parameter ranges, which are binding
    (§6.1).
    """

    decision: Literal["accept", "accept_with_modifications", "reject"]
    edits: Plan | None = None

    @model_validator(mode="after")
    def _edits_match_decision(self) -> "PlanDecisionRequest":
        if self.decision == "accept_with_modifications" and self.edits is None:
            raise ValueError("accept_with_modifications requires `edits`")
        if self.decision != "accept_with_modifications" and self.edits is not None:
            raise ValueError("`edits` is only valid with accept_with_modifications")
        return self
