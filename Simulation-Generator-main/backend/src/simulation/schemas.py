from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class SimulationRead(BaseModel):
    """One simulation, whole.

    `core_html` is returned in full rather than behind a second request: the
    workspace cannot render anything without the document, so splitting it would
    only add a round trip to the one screen that needs both halves at once.
    """

    id: UUID
    lab_id: UUID
    component_ref: str
    version: int
    manifest_json: dict[str, Any]
    core_html: str
    is_current: bool
    change_summary: str | None = None
    created_at: datetime


class SimulationSummary(BaseModel):
    """A row in the version list. Deliberately without `core_html`.

    The history sidebar renders dozens of these; shipping a full document per
    entry to draw a list of version numbers would be absurd.
    """

    id: UUID
    version: int
    is_current: bool
    change_summary: str | None = None
    created_at: datetime
