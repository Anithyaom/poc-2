from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=128)


class CourseRead(BaseModel):
    id: UUID
    title: str
    subject: str
    created_at: datetime


class LabSummary(BaseModel):
    """A lab as it appears in a course listing.

    `title` is derived: `plan_json.title` once a plan exists, a truncation of the
    description before that. No title column to keep in sync.
    """

    id: UUID
    title: str
    audience: str
    status: str
    created_at: datetime


class CourseDetail(CourseRead):
    labs: list[LabSummary]
