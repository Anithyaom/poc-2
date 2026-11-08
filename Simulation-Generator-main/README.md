# simgen

A teacher opens a course, describes a simulation in plain English, and simgen generates a
teacher-readable **blueprint**, then a working **interactive simulation** from the approved
blueprint, then refines that simulation from natural-language feedback.

This is a proof of concept of the creator-side authoring pipeline only — no publishing, no
real auth, nothing student-facing.

**Current state:** course/lab intake → blueprint review → generated simulation works end to
end. The refinement loop is the remaining stage.

## Stack

Next.js frontend (runs on your host) → nginx → FastAPI → Postgres, with generation handled by
a Celery worker over RabbitMQ and Redis as the result backend. The backend is dockerised; the
frontend deliberately is not.

## Prerequisites

- Docker + Docker Compose
- Node.js 20+ and npm
- [uv](https://docs.astral.sh/uv/) — for migrations and tests
- An OpenAI API key with access to `gpt-5.5` — powers simulation generation (LLM call #2)
- [Ollama](https://ollama.com/) running on the host with `qwen3:4b` pulled (`ollama pull
  qwen3:4b`) — powers plan generation (LLM call #1)

## Setup

```bash
cp .env.example .env
```

Fill in the three values marked `# set me`: `POSTGRES_PASSWORD`, `RABBITMQ_PASSWORD`, and
`OPENAI_API_KEY`. Keep comments on their own lines — Compose does not strip inline `#`
comments from values.

Simulation generation (LLM call #2) always uses OpenAI. Plan generation (LLM call #1) uses
Ollama by default via `OLLAMA_BASE_URL`/`OLLAMA_MODEL`; point those at any other
OpenAI-compatible endpoint (including OpenAI itself) if you'd rather not run Ollama locally.

`web/.env.local` is gitignored, so create it:

```bash
printf 'BACKEND_URL=http://localhost:80\n' > web/.env.local
```

Start the backend (migrations apply on boot):

```bash
docker compose up -d --build
```

Then the frontend:

```bash
cd web && npm install && npm run dev
```

Open http://localhost:3000.

## First run

Create a course, then a lab, and describe the simulation you want. Review the generated
blueprint and accept it; a second job generates the simulation, which lands at
`/labs/<id>/sim`. Auth is faked in local dev — there is no login screen.

## Commands

```bash
docker compose up -d --build       # backend stack
docker compose logs -f             # follow its logs
cd web && npm run dev              # frontend
cd backend && uv run pytest        # tests
cd backend && uv run ruff check .  # lint
data/fetch_ncert_pdfs.sh           # download Ganita Prakash Grade 8 PDFs into data/pdfs/
cd backend && PYTHONPATH=. uv run python scripts/extract_textbook.py  # -> data/textbook/*.json
```

The extracted textbook is mounted read-only into `api` and the worker; once it exists, the
new-lab form offers an optional Ganita Prakash section to ground the blueprint in.

Migrations apply automatically when the stack boots. If you change a model, generate the
migration yourself and commit it:

```bash
cd backend
POSTGRES_HOST=localhost uv run tortoise makemigrations
```

## Layout

```
backend/src/
  course/ lab/ plan/ simulation/ job/   # routers, models, schemas per domain
  llm/          # prompts and structured-output schemas
  tasks/        # Celery tasks
  migrations/
web/
  app/          # Next.js App Router; app/api/** proxies to the backend
  components/   # the control UI rendered around each simulation
```

`SIMGEN_POC_SPEC.md` is the build reference — architecture, data model, API, LLM contracts.
`SIMGEN_POC_HANDOFF.md` covers scope and the decision log; read it before changing the stack
or architecture.

## Terminology

- **Course** — a folder of labs.
- **Lab** — one authored artifact: description, plan, simulation versions.
- **Shell** — the host-rendered control UI.
- **Core** — the generated sandboxed simulation document.
- **Manifest** — the JSON contract describing a simulation's parameters and readouts.
