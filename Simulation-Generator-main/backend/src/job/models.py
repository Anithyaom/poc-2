from enum import StrEnum

from tortoise import fields
from tortoise.models import Model


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobType(StrEnum):
    GENERATE_PLAN = "generate_plan"
    REVISE_PLAN = "revise_plan"
    GENERATE_SIMULATION = "generate_simulation"
    EDIT_SIMULATION = "edit_simulation"
    # No SPIKE_SIMULATION: nothing dispatches it any more. `job_type` is a plain
    # CharField, so the milestone-0 rows keep their own string and still read back.


class GenerationJob(Model):
    """Domain-level status of a background generation.

    This — not Celery's result backend — is what the frontend polls. Redis holds
    task-level state the UI never reads.
    """

    id = fields.UUIDField(primary_key=True)
    job_type = fields.CharField(max_length=64)
    status = fields.CharField(max_length=32, default=JobStatus.QUEUED)

    # Nullable: milestone-0 spike jobs had no lab. Every job type that remains sets
    # it, but the historical rows do not, so the column stays permissive.
    lab_id = fields.UUIDField(null=True)
    # What the job acts on (e.g. the plan component / simulation being edited).
    target_id = fields.UUIDField(null=True)
    # What the job produced, once it succeeds.
    artifact_id = fields.UUIDField(null=True)

    celery_task_id = fields.CharField(max_length=255, null=True)
    error = fields.TextField(null=True)

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "generation_jobs"

    def __str__(self) -> str:
        return f"{self.job_type}:{self.id} [{self.status}]"
