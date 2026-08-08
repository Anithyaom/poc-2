# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

**Milestones 0–3 are built.** The backend stack (nginx, api, celery worker, postgres, rabbitmq, redis) builds and runs, Tortoise migrations apply on boot, and the host-run Next.js app takes a teacher from course/lab intake through blueprint review to a working generated simulation at `/labs/[id]/sim`. **Milestone 4 — the refinement loop (LLM call #3) — is the remaining pipeline stage.**

The milestone-0 spike is **gone** (`src/spike/`, `src/tasks/spike.py`, `web/app/spike/`, and the `spike_simulations` table, dropped in migration `0006`). It proved the risky path — real OpenAI call → Celery → sandboxed sim — before any pipeline sat on top, and the real path has replaced it. Its task shape lives on in `src/tasks/plan.py` and `src/tasks/simulation.py`: job row → running → validate → persist → succeeded, one retry, raw response kept on failure. That is the template milestone 4's task follows too.

- `SIMGEN_POC_SPEC.md` — the build reference. Architecture, data model, REST API, LLM contracts, shell/core protocol, compose file, repo layout.
- `SIMGEN_POC_HANDOFF.md` — orientation: scope line, decision log (with rationale), open decisions, risks.

The **decision log** in the handoff (§4) records locked decisions *and why*. Read it before proposing a change to stack or architecture — several entries exist specifically to stop good decisions being quietly undone. `AI_virtual_lab.md` and `SIMGEN_POC_PLAN.md` are referenced as historical/superseded but are not present in the repo.

## What simgen is

A teacher opens a course, describes a simulation in free-text English prose, and the system generates a teacher-readable simulation blueprint (LLM #1), then a working interactive simulation from the approved blueprint (LLM #2), then refines that simulation from natural-language feedback (LLM #3). The POC is the creator-side authoring pipeline only — it ends at the refinement loop.

**Scope guardrail:** anything past "refine the finished simulation" is v1, not POC. No publishing, no real auth, no student-facing features. The full product vision (offline models, tutoring, assessments) is deliberately excluded; don't let it leak in.

## Settled at milestone 0

Both details the spec flagged as unverified are now confirmed by execution:

1. **Tortoise CLI** — `tortoise-orm 1.1.7` ships `init` / `makemigrations` / `migrate` and reads `[tool.tortoise] tortoise_orm = "..."` from the `pyproject.toml` in its cwd. `tortoise init` must be run once to create the migrations package. Spec §11.0 is correct.
2. **Model ID** — `gpt-5.5`, confirmed against the live models endpoint. `verify_model()` runs at API startup so a typo fails loudly at boot instead of inside a worker.

Environment quirks this machine needs:

- **npm, not pnpm.** `registry.npmjs.org`'s Cloudflare IPs are unreachable from this network (DNS resolves, TCP times out); `.npmrc` points at the `registry.yarnpkg.com` mirror. Delete `.npmrc` once direct access works.
- **Compose does not strip inline `#` comments from `.env` values.** `OPENAI_API_KEY=  # set me` makes the key literally `"# set me"`, which fails as an ASCII-encoding error deep in the SDK. Keep comments on their own lines.

## Commands

The backend is dockerised; the Next.js frontend deliberately is not.

```bash
docker compose up --build          # backend stack: nginx, api, celery worker, postgres, rabbitmq, redis
cd web && npm run dev              # frontend on the host, talks to http://localhost:80
```

Migrations (Tortoise ORM's built-in tooling — **not** Alembic, **not** Aerich). The compose `*_HOST` values are service names, so host-run commands need `POSTGRES_HOST=localhost`:

```bash
cd backend
POSTGRES_HOST=localhost uv run tortoise makemigrations   # developer command; review + commit the generated file
POSTGRES_HOST=localhost uv run tortoise migrate          # also run by the api container's entrypoint.sh on boot
```

`entrypoint.sh` runs `migrate` only. Never add `makemigrations` to it — a running image must not invent schema nobody reviewed.

```bash
cd backend && uv run pytest        # pure functions only; no stack, no network, under a second
```

The suite deliberately covers only the heuristics whose regressions are silent — `check_coherence` today. Everything else is exercised by running the stack.

## Architecture — the load-bearing ideas

These are the things that require reading several spec sections to piece together.

### Shell / core split
The LLM never generates control UI. It generates only the **core**: a self-contained sandboxed simulation document (`core_html`) plus a **manifest** describing parameters and readouts. The **shell** — sliders, toggles, readouts — is rendered by our own React components from that manifest. This keeps every simulation's UI consistent without building a generic rendering engine, and shrinks the generation surface.

The interface between them is the manifest's parameter `id`s and the `postMessage` protocol (`sim:init` / `sim:set` / `sim:ready` / `sim:readout` / `sim:error`). **If the generation prompt and the React shell drift apart, controls silently stop driving the simulation** — spec §7 is the contract for both sides; change them together.

Run controls are not parameters. The manifest's `time_stepped` boolean makes the shell render one fixed Step/Run/Pause/Reset bar, and the core implements `sim:step` / `sim:play` / `sim:pause` / `sim:reset` rather than drawing buttons of its own (spec §7.4).

### Nothing runs an LLM call inline
Every generation is a Celery job. FastAPI validates input, writes a `generation_jobs` row, dispatches the task, returns `202 {job_id}`. The frontend polls `/api/jobs/{id}` until terminal. Domain status lives in Postgres, not Celery internals — Redis is only the result backend, and the UI never reads it.

### The browser never calls FastAPI
Next.js route handlers under `app/api/**` are a BFF that proxies to nginx → FastAPI. `BACKEND_URL` is server-side only and must never become a `NEXT_PUBLIC_` var — that is the whole point of the layer.

### The blueprint owns the simulation
LLM #1 produces one simulation blueprint: interpretation, learning objective, experience, controls, visual elements, readouts, behavior rules, and expected observations. It must never generate lesson sequencing, readings, classroom activities, timings, or teacher notes. The blueprint defaults to a document-style review view; only the section whose Edit button was pressed becomes a form. Internal IDs and manifest terminology stay hidden.

On acceptance, `controls[]` and `readouts[]` are projected into `manifest_json` by deterministic code (`manifest_from_plan`), so **LLM #2 generates `core_html` alone**. The remaining blueprint fields constrain what that core draws and how it behaves. `PLAN_SCHEMA` and `MANIFEST_SCHEMA` build controls from one shared factory (`_parameter_schema` in `src/llm/schemas.py`); defining them separately would allow drift.

This freezes only the *initial* manifest — call #3 may legitimately change it ("add a mass slider"), and append-only versioning keeps the approved v1 rollback-able.

Because the manifest is copied from the control verbatim, a blueprint that contradicts *itself* would ship a control its own rules cannot use. `check_coherence` (`src/llm/coherence.py`) is the deterministic guard: it runs inside the plan task, retries once with the contradictions fed back, then fails the job. **It is tuned for silence, not for coverage** — a false positive rejects a blueprint a teacher would have approved, which is worse than the contradiction it prevents. Before making it stricter, run it over the stored `plan_versions`; every real blueprint must stay quiet.

### Nothing generated is trusted on its own word
Two deterministic gates bracket the LLM calls, and both feed their failures back into exactly one retry rather than asking the model to review itself. `check_coherence` guards the input to generation; `validate_core` (`src/simulation/validate.py`) guards its output — complete document, network-blocking CSP, every handshake message handled, all four transport messages when `time_stepped`, no self-drawn controls, every approved id used. Spec §7.5 is the list; add to it rather than adding prompt pressure.

The same seam injects the design tokens (`src/simulation/styles.py`). The prompt *tells* the model to use the CSS variables; injection *guarantees* they exist — the `data-simgen-tokens` marker is what lets a stored core be restyled later without regenerating it. Roles, never colours: `--sim-primary` means "the object under study". Spec §7.6.

### Versioning is append-only
Nothing is overwritten. A rejected plan, an edited simulation, a rollback — each produces or re-points to a row, never mutates one. Exactly one `simulations` row per `(lab_id, component_ref)` has `is_current = true`, enforced by a **partial unique index written by hand in migration `0005`** — Tortoise's `unique_together` cannot express it, and it would forbid a second historical row.

## Sharp edges

- **Celery is sync; Tortoise is async.** Each task must own its event loop and call `Tortoise.init` / `close_connections` *inside* the task, never at worker startup. A prefork child that inherits a loop or asyncpg pool across the fork fails with "attached to a different loop." Bridge helper is in spec §11.0.
- **Next.js caches Server Component fetches by default**, which hides freshly generated artifacts. Use `cache: 'no-store'` and `export const dynamic = 'force-dynamic'` on every route reading a lab, plan, or simulation.
- **Strict Structured Outputs constrains the schema**: every property must appear in `required`, every object needs `"additionalProperties": false`, and optional means a union with `null`. This is why LLM call #3's two outcomes (edit vs. clarification) share **one** schema with an `outcome` discriminator rather than being two alternative shapes.
- **Sandbox discipline:** `sandbox="allow-scripts"` **without** `allow-same-origin`, plus the network-blocking CSP inside the generated core. Don't loosen either for convenience — the core is generated code.
- **Never trust LLM output.** Schema-validate before persisting; malformed output is a retry-once-then-fail-the-job path with the raw response stored, never a crash.
- **`OPENAI_API_KEY` is required from day one.** The inherited plan marked work "done" while only ever calling a mock; verifying against the real model from milestone 0 is a direct correction of that failure.

## Terminology

**Course** → contains labs. **Lab** → one authored artifact (description, plan, simulation versions); this was called `module` in earlier drafts. **Shell** → host-rendered control UI. **Core** → the LLM-generated sandboxed simulation. **Manifest** → JSON contract describing a sim's parameters and readouts.
