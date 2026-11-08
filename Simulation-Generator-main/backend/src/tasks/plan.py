"""LLM call #1 — plan generation.

Same shape as every generation task: mark running, call the model, validate, write
the artifact, mark succeeded. A malformed response is a failed job with the raw
text kept, never a crash.
"""

import logging
import uuid

from src.config.settings import settings
from src.job.models import GenerationJob, JobStatus
from src.lab.models import Lab, LabStatus
from src.llm.client import LLMOutputError, structured_completion
from src.llm.coherence import check_coherence
from src.llm.prompts import (
    PLAN_SYSTEM_PROMPT,
    plan_revision_user_prompt,
    plan_user_prompt,
    textbook_source_block,
)
from src.llm.schemas import PLAN_SCHEMA, Plan
from src.plan.models import PlanDecision, PlanVersion
from src.tasks.base import run_async
from src.textbook.library import resolve_ref
from src.worker import app

logger = logging.getLogger(__name__)


def _complete(user: str) -> tuple[Plan, dict]:
    return structured_completion(
        system=PLAN_SYSTEM_PROMPT,
        user=user,
        schema=PLAN_SCHEMA,
        schema_name="plan",
        model_cls=Plan,
        # Plan generation runs against Ollama, not OpenAI: it's the most-iterated
        # call (draft + every revision), so drafts run locally instead of
        # spending OpenAI budget on each retry.
        provider="ollama",
    )


def _with_retry(*, user: str, retry_note: str) -> tuple[Plan, dict]:
    """One attempt, then one retry — spec §3's reliability rule.

    Two independent things can reject an attempt: the schema, and the coherence
    cross-check. Both get the same single retry, and the retry is told exactly
    which one rejected it. A blueprint that still contradicts itself fails the
    job with a teacher-readable reason — the same path as malformed JSON, because
    a plan whose rules do not match its own controls is just as unusable.
    """
    try:
        plan, raw = _complete(user)
        problems = check_coherence(plan)
        if not problems:
            return plan, raw
        logger.warning("Plan is incoherent, retrying once: %s", problems)
        rejection = "The previous attempt contradicted itself:\n" + _bullets(problems)
    except LLMOutputError as first:
        logger.warning("Plan failed validation, retrying once: %s", first)
        rejection = f"The previous attempt was rejected by validation. {retry_note}"

    plan, raw = _complete(f"{user}\n\n{rejection}")
    problems = check_coherence(plan)
    if problems:
        raise LLMOutputError(
            "This blueprint contradicts itself, so it was not saved.\n\n" + _bullets(problems)
        )
    return plan, raw


def _bullets(problems: list[str]) -> str:
    return "\n".join(f"- {problem}" for problem in problems)


class SourceUnavailable(Exception):
    """The lab names a textbook section the worker cannot read."""


def _source_block(lab: Lab) -> str | None:
    """The textbook block for a grounded lab, or None for an ungrounded one.

    A lab whose section cannot be loaded fails the job rather than drafting without
    it: the teacher asked for a grounded blueprint, and a silently ungrounded one
    would look like it was.
    """
    if not lab.source_ref:
        return None
    section = resolve_ref(lab.source_ref)
    if section is None:
        raise SourceUnavailable(
            "The textbook section this lab is based on could not be loaded, so no "
            "blueprint was drafted. The extracted textbook must be present in "
            "data/textbook/ (see the README)."
        )
    return textbook_source_block(section, max_words=settings.textbook_excerpt_max_words)


def _generate(
    *,
    description: str,
    audience: str,
    course_title: str,
    course_subject: str,
    source: str | None,
):
    return _with_retry(
        user=plan_user_prompt(
            description=description,
            audience=audience,
            course_title=course_title,
            course_subject=course_subject,
            source=source,
        ),
        retry_note=(
            "Return a simulation blueprint that matches the schema exactly. Every control "
            "must be coherent for its type, and no control or readout id may be reused."
        ),
    )


