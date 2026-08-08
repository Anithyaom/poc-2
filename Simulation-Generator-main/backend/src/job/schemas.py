from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobAccepted(BaseModel):
    """The 202 body every generation endpoint returns."""

    job_id: UUID


class JobRead(BaseModel):
    id: UUID
    job_type: str
    status: str
    artifact_id: UUID | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
