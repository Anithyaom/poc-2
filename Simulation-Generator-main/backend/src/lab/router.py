from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import ValidationError

from src.job.models import GenerationJob, JobStatus, JobType
from src.job.schemas import JobAccepted
from src.lab.models import Lab
from src.lab.schemas import LabRead, PlanGenerateRequest
from src.lab.service import read_lab
from src.llm.schemas import Plan
from src.plan.models import PlanVersion
from src.simulation.models import Simulation
from src.simulation.schemas import SimulationSummary
from src.tasks.plan import generate_plan
from src.tasks.simulation import generate_simulation

router = APIRouter(prefix="/api/labs", tags=["labs"])


@router.get("/{lab_id}", response_model=LabRead)
async def get_lab(lab_id: UUID) -> LabRead:
    lab = await Lab.get_or_none(id=lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    return await read_lab(lab)


@router.post(
    "/{lab_id}/plan:generate",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_plan_for_lab(
    lab_id: UUID, payload: PlanGenerateRequest | None = None
) -> JobAccepted:
    """Validate, create the job row, dispatch, return. No LLM call inline."""
    lab = await Lab.get_or_none(id=lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")

    # Regenerating after a rejection may carry an edited description — that edit is
    # the whole point of the reject branch.
    if payload:
        if payload.description is not None:
            lab.description = payload.description
        if payload.audience is not None:
            lab.audience = payload.audience
        if payload.description is not None or payload.audience is not None:
            await lab.save()

    job = await GenerationJob.create(
        job_type=JobType.GENERATE_PLAN,
        status=JobStatus.QUEUED,
        lab_id=lab.id,
    )
    task = generate_plan.delay(str(job.id))
    job.celery_task_id = task.id
    await job.save()
    return JobAccepted(job_id=job.id)


@router.post(
    "/{lab_id}/simulations:generate",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_simulation_for_lab(lab_id: UUID) -> JobAccepted:
    """Build the simulation from the accepted blueprint. No LLM call inline."""
    lab = await Lab.get_or_none(id=lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    if lab.active_plan_id is None:
        raise HTTPException(
            status_code=409,
            detail="This lab has no accepted blueprint yet. Accept one first.",
        )

    plan_version = await PlanVersion.get_or_none(id=lab.active_plan_id)
    if plan_version is None:
        raise HTTPException(status_code=409, detail="The accepted blueprint is missing")

    # The accepted row must still validate as a `Plan`, not merely exist. Blueprints
    # written before the current format are still sitting in `plan_accepted` — one
    # holds a retired lesson-plan shape entirely. Without this the ValidationError
    # surfaces as a 500, or worse as a failed job the teacher has to interpret.
    try:
        Plan(**plan_version.plan_json)
    except ValidationError:
        raise HTTPException(
            status_code=409,
            detail=(
                "This blueprint predates the current format and cannot be built from. "
                "Draft a fresh one from the lab description."
            ),
        ) from None

    job = await GenerationJob.create(
        job_type=JobType.GENERATE_SIMULATION,
        status=JobStatus.QUEUED,
        lab_id=lab.id,
        target_id=plan_version.id,
    )
    task = generate_simulation.delay(str(job.id))
    job.celery_task_id = task.id
    await job.save()
    return JobAccepted(job_id=job.id)


@router.get("/{lab_id}/simulations", response_model=list[SimulationSummary])
async def list_simulations(lab_id: UUID) -> list[Simulation]:
    """Version history. Append-only, so this only ever grows."""
    return await Simulation.filter(lab_id=lab_id).order_by("-version")


@router.get("/{lab_id}/plans", response_model=list[dict])
async def list_plan_versions(lab_id: UUID) -> list[dict]:
    """Version history. Append-only, so this only ever grows."""
    versions = await PlanVersion.filter(lab_id=lab_id).order_by("-version")
    return [
        {
            "id": str(v.id),
            "version": v.version,
            "decision": v.decision,
            "title": v.plan_json.get("title"),
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]
