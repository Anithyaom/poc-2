from uuid import UUID

from fastapi import APIRouter, HTTPException

from src.job.models import GenerationJob
from src.job.schemas import JobRead

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: UUID) -> GenerationJob:
    """What the frontend polls until the status is terminal.

    Reads Postgres, not Celery's result backend — the UI never depends on
    Celery internals.
    """
    job = await GenerationJob.get_or_none(id=job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
