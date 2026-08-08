# Repository Guidelines

## Project Structure & Module Organization

Simgen is split into a containerized Python backend and a host-run Next.js frontend. Backend code lives in `backend/src/`: domain packages such as `course/`, `lab/`, `plan/`, and `spike/` contain routers, schemas, and models; shared configuration, LLM integration, Celery tasks, and migrations have dedicated packages. `web/app/` contains App Router pages and the BFF proxy, `web/components/` holds reusable UI, `web/lib/` holds API helpers and types, and `web/public/` contains static assets. Read `SIMGEN_POC_SPEC.md`, `SIMGEN_POC_HANDOFF.md`, and `CLAUDE.md` before changing architecture. More specific frontend rules are in `web/AGENTS.md`.

## Build, Test, and Development Commands

- `docker compose up --build`: build and run nginx, FastAPI, Celery, PostgreSQL, RabbitMQ, and Redis.
- `cd web && npm install && npm run dev`: install frontend dependencies and serve Next.js at `http://localhost:3000`.
- `cd web && npm run lint`: run Next.js ESLint checks.
- `cd web && npm run build`: type-check and create the production frontend build.
- `cd backend && uv sync --dev && uv run ruff check src`: install Python dependencies and lint backend code.
- `cd backend && POSTGRES_HOST=localhost uv run tortoise migrate`: apply migrations from the host. Generate migrations with `tortoise makemigrations`, then review and commit them; never generate them during application startup.

## Coding Style & Naming Conventions

Python targets 3.12, uses four-space indentation, 100-character lines, type hints, and Ruff rules `E`, `F`, `I`, `UP`, and `B`. Use `snake_case` for modules and functions and `PascalCase` for classes. TypeScript uses strict mode and ESLint; use two-space indentation, `PascalCase` component filenames, camelCase functions, and Next.js route conventions such as `app/courses/[id]/page.tsx`. Keep generated migrations unformatted.

## Testing Guidelines

No automated test framework or coverage threshold is configured yet. At minimum, run Ruff, frontend lint, and the production build before submitting. Add focused tests alongside any new test infrastructure, name them by behavior (for example, `test_plan_acceptance.py`), and document the command in the PR.

## Commit & Pull Request Guidelines

Recent commits use short, imperative subjects such as `Add POC spec...` and `Note ... details`. Keep commits focused and explain migration or contract changes in the body. PRs should summarize behavior, list verification commands, link relevant issues/spec sections, flag configuration or schema changes, and include screenshots for UI changes. Never commit `.env` values, API keys, or generated build artifacts.
