"""LLM call #2 — simulation generation.

Same shape as every generation task: mark running, call the model, validate, write
the artifact, mark succeeded. A malformed response is a failed job with the raw
text kept, never a crash.

The manifest is *not* generated here. It is projected from the accepted blueprint
by `manifest_from_plan`, so what ships is exactly what the teacher reviewed, and
this call writes `core_html` alone.
"""

import logging
import uuid

from src.job.models import GenerationJob, JobStatus
from src.lab.models import Lab, LabStatus
from src.llm.client import LLMOutputError, structured_completion
from src.llm.prompts import SIM_CORE_CONTRACT, sim_core_user_prompt
from src.llm.schemas import CORE_SCHEMA, CoreOutput, Manifest, Plan, manifest_from_plan
from src.plan.models import PlanVersion
from src.simulation.models import MAIN_COMPONENT, Simulation
from src.simulation.styles import inject_tokens
from src.simulation.validate import validate_core
from src.tasks.base import run_async
from src.worker import app

logger = logging.getLogger(__name__)


def _generate_core(*, plan: Plan, manifest: Manifest) -> tuple[str, dict]:
    """One attempt, then one retry — but the retry is told exactly what failed.

    This is the difference between a grounded loop and self-critique: the model
    never reviews its own code, it is handed a deterministic verdict on it. A
    second failure is a failed job, not a third attempt — three 90-second calls is
    long enough that a teacher assumes the product is broken.
    """
    user = sim_core_user_prompt(plan=plan.model_dump(), manifest=manifest.model_dump())

    core, raw = structured_completion(
        system=SIM_CORE_CONTRACT,
        user=user,
        schema=CORE_SCHEMA,
        schema_name="simulation_core",
        model_cls=CoreOutput,
        # Simulation generation runs against real OpenAI, not Ollama: core_html
        # is the artifact a teacher and students actually see, so it gets the
        # stronger model.
        provider="openai",
    )
    problems = validate_core(core.core_html, manifest)
    if not problems:
        return core.core_html, raw

    logger.warning("Core rejected by the gate, retrying once: %s", problems)
    core, raw = structured_completion(
        system=SIM_CORE_CONTRACT,
        user=(
            f"{user}\n\nYour previous attempt was rejected for these reasons. "
            "Fix every one of them and return the complete document again:\n"
            + "\n".join(f"- {problem}" for problem in problems)
        ),
        schema=CORE_SCHEMA,
        schema_name="simulation_core",
        model_cls=CoreOutput,
        provider="openai",
    )
    remaining = validate_core(core.core_html, manifest)
    if remaining:
        raise LLMOutputError(
            "The generated simulation did not meet the contract: " + " ".join(remaining),
            raw=core.core_html,
        )
    return core.core_html, raw


async def _run(job_id: str) -> str:
    job = await GenerationJob.get(id=uuid.UUID(job_id))
    job.status = JobStatus.RUNNING
    await job.save()

    lab = await Lab.get(id=job.lab_id)
    plan_version = await PlanVersion.get(id=lab.active_plan_id)

    try:
        # Re-validated here as well as in the route: the route's check proves the
        # teacher can start the job, this one proves the worker can finish it, and
        # between the two a revision could have re-pointed active_plan_id.
        plan = Plan(**plan_version.plan_json)
        manifest = manifest_from_plan(plan)
        core_html, raw = _generate_core(plan=plan, manifest=manifest)
    except LLMOutputError as exc:
        job.status = JobStatus.FAILED
        job.error = str(exc)[:4000]
        await job.save()
        logger.exception("Simulation generation failed for job %s", job_id)
        return "failed"
    except Exception as exc:  # noqa: BLE001 — a task must never crash the worker
        job.status = JobStatus.FAILED
        job.error = f"{type(exc).__name__}: {exc}"[:4000]
        await job.save()
        logger.exception("Simulation generation errored for job %s", job_id)
        return "failed"

    # Append-only: regenerating produces a new version and re-points is_current.
    # Demote first — the partial unique index forbids two current rows, so doing
    # this the other way round would fail the insert.
    await Simulation.filter(lab_id=lab.id, component_ref=MAIN_COMPONENT, is_current=True).update(
        is_current=False
    )
    last = (
        await Simulation.filter(lab_id=lab.id, component_ref=MAIN_COMPONENT)
        .order_by("-version")
        .first()
    )
    simulation = await Simulation.create(
        lab_id=lab.id,
        component_ref=MAIN_COMPONENT,
        version=(last.version + 1) if last else 1,
        manifest_json=manifest.model_dump(),
        core_html=inject_tokens(core_html),
        raw_llm_response=raw,
        is_current=True,
    )

    lab.status = LabStatus.SIM_READY
    await lab.save()

    job.status = JobStatus.SUCCEEDED
    job.artifact_id = simulation.id
    await job.save()

    logger.info("Simulation v%s generated for lab %s", simulation.version, lab.id)
    return "succeeded"


@app.task(
    name="src.tasks.simulation.generate_simulation",
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    max_retries=2,
)
def generate_simulation(self, job_id: str) -> str:  # noqa: ARG001
    return run_async(_run(job_id))
