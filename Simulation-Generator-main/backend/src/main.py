import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import RegisterTortoise

from src.config.database import TORTOISE_ORM
from src.config.settings import settings
from src.core.exceptions import register_exception_handlers
from src.course.router import router as course_router
from src.job.router import router as job_router
from src.lab.router import router as lab_router
from src.llm.client import verify_model
from src.plan.router import router as plan_router
from src.simulation.router import router as simulation_router
from src.textbook.router import router as textbook_router

logging.basicConfig(level=logging.DEBUG if settings.debug else logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # generate_schemas=False: migrations own the schema, never runtime auto-creation.
    async with RegisterTortoise(app, config=TORTOISE_ORM, generate_schemas=False):
        # Loud, but not fatal — a dead models endpoint shouldn't stop the API from
        # serving reads. The generation path fails visibly on its own if a key or
        # model id is wrong. Both providers are verified independently since a
        # working Ollama shouldn't mask a broken OpenAI key or vice versa.
        try:
            info = verify_model("openai")
            logger.info(
                "Simulation LLM verified: %s (provider=openai, owned_by=%s)",
                info["id"],
                info["owned_by"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Could not verify OPENAI_MODEL=%s: %s. Simulation generation will fail "
                "until this is fixed.",
                settings.openai_model,
                exc,
            )
        try:
            info = verify_model("ollama")
            logger.info(
                "Plan LLM verified: %s (provider=ollama, owned_by=%s)",
                info["id"],
                info["owned_by"],
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Could not verify OLLAMA_MODEL=%s at OLLAMA_BASE_URL=%s: %s. Plan "
                "generation will fail until this is fixed.",
                settings.ollama_model,
                settings.ollama_base_url,
                exc,
            )
        yield


app = FastAPI(title="simgen API", version="0.1.0", debug=settings.debug, lifespan=lifespan)

# Near-vestigial under the BFF (the browser only ever talks to Next.js), kept for
# direct API poking during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(course_router)
app.include_router(lab_router)
app.include_router(plan_router)
app.include_router(job_router)
app.include_router(simulation_router)
app.include_router(textbook_router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "simulation_model": settings.openai_model,
        "plan_model": settings.ollama_model,
    }