def _revise(
    *,
    plan: dict,
    feedback: str,
    audience: str,
    course_title: str,
    course_subject: str,
    source: str | None,
):
    return _with_retry(
        user=plan_revision_user_prompt(
            plan=plan,
            feedback=feedback,
            audience=audience,
            course_title=course_title,
            course_subject=course_subject,
            source=source,
        ),
        retry_note=(
            "Return the complete revised blueprint matching the schema exactly. Every "
            "control must be coherent for its type, and no control or readout id may "
            "be reused."
        ),
    )


async def _run_revision(job_id: str, feedback: str) -> str:
    job = await GenerationJob.get(id=uuid.UUID(job_id))
    job.status = JobStatus.RUNNING
    await job.save()

    source = await PlanVersion.get(id=job.target_id)
    lab = await Lab.get(id=job.lab_id).prefetch_related("course")
    course = lab.course

    try:
        plan, raw = _revise(
            plan=source.plan_json,
            feedback=feedback,
            audience=lab.audience,
            course_title=course.title,
            course_subject=course.subject,
            source=_source_block(lab),
        )
    except (LLMOutputError, SourceUnavailable) as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)[:4000]
        await job.save()
        logger.exception("Plan revision failed for job %s", job_id)
        return "failed"
    except Exception as exc:  # noqa: BLE001 — a task must never crash the worker
        job.status = JobStatus.FAILED
        job.error = f"{type(exc).__name__}: {exc}"[:4000]
        await job.save()
        logger.exception("Plan revision errored for job %s", job_id)
        return "failed"

    # Write first, supersede second. If anything above failed, the source row is
    # still PENDING and the teacher still has a reviewable blueprint.
    last = await PlanVersion.filter(lab_id=lab.id).order_by("-version").first()
    revised = await PlanVersion.create(
        lab_id=lab.id,
        version=(last.version + 1) if last else 1,
        raw_llm_response=raw,
        plan_json=plan.model_dump(),
        revision_feedback=feedback,
    )
    source.decision = PlanDecision.SUPERSEDED
    await source.save()

    # lab.status stays PLAN_REVIEW and active_plan_id is untouched: only an
    # acceptance points the lab at a plan.
    job.status = JobStatus.SUCCEEDED
    job.artifact_id = revised.id
    await job.save()

    logger.info("Plan revised to v%s for lab %s", revised.version, lab.id)
    return "succeeded"


async def _run(job_id: str) -> str:
    job = await GenerationJob.get(id=uuid.UUID(job_id))
    job.status = JobStatus.RUNNING
    await job.save()

    lab = await Lab.get(id=job.lab_id).prefetch_related("course")
    course = lab.course

    try:
        plan, raw = _generate(
            description=lab.description,
            audience=lab.audience,
            course_title=course.title,
            course_subject=course.subject,
            source=_source_block(lab),
        )
    except (LLMOutputError, SourceUnavailable) as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)[:4000]
        await job.save()
        logger.exception("Plan generation failed for job %s", job_id)
        return "failed"
    except Exception as exc:  # noqa: BLE001 — a task must never crash the worker
        job.status = JobStatus.FAILED
        job.error = f"{type(exc).__name__}: {exc}"[:4000]
        await job.save()
        logger.exception("Plan generation errored for job %s", job_id)
        return "failed"

    # Append-only: a regeneration after a rejection is a new row, never an update.
    last = await PlanVersion.filter(lab_id=lab.id).order_by("-version").first()
    version = (last.version + 1) if last else 1

    plan_version = await PlanVersion.create(
        lab_id=lab.id,
        version=version,
        raw_llm_response=raw,
        plan_json=plan.model_dump(),
    )

    lab.status = LabStatus.PLAN_REVIEW
    await lab.save()

    job.status = JobStatus.SUCCEEDED
    job.artifact_id = plan_version.id
    await job.save()

    logger.info("Plan v%s generated for lab %s", version, lab.id)
    return "succeeded"


@app.task(
    name="src.tasks.plan.generate_plan",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
)
def generate_plan(self, job_id: str) -> str:  # noqa: ARG001
    return run_async(_run(job_id))


@app.task(
    name="src.tasks.plan.revise_plan",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
)
def revise_plan(self, job_id: str, feedback: str) -> str:  # noqa: ARG001
    return run_async(_run_revision(job_id, feedback))
