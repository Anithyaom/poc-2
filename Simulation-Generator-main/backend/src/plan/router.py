from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.job.models import GenerationJob, JobStatus, JobType
from src.job.schemas import JobAccepted
from src.lab.models import Lab, LabStatus
from src.plan.models import PlanDecision, PlanVersion
from src.plan.schemas import PlanDecisionRequest, PlanRevisionRequest, PlanVersionRead
from src.tasks.plan import revise_plan

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("/{plan_id}", response_model=PlanVersionRead)
async def get_plan(plan_id: UUID) -> PlanVersion:
    plan = await PlanVersion.get_or_none(id=plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post(
    "/{plan_id}/revisions",
    response_model=JobAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_changes(plan_id: UUID, payload: PlanRevisionRequest) -> JobAccepted:
    """Revise this blueprint from the teacher's feedback. No LLM call inline.

    Unlike reject-and-redraft, which returns to the original prose and regenerates
    from scratch, this sends the current blueprint *and* the feedback to call #1.
    Everything the teacher did not mention survives.
    """
    plan = await PlanVersion.get_or_none(id=plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.decision != PlanDecision.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Plan v{plan.version} is already {plan.decision}",
        )

    # The teacher's own edits become a version BEFORE the model runs, so a failed
    # revision cannot lose them. PENDING, not ACCEPTED — the review continues.
    source = plan
    if payload.edits is not None:
        plan.decision = PlanDecision.SUPERSEDED
        await plan.save()
        source = await PlanVersion.create(
            lab_id=plan.lab_id,
            version=plan.version + 1,
            raw_llm_response=None,  # a human authored this one by editing
            plan_json=payload.edits.model_dump(),
            decision=PlanDecision.PENDING,
        )

    job = await GenerationJob.create(
        job_type=JobType.REVISE_PLAN,
        status=JobStatus.QUEUED,
        lab_id=plan.lab_id,
        target_id=source.id,
    )
    task = revise_plan.delay(str(job.id), payload.feedback_text)
    job.celery_task_id = task.id
    await job.save()
    return JobAccepted(job_id=job.id)


@router.post("/{plan_id}/decision", response_model=PlanVersionRead)
async def decide(plan_id: UUID, payload: PlanDecisionRequest) -> PlanVersion:
    """Accept, accept an edited copy, or reject. Nothing is ever overwritten.

    An edited acceptance writes a NEW version holding what the teacher actually
    approved, and marks the generated one superseded. That matters because the
    plan owns the manifest (§6.1) — the accepted row is what the simulation is
    built from, so it has to be the edited one.
    """
    plan = await PlanVersion.get_or_none(id=plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.decision != PlanDecision.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Plan v{plan.version} is already {plan.decision}",
        )

    lab = await Lab.get(id=plan.lab_id)

    if payload.decision == "reject":
        plan.decision = PlanDecision.REJECTED
        await plan.save()
        # Back to intake, where the teacher edits the prose and regenerates.
        lab.status = LabStatus.DRAFT
        await lab.save()
        return plan

    accepted = plan
    if payload.decision == "accept_with_modifications":
        plan.decision = PlanDecision.SUPERSEDED
        await plan.save()
        accepted = await PlanVersion.create(
            lab_id=lab.id,
            version=plan.version + 1,
            raw_llm_response=None,  # a human authored this one by editing
            plan_json=payload.edits.model_dump(),
            decision=PlanDecision.ACCEPTED,
        )
    else:
        plan.decision = PlanDecision.ACCEPTED
        await plan.save()

    lab.active_plan_id = accepted.id
    lab.status = LabStatus.PLAN_ACCEPTED
    await lab.save()
    return accepted
