# simgen — POC Technical Specification

**Status:** Draft for build · **Scope:** authoring pipeline POC (Intake → Plan → Simulation → Refine) · **Supersedes:** the inherited `AI_virtual_lab.md` plan.

---

## 1. Overview & scope

simgen lets a creator use AI to **draft a simulation blueprint, approve it, generate a working interactive simulation from it, and refine that simulation by talking to it** — all from the frontend. The blueprint is not a lesson plan; every field exists to constrain the generated simulation.

Because the two generative steps (plan, simulation) each take real seconds against an LLM, all generation runs **asynchronously as background jobs** (Celery + RabbitMQ). The frontend enqueues work, then polls a job record until the artifact is ready.

Simulations are produced as **generated code split from host-owned chrome** — the "shell/core" model (§7). The LLM writes only the simulation *core*; the control UI (the *shell*) is rendered by our own React (Next.js) components. This keeps every simulation's UI consistent without building a generic rendering engine.

### In scope
- Course list & a course's labs (the teacher's navigational spine)
- Intake: a free-text English description of the desired lab + grade level
- **LLM call #1** — plan generation (async job)
- Plan review with accept / reject (reject re-generates)
- **LLM call #2** — simulation generation (async job)
- Sandboxed interactive simulation runtime (shell/core)
- **LLM call #3** — scoped, feedback-driven simulation edits (async job)
- Version history + rollback

### Out of scope (deferred to v1)
- Publishing / deployment of finished labs
- Real authentication & multi-user (a stub single user is used)
- Student-facing runtime, tutoring, hints, quizzes, assessments, progress tracking
- Local / on-device models & offline hybrid infra
- Production infra (Terraform, managed services, autoscaling)
- **Determinism / caching of generations** (explicitly parked for the demo — same plan may regenerate a different sim; that's acceptable for the POC)
- Normalized simulation-spec tables + generic renderer

---

## 2. System architecture

```mermaid
graph TD
  subgraph Host["Host machine (not dockerised)"]
    B["Browser"] --> NX["Next.js (App Router)<br/>UI + BFF route handlers"]
  end
  subgraph Docker["docker-compose stack"]
    NX -->|REST via localhost:80| NG["nginx<br/>reverse proxy"]
    NG --> API["FastAPI<br/>API service"]
    API -->|enqueue task| MQ["RabbitMQ<br/>(broker)"]
    MQ --> W["Celery worker(s)"]
    W -->|write artifacts + job status| DB[("PostgreSQL")]
    API -->|read/write| DB
    W -->|task state| R[("Redis<br/>result backend")]
  end
  W -->|OpenAI calls| LLM["OpenAI API<br/>(gpt-5.5)"]
  NX -->|poll job status| NG
```

**Components**
- **Next.js (App Router, on the host)** — the only client, run with `npm run dev` / `npm start` outside Docker for fast iteration. Server Components and route handlers under `app/api/**` act as a **BFF**: the browser talks only to Next.js, and Next.js proxies to nginx → FastAPI. The FastAPI service is never called directly from the browser, so no CORS surface and no API base URL leaks into client bundles.
- **nginx** — the single dockerised entry point (`:80`). Reverse-proxies `/api/**` to FastAPI. Keeps FastAPI itself off published ports and gives real auth/TLS a place to live later.
- **FastAPI** — thin, fast REST layer. Never runs an LLM call inline; it validates input, creates a `generation_jobs` row, dispatches a Celery task, and returns immediately (`202`).
- **RabbitMQ** — Celery broker (task queue).
- **Celery worker(s)** — execute the long-running LLM calls, validate structured output, persist artifacts, and update job status.
- **PostgreSQL** — source of truth for courses, labs, plans, simulations, feedback, and job status. Accessed via Tortoise ORM.
- **Redis** — Celery result backend (task-level state). Domain-level status the frontend reads lives in `generation_jobs` in Postgres, so the UI never depends on Celery internals.
- **OpenAI API** — the three generative calls (`gpt-5.5`, Structured Outputs).

> A real OpenAI call is wired and exercised in the very first build milestone — not stubbed and deferred. This is the one hard lesson carried over from the inherited plan.

---

## 3. Asynchronous generation model

Every generative action follows the same lifecycle. The frontend never waits on an open connection for the LLM.

```mermaid
sequenceDiagram
  participant UI as Browser (Next.js client)
  participant BFF as Next.js route handler
  participant API as FastAPI (via nginx)
  participant MQ as RabbitMQ
  participant W as Celery worker
  participant DB as Postgres
  UI->>BFF: POST /api/.../generate
  BFF->>API: proxy POST
  API->>DB: create generation_jobs (queued)
  API->>MQ: enqueue task(job_id)
  API-->>BFF: 202 { job_id }
  BFF-->>UI: 202 { job_id }
  W->>DB: job -> running
  W->>W: compose prompt, call OpenAI, validate
  W->>DB: write artifact (plan/sim), job -> succeeded (+ artifact_id)
  loop until terminal
    UI->>BFF: GET /api/jobs/{job_id}
    BFF->>API: proxy GET
    API-->>BFF: { status, artifact_id? , error? }
    BFF-->>UI: { status, artifact_id? , error? }
  end
  UI->>BFF: GET artifact by id
```

**Job states:** `queued → running → succeeded | failed`.

**Polling:** the client polls its own `GET /api/jobs/{id}` route handler every ~1.5 s until terminal; the handler forwards to FastAPI (a WebSocket/SSE push is a nice-to-have, not required for the POC).

**Task set (Celery):**
| Task | Trigger | Writes |
|---|---|---|
| `generate_plan` | plan generation request | new `plan_versions` row |
| `generate_simulation` | simulation generation request | new `simulations` row (v1, `is_current`) |
| `edit_simulation` | feedback submission | new `simulations` row (v+1) **or** clarification on the `simulation_feedback` row |

**Reliability:** each task validates the LLM's structured output; on a validation/parse failure it retries once inside the task, then marks the job `failed` with the raw response persisted for debugging (never a crash). Transient network errors use Celery autoretry with backoff.

**Celery config (essentials):**
```python
broker_url = "amqp://guest:guest@rabbitmq:5672//"
result_backend = "redis://redis:6379/0"
task_acks_late = True            # redeliver if a worker dies mid-task
worker_prefetch_multiplier = 1   # long tasks: don't hoard the queue
task_track_started = True
```

---

## 4. Pipeline walkthrough

### 4.1 Teacher's journey

The pipeline hangs off a simple navigational spine — a teacher lands on their courses, opens one, and creates a lab inside it. Generation only begins at step 4.

```mermaid
graph LR
  A["Teacher lands<br/>on dashboard"] --> B["Course list"]
  B --> C["Open a course<br/>(its labs)"]
  C --> D["+ New lab<br/>describe it in prose"]
  D --> E["Plan generated<br/>(LLM #1)"]
  E --> F{"Review"}
  F -->|reject| E
  F -->|accept| G["Simulation generated<br/>(LLM #2)"]
  G --> H["Refine by feedback<br/>(LLM #3)"]
  H --> H
```

A **course** is just a folder with a title and subject ("Grade 9 Physics"). A **lab** is one authored artifact — a description, a plan, and the simulation versions generated from it. Everything from §2 onward operates on a lab.

### 4.2 Stages

| Stage | API entry | Runs as | Persists |
|---|---|---|---|
| 0. Course setup | `POST /api/courses` | sync | `courses` |
| 1. Intake | `POST /api/courses/{id}/labs` | sync | `labs` |
| 2. Plan generation | `POST /api/labs/{id}/plan:generate` | **job** | `plan_versions` |
| 3. Review & decision | `POST /api/plans/{id}/decision` | sync | decision on `plan_versions`, `labs.active_plan_id` |
| 4. Simulation generation | `POST /api/labs/{id}/simulations:generate` | **job** | `simulations` (v1) |
| 5. Refine loop | `POST /api/simulations/{id}/feedback` | **job** | `simulations` (v+1), `simulation_feedback` |
| — | rollback | `POST /api/simulations/{id}/activate` | sync | flips `is_current` |

### 4.3 Intake shape

The teacher writes **free-text English prose** describing the lab they want, plus one structured field for grade level. Prose is the primary signal; the model infers subject, topic, and objectives from it.

```json
{
  "description": "I want students to see why a heavier ball and a lighter ball
                  fall at the same rate, and what changes when there's air resistance.",
  "audience": "Grade 9"
}
```

The model echoes its inferred `subject` and `topic` back in the generated plan, so the teacher confirms the interpretation at plan review rather than being made to type it up front. If the inference is wrong, that's a plan rejection — the same loop that already exists, no extra machinery.

**Reject branch:** a rejected plan returns the teacher to intake with the description pre-filled for editing; regenerating creates a **new** `plan_versions` row. Nothing is overwritten.

**Lab status machine:** `draft → plan_review → plan_accepted → sim_ready → refining`. (No `published` — out of scope.)

---

## 5. Data model

Deliberately lean. The complete blueprint stays embedded in `plan_json`; controls, visuals, and rules are not normalized into separate tables. Nothing is ever overwritten: new state means a new version row.

```mermaid
erDiagram
  courses ||--o{ labs : contains
  labs ||--o{ plan_versions : has
  labs ||--o{ simulations : has
  simulations ||--o{ simulation_feedback : receives
  generation_jobs }o--|| labs : for
  courses {
    uuid id PK
    string title
    string subject
    string owner_sub
    timestamp created_at
  }
  labs {
    uuid id PK
    uuid course_id FK
    text description
    string audience
    string status
    uuid active_plan_id
    timestamp created_at
  }
  plan_versions {
    uuid id PK
    uuid lab_id FK
    int version
    jsonb raw_llm_response
    jsonb plan_json
    string decision
    timestamp created_at
  }
  simulations {
    uuid id PK
    uuid lab_id FK
    string component_ref
    int version
    jsonb manifest_json
    text core_html
    bool is_current
    text change_summary
    timestamp created_at
  }
  simulation_feedback {
    uuid id PK
    uuid simulation_id FK
    text feedback_text
    uuid resulted_in_simulation_id
    text clarification_needed
    timestamp created_at
  }
  generation_jobs {
    uuid id PK
    string job_type
    string status
    uuid lab_id
    uuid target_id
    uuid artifact_id
    string celery_task_id
    text error
    timestamp created_at
    timestamp updated_at
  }
```

`courses.owner_sub` holds the stub dev user's subject claim — the seam real auth drops into later. A lab's human-readable title comes from `plan_json.title` once a plan exists; before that the UI shows a truncation of `description`. No separate `title` column to keep in sync.

Notes:
- `plan_json` is one simulation blueprint: `{ title, inferred_subject, inferred_topic, concept_summary, learning_objective, misconception, simulation_experience, controls[], visual_elements[], readouts[], behavior_rules[], expected_observations[] }`.
- One blueprint describes one simulation. The internal `component_ref` used by simulation versioning is the stable value `main`; it is not shown to teachers.
- `manifest_json` follows the schema in §7 and is **projected from the blueprint, not regenerated** (§6.1). `controls[]` becomes manifest `parameters[]`; teacher-facing rationales and readout descriptions are dropped.
- `core_html` is generated from the complete approved blueprint plus that projected manifest, so visual elements and behavior rules constrain the generated code.

---

## 6. LLM integration

One shared `llm_client` wraps the **OpenAI Python SDK**: model routing, timeout, backoff, and **structured-output validation** against a JSON schema. All three calls run on **`gpt-5.5`** and use **Structured Outputs** (`response_format: { type: "json_schema", json_schema: { strict: true, … } }`), so the model is constrained to the schema rather than merely asked for JSON. The Pydantic model is still re-validated on our side after parsing — strict mode narrows the failure surface, it does not remove it.

```python
# src/llm/client.py — sketch
from openai import OpenAI
client = OpenAI(api_key=settings.openai_api_key, timeout=120.0, max_retries=2)

resp = client.chat.completions.create(
    model=settings.OPENAI_MODEL,           # "gpt-5.5"
    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    response_format={"type": "json_schema",
                     "json_schema": {"name": "plan", "strict": True, "schema": PLAN_SCHEMA}},
)
```

Notes that bite in practice:
- **Strict-mode schema rules:** every property must appear in `required`, and every object needs `"additionalProperties": false`. Optional fields are expressed as a union with `null`, not by omission.
- **Sim generation returns a large `core_html` string** — set a generous `max_completion_tokens` (≥ 16k) and keep the worker's task timeout above the model's.
- **`OPENAI_API_KEY` is required from day one.** Same non-negotiable as before, new provider.

### Call #1 — plan generation
- **Input context:** the teacher's free-text `description`, the lab's `audience` (grade level), and the parent course's `title` + `subject` as framing.
- **Output (validated):** the model must **echo back its inferred `subject` and `topic`**, which is how the teacher confirms it understood the prose.
```json
{
  "title": "string",
  "inferred_subject": "string",
  "inferred_topic": "string",
  "concept_summary": "string",
  "learning_objective": "string",
  "misconception": "string",
  "simulation_experience": {
    "summary": "string", "initial_state": "string",
    "student_actions": ["string"], "completion_state": "string"
  },
  "time_stepped": true,
  "controls": [
    { "id": "length", "label": "Length", "type": "slider",
      "min": 0.2, "max": 3.0, "step": 0.1, "unit": "m",
      "options": null, "default": 1.0, "rationale": "string" }
  ],
  "visual_elements": [{ "name": "Pendulum", "description": "string" }],
  "readouts": [{ "id": "period", "label": "Period", "unit": "s", "description": "string" }],
  "behavior_rules": ["string"],
  "expected_observations": ["string"]
}
```
The plan review screen surfaces `inferred_subject` / `inferred_topic` prominently at the top — a wrong inference is the cheapest possible thing to catch here, and the fix is a plan rejection with an edited description.

#### 6.1 The plan owns the manifest

The blueprint is manifest-shaped where it must be. On acceptance it is **projected into `manifest_json` by deterministic code — no LLM in between** (`manifest_from_plan` in `src/llm/schemas.py`): title, concept, learning objective, controls, and readouts carry through; teacher-facing rationales and descriptions are dropped because the shell has no use for them.

Three consequences, all deliberate:

- **The approval gate is real.** What the teacher signed off is exactly what ships; the plan review screen is not decorative. It also makes plan-stage edits the natural place to fix a bad range — the human is the physics check on a model choosing bounds.
- **Drift between the plan and the manifest is structurally impossible**, rather than something call #2 has to be trusted not to do.
- **Call #2 shrinks to one field.** It writes code, not UX — consistent with the locked "shrink the generation surface" rationale behind the shell/core split.

The cost: the plan-stage model fixes ranges and defaults before anything reasons about the rendering. The prompt compensates by making it reason through the governing equation, the range over which the effect is visible, and real-world anchors *before* committing to bounds. `PLAN_SCHEMA` and `MANIFEST_SCHEMA` build their parameter objects from one shared factory (`_parameter_schema`), so the two shapes cannot drift apart in code either.

**This does not freeze the manifest forever.** The plan owns the *initial* manifest; call #3 may legitimately change it ("add a mass slider"), since refinement is the teacher iterating on the finished artifact. Append-only versioning means the approved v1 is still there to roll back to.

#### 6.2 Teacher-readable blueprint

The stored schema is rendered as familiar form sections; teachers never see JSON keys, control IDs, `component_ref`, or the word manifest.

| Field | Serves |
|---|---|
| `title`, `inferred_subject`, `inferred_topic` | teacher confirms the prose was understood |
| `concept_summary`, `learning_objective`, `misconception` | what the simulation must teach |
| `simulation_experience` | opening state, student actions, and completion/reset behavior |
| `time_stepped` | whether the shell renders its Step/Run/Pause/Reset bar (§7.4) |
| `controls[]` | editable control types, values, defaults, and teaching rationale |
| `visual_elements[]` | what the generated core must draw and animate |
| `readouts[]` | computed values shown by the shell |
| `behavior_rules[]` | observable requirements the generated code must implement |
| `expected_observations[]` | teacher's acceptance checklist for the generated result |

Lesson sequencing, readings, classroom activities, timings, worksheets, assessments, and teacher notes are deliberately absent: they do not constrain the simulation and would misrepresent this product as a lesson planner.

### Call #2 — simulation generation
- **Input context:** the complete approved blueprint + projected manifest (§6.1) + the shell/core contract (§7) as system instructions.
- **Output (validated):** code only — the manifest is already fixed.
```json
{
  "core_html": "<!doctype html> ... self-contained sim core ..."
}
```
The core must honour the given manifest's parameter and readout `id`s verbatim; it has no latitude to rename, add, or drop controls.

> The old two-field `{manifest, core_html}` shape is gone. It survived only in the milestone-0 spike, which predated the plan stage; the spike and its schema were deleted at the end of milestone 3. Call #2 returns `core_html` alone, because the manifest is projected from the approved blueprint (§6.1) and the model must not be able to change it.

### Call #3 — scoped simulation edit (feedback)
- **Input context:** the current `manifest` + `core_html` + the free-text feedback + instruction to make a **targeted** change preserving everything else.
- **Output (validated):** strict Structured Outputs cannot express "one of two shapes," so both branches share **one schema with nullable fields** plus a discriminator:
```json
{
  "outcome": "edited",                       // "edited" | "clarification_needed"
  "manifest": { },                            // null when outcome = clarification_needed
  "core_html": "…",                           // null when outcome = clarification_needed
  "change_summary": "string",                 // null when outcome = clarification_needed
  "clarification_question": null              // set only when outcome = clarification_needed
}
```
The worker branches on `outcome` and asserts the matching fields are non-null before persisting. The ambiguity guard means unclear feedback returns a question instead of a bad edit; the question is stored on `simulation_feedback.clarification_needed` and shown in the UI.

**Validation & retry:** parse JSON → validate against the Pydantic model → for sims, assert `core_html` is present and contains the message-listener contract (basic structural check). On failure: one retry, else fail the job with `raw_llm_response` persisted.

---

## 7. Simulation architecture — the shell / core split

The LLM does **not** generate control UI. It generates only the *core*: a self-contained, sandboxed simulation that receives parameter values and renders. The *shell* — sliders, toggles, layout, readouts — is rendered by our React (Next.js) components from the manifest. Result: identical, on-brand controls across every simulation; a much smaller generation surface; simple, safe sandboxing.

```mermaid
graph LR
  subgraph Host["Host (Next.js client) — the shell"]
    CP["Control panel<br/>rendered from manifest"]
    RO["Readouts"]
    FB["Feedback panel"]
  end
  subgraph Iframe["Sandboxed iframe — the core (LLM-generated)"]
    SIM["Canvas + sim logic"]
  end
  CP -->|"postMessage: sim:set"| SIM
  Host -->|"sim:init"| SIM
  SIM -->|"sim:ready / sim:readout"| Host
```

### 7.1 Manifest schema
```json
{
  "title": "Simple pendulum",
  "concept": "Period vs length and gravity",
  "learning_goal": "See how period depends on length, not mass",
  "time_stepped": true,
  "parameters": [
    { "id": "length",  "label": "Length",  "type": "slider",
      "min": 0.2, "max": 3.0, "step": 0.1, "default": 1.0, "unit": "m" },
    { "id": "gravity", "label": "Gravity", "type": "slider",
      "min": 1.0, "max": 20, "step": 0.1, "default": 9.8, "unit": "m/s^2" },
    { "id": "damping", "label": "Damping", "type": "toggle", "default": false }
  ],
  "readouts": [
    { "id": "period", "label": "Period", "unit": "s" }
  ]
}
```
Parameter `type ∈ {slider, toggle, dropdown, number}`; `dropdown` adds `options[]`.

### 7.2 Sandbox
The core renders in:
```html
<iframe sandbox="allow-scripts" srcdoc={core_html} />
```
No `allow-same-origin` — the core cannot touch the parent app, cookies, or storage. The generated `core_html` must additionally embed a strict CSP that blocks all network access, enforcing the "no external dependencies" rule:
```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:;">
```

### 7.3 postMessage protocol
**Host → core**
| Message | Meaning |
|---|---|
| `{ type: "sim:init", params }` | initial parameter values |
| `{ type: "sim:set", id, value }` | a control changed |
| `{ type: "sim:reset" }` | reset to defaults and return to the opening state |
| `{ type: "sim:play" }` / `{ type: "sim:pause" }` | start / halt time advancing |
| `{ type: "sim:step" }` | advance exactly one step, then hold |

**Core → host**
| Message | Meaning |
|---|---|
| `{ type: "sim:ready" }` | core loaded, ready for `sim:init` |
| `{ type: "sim:readout", values }` | live values for manifest `readouts` |
| `{ type: "sim:error", message }` | runtime failure to surface in the shell |

The generation prompt hands the LLM this contract and requires the core to (a) listen for `sim:init` / `sim:set`, (b) announce `sim:ready`, and (c) use the manifest's parameter `id`s verbatim.

#### 7.4 Run controls — a fixed transport bar, not a generated one

Step, Run, Pause and Reset are the same four actions in every simulation that advances, so they are **not** parameters. The manifest carries a single boolean, `time_stepped`; when it is true the shell renders one fixed Step/Run/Pause/Reset bar in `ControlPanel`, identical for every simulation, and the core implements the four messages above. When it is false the bar is absent and the panel keeps its plain "Reset to defaults" button.

The alternative — an `action` parameter type — was rejected: it would let the model invent its own transport UI per simulation, and it would push a type with no `min`/`max`/`default` through the shared `_parameter_schema` factory. One boolean keeps *the LLM never generates control UI* literally true.

Two consequences worth stating, because both are easy to get wrong:

- **The core must not draw its own Step/Run/Pause/Reset buttons.** Blueprints legitimately say "Press Step" in `student_actions`, and a model reading that will render a button inside the iframe unless explicitly forbidden. `_CORE_RUNTIME_CONTRACT` forbids it by name.
- **Reset is two halves.** The shell returns the controls to their manifest defaults *and* posts `sim:reset` so the core rewinds its own internal state — elapsed time, trails, step counters — which no amount of `sim:set` would clear. Run commands are one-shot events, so the host pushes them through an imperative handle on `SandboxedSimFrame` rather than mirroring them into React state the way parameter values are.

`time_stepped` is set by LLM #1 in the blueprint, reviewed by the teacher on the plan screen ("Students can step, run, pause and reset it"), and carried into the manifest verbatim by `manifest_from_plan` — the same projection guarantee as every other approved field.

### 7.5 The generation gate

A generated core is never persisted on the model's word. `validate_core` (`src/simulation/validate.py`) runs before the row is written and asserts, deterministically:

| Check | Why it is here rather than left to review |
|---|---|
| Complete document — starts `<!doctype html>`, closes `</html>` | A truncated document renders blank; the teacher cannot tell that from a broken simulation |
| CSP present **and** contains `default-src 'none'` | Sandbox discipline. Checked by name, not exact string, so reformatting the attributes still passes |
| `sim:init`, `sim:set`, `sim:ready`, `sim:readout` all handled | A missing handler fails silently — controls simply stop working |
| All four transport messages handled when `time_stepped` | Same failure, confined to the run bar |
| No `<button>`, `<select>` or visible `<input>` | The shell owns every control (§7.4) |
| Every approved parameter and readout id appears verbatim | An unused id is a control wired to nothing |

A failure **retries once with the specific problems fed back** — the model is handed a deterministic verdict, never asked to review its own code. A second failure is a failed job with the raw response kept.

**What this cannot do:** it reads text, it does not run the simulation. It proves the core *mentions* `sim:ready`, not that it fires it, and cannot catch a core that loads and draws nothing. Executing generated code needs a headless browser in the worker image — real weight for a POC — so the teacher remains the runtime check. Everything checked here is a failure a reviewer would struggle to diagnose; everything left unchecked is one they can see at a glance.

### 7.6 Design tokens are injected, not requested

After the gate passes, `inject_tokens` (`src/simulation/styles.py`) writes a host-authored `<style data-simgen-tokens>` block into the core's `<head>`. The prompt *tells* the model to style everything with these CSS custom properties; the injection *guarantees* they exist — a core that invented its own palette would still render, so nothing would ever fail loudly and six simulations would quietly look like six products.

The variables are roles, not colours (`--sim-primary` is "the object under study", not "blue"), which is what lets the palette change without every simulation's semantics changing with it. The three series hues are validated rather than chosen by eye: all-pairs CVD ΔE 9.2, normal-vision ΔE 24.0. A fourth would put yellow beside orange and fail — hence the contract's cap of **three tracked quantities** per core, with folding or a second small view beyond that. Aqua measures 2.74:1 on this surface, so every distinct element carries a visible text label and colour never carries identity alone.

The `data-simgen-tokens` marker is load-bearing: it makes the block findable, so a stored core can be restyled later without regenerating it, and a re-injection replaces rather than stacks. The block is placed at the **top** of `<head>` so a core's own CSS still wins — the tokens make the unstated consistent, they do not overrule intent.

---

## 8. Feedback & versioning loop

1. Creator types feedback on the current simulation.
2. `POST /api/simulations/{id}/feedback` creates a `simulation_feedback` row + a `generation_jobs` row and enqueues `edit_simulation`.
3. Worker runs Call #3 with the current `manifest` + `core_html`.
   - **Edit:** write a new `simulations` row (`version + 1`, `is_current` flipped to it), set `change_summary`, and link `simulation_feedback.resulted_in_simulation_id`.
   - **Clarification:** write `simulation_feedback.clarification_needed`; no new version.
4. Frontend polls the job, then re-fetches the current simulation and version list.
5. **Rollback:** `POST /api/simulations/{id}/activate` flips `is_current` to any prior version — no LLM call.

Because many edits touch only the manifest (e.g. "add a mass slider"), the shell re-renders new controls immediately while the core adapts — the split makes small refinements cheap.

---

## 9. REST API reference

Auth is a stub for the POC (a fixed dev user); endpoints are written so real auth drops in later.

**Two hops, one path shape.** The browser calls Next.js at `/api/<path>`; the route handler forwards verbatim to `${BACKEND_URL}/api/<path>` (nginx → FastAPI). Paths below are the FastAPI routes and are mirrored 1:1 by the BFF, so there is only one URL vocabulary to remember.

```ts
// app/api/[...path]/route.ts — catch-all passthrough
const BACKEND = process.env.BACKEND_URL!; // http://localhost:80 — server-side only, never NEXT_PUBLIC_
```

A catch-all proxy is the right size for the POC. Promote an individual route to a hand-written handler only when it needs to do something extra (response shaping, auth header injection, caching). `BACKEND_URL` must **not** be `NEXT_PUBLIC_` — the whole point of the BFF is that the browser never learns the backend address.

All routes are prefixed `/api`. Routers are split per domain package (`src/course/router.py`, `src/lab/router.py`, …), following the reference backend's layout.

| Method | Path | Body | Returns |
|---|---|---|---|
| `GET` | `/api/courses` | — | `course[]` |
| `POST` | `/api/courses` | `{title, subject}` | `course` |
| `GET` | `/api/courses/{id}` | — | `course` + its `labs[]` |
| `POST` | `/api/courses/{id}/labs` | `{description, audience}` | `lab` |
| `GET` | `/api/labs/{id}` | — | `lab` (+ active plan, current sims) |
| `POST` | `/api/labs/{id}/plan:generate` | — | `202 {job_id}` |
| `GET` | `/api/plans/{id}` | — | `plan_version` |
| `POST` | `/api/plans/{id}/decision` | `{decision, edits?}` | `plan_version` |
| `POST` | `/api/labs/{id}/simulations:generate` | — | `202 {job_id}` |
| `GET` | `/api/simulations/{id}` | — | `simulation` |
| `GET` | `/api/labs/{id}/simulations` | — | `simulation[]` (version list) |
| `POST` | `/api/simulations/{id}/feedback` | `{feedback_text}` | `202 {job_id}` |
| `POST` | `/api/simulations/{id}/activate` | — | `simulation` (rollback) |
| `GET` | `/api/jobs/{id}` | — | `{status, artifact_id?, error?}` |

`decision ∈ {accept, accept_with_modifications, reject}`. `edits` carries the complete edited blueprint. Teachers can change its purpose, experience, control types and values, dropdown options, visuals, readouts, behavior rules, and expected observations. Because the blueprint owns the manifest (§6.1), correcting a control here corrects what actually ships without another LLM call.

---

## 10. Frontend structure

**Next.js (App Router) + TypeScript + Tailwind + shadcn/ui**, run on the host — not dockerised. `npm run dev` for iteration; the backend stack runs alongside in Docker.

**Routes**
| Route | Screen | Rendering |
|---|---|---|
| `/` | Course list — the teacher's landing page | Server Component |
| `/courses/[id]` | One course: its labs + "New lab" | Server Component |
| `/courses/[id]/labs/new` | Intake — prose textarea + grade select | Client (form state) |
| `/labs/[id]/plan` | Blueprint review — document view by default, focused per-section editing, Accept / Modify / Reject | Server shell + Client editor |
| `/labs/[id]/sim` | Simulation workspace — the payoff screen | Client (iframe + live messaging) |
| `/api/[...path]` | BFF passthrough to FastAPI | Route handler |

Labs are addressed at the top level (`/labs/[id]`) rather than nested under their course, so the deep authoring screens don't carry a redundant course id through every URL. The course is reachable from the lab record and shown as a breadcrumb.

**Server vs Client split.** Initial reads (course list, a course's labs, a plan, the current simulation) happen in Server Components calling the backend directly over the Docker-exposed nginx port — no client round trip, no loading flash. Everything reactive (job polling, the sim iframe, controls, feedback) is a Client Component. The simulation workspace is unavoidably client-side: `postMessage` and iframe refs are browser-only.

**Key building blocks**
- `useJob(jobId)` — client hook; polls `/api/jobs/{id}` until terminal, returns status + artifact id. On success calls `router.refresh()` so the Server Components re-fetch the new artifact rather than duplicating fetch logic client-side.
- `SandboxedSimFrame` — `'use client'`, mounts the `srcdoc` iframe, handles the postMessage handshake, forwards control changes as `sim:set`, receives `sim:readout` / `sim:error`. Must be `dynamic(..., { ssr: false })` or guarded — it touches `window` on mount.
- `ControlPanel` — renders sliders/toggles/dropdowns from `manifest.parameters`.
- `FeedbackPanel` — submits feedback, renders clarification questions, shows the latest `change_summary`.
- `VersionHistory` — lists versions, one-click rollback.

**Caching discipline.** Generated artifacts change under the user's feet, so opt out of Next's default caching on every backend read: `fetch(url, { cache: 'no-store' })` in Server Components, and `export const dynamic = 'force-dynamic'` on the lab/plan/sim routes. A cached plan page after a regeneration is the most likely "why didn't it update?" bug in this stack.

**Design direction:** the simulation is the hero; generous canvas, restrained palette, one accent; generation progress is always visible (job polling drives a clear "Generating…" state) so latency reads as "working," not "frozen."

---

## 11. Tech stack & local infra

| Layer | Choice | Dockerised? |
|---|---|---|
| API | FastAPI (uvicorn), Pydantic v2, `uv` for deps | ✅ |
| ORM | **Tortoise ORM ≥ 1.0** (`[asyncpg,psycopg]`) with its **built-in migrations** — no Alembic, no Aerich | ✅ |
| Async | Celery + RabbitMQ (broker) + Redis (result backend) | ✅ |
| DB | PostgreSQL 17 | ✅ |
| Proxy | nginx — sole entry point on `:80` | ✅ |
| LLM | OpenAI `gpt-5.5` via official Python SDK, Structured Outputs (`OPENAI_API_KEY` required from day one) | — |
| Frontend | Next.js (App Router) + TypeScript + Tailwind + shadcn/ui, **run on the host** | ❌ by design |
| Sandbox | iframe `srcdoc` + `sandbox="allow-scripts"` + CSP in core | — |

### 11.0 Persistence — Tortoise ORM

Tortoise 1.0 ships **native migrations** (Django-style `Migration` classes with an `operations` list), so Alembic and Aerich are both out. Config lives in `pyproject.toml`, pointing at a single `TORTOISE_ORM` dict:

```toml
[tool.tortoise]
tortoise_orm = "src.config.database.TORTOISE_ORM"
```

```python
# src/config/database.py
TORTOISE_ORM = {
    "connections": {"default": build_db_url()},   # postgres://user:pass@host:port/db
    "apps": {
        "models": {
            "models": ["src.course.models", "src.lab.models",
                       "src.plan.models", "src.simulation.models", "src.job.models"],
            "default_connection": "default",
            "migrations": "src.migrations",
        }
    },
}
```

Registered on the FastAPI app via `RegisterTortoise` in a lifespan context manager with `generate_schemas=False` — migrations own the schema, never runtime auto-creation. Tortoise's exception types (`DoesNotExist`, `IntegrityError`, `OperationalError`, `ValidationError`) get app-level handlers in `src/core/exceptions.py` so the API returns clean JSON instead of 500s.

**Migration workflow:** `uv run tortoise makemigrations` → review the generated file in `src/migrations/` → `uv run tortoise migrate`. The API container's `entrypoint.sh` runs `migrate` on boot before uvicorn starts.

> Generated migrations are reviewed and committed, not regenerated on the fly. Running `makemigrations` inside the container entrypoint would let the running image silently invent schema — keep it a developer command.

**Celery ⟷ Tortoise is the one real friction point.** Tortoise is async-only; Celery's prefork worker is sync. Each task must therefore own an event loop and its own ORM lifecycle:

```python
# src/tasks/base.py
def run_async(coro):
    """Celery tasks are sync; Tortoise is async. Bridge with a per-task loop."""
    async def _wrapped():
        await Tortoise.init(config=TORTOISE_ORM)
        try:
            return await coro
        finally:
            await Tortoise.close_connections()
    return asyncio.run(_wrapped())
```

Two rules that follow, both easy to get wrong:
- **Init and close inside every task**, not at worker startup. A prefork child that inherits an event loop or an asyncpg pool across the fork will fail with cryptic "attached to a different loop" errors.
- **The OpenAI SDK call stays synchronous** (`OpenAI`, not `AsyncOpenAI`). It's the only blocking work in the task and there's nothing to overlap it with, so an async client would add ceremony for no gain.

If this bridge proves noisy in practice, the fallback is a plain `asyncpg` connection for the three status/artifact writes the worker does — but start with Tortoise everywhere so models are defined once.

**Why the frontend stays out of Docker.** Next.js dev-server iteration (HMR, fast refresh) is materially worse through a bind-mounted container on macOS, and the POC's whole value is fast UI iteration. It reaches the backend at `http://localhost:80` — the published nginx port — so nothing about the container topology changes when it's dockerised later for deployment.

### 11.1 docker-compose

```yaml
services:
  redis:
    container_name: redis
    image: redis:latest
    ports:
      - "6379:6379"
    restart: always
    networks:
      - main

  rabbitmq:
    container_name: rabbitmq
    image: rabbitmq:3.13-management
    ports:
      - "5672:5672"   # AMQP port
      - "15672:15672" # Management UI port
    environment:
      RABBITMQ_DEFAULT_USER: ${RABBITMQ_USER}
      RABBITMQ_DEFAULT_PASS: ${RABBITMQ_PASSWORD}
      RABBITMQ_DEFAULT_VHOST: ${RABBITMQ_VHOST}
      RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS: "-rabbit consumer_timeout 18000000"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    restart: always
    networks:
      - main

  postgres:
    container_name: postgres
    image: postgres:17.6-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    networks:
      - main

  api:
    container_name: api
    build:
      context: .
      dockerfile: ./backend/Dockerfile
      target: app
    # entrypoint.sh runs `tortoise migrate` then uvicorn
    depends_on:
      - postgres
      - redis
      - rabbitmq
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_PORT: ${POSTGRES_PORT}
      REDIS_HOST: ${REDIS_HOST}
      REDIS_PORT: ${REDIS_PORT}
      REDIS_DB: ${REDIS_DB}
      RABBITMQ_HOST: ${RABBITMQ_HOST}
      RABBITMQ_PORT: ${RABBITMQ_PORT}
      RABBITMQ_USER: ${RABBITMQ_USER}
      RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
      RABBITMQ_VHOST: ${RABBITMQ_VHOST}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_MODEL: ${OPENAI_MODEL}
      OPENAI_MAX_OUTPUT_TOKENS: ${OPENAI_MAX_OUTPUT_TOKENS}
      ALLOWED_HOSTS: ${ALLOWED_HOSTS}
      CORS_ALLOWED_ORIGINS: ${CORS_ALLOWED_ORIGINS}
      DEBUG: ${DEBUG}
      FAKE_AUTH: ${FAKE_AUTH}
      FAKE_USER_SUB: ${FAKE_USER_SUB}
      APP_PORT: ${APP_PORT}
      WORKERS: ${WORKERS}
      LOCAL_DEV: ${LOCAL_DEV}
    restart: always
    networks:
      - main

  nginx:
    container_name: nginx
    build:
      context: .
      dockerfile: ./backend/nginx/Dockerfile
    volumes:
      - ./backend/nginx/nginx.conf:/etc/nginx/conf.d/default.conf:rw
    ports:
      - "80:80"
    restart: always
    depends_on:
      - api
    networks:
      - main

  celery-worker-generation:
    container_name: celery-worker-generation
    build:
      context: .
      dockerfile: ./backend/Dockerfile
      target: celery
    command: uv run --no-sync celery -A src.worker worker -Q generation -l info --pool=prefork --concurrency=4 --prefetch-multiplier=1
    depends_on:
      - api
      - redis
      - rabbitmq
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_HOST: ${POSTGRES_HOST}
      POSTGRES_PORT: ${POSTGRES_PORT}
      REDIS_HOST: ${REDIS_HOST}
      REDIS_PORT: ${REDIS_PORT}
      REDIS_DB: ${REDIS_DB}
      RABBITMQ_HOST: ${RABBITMQ_HOST}
      RABBITMQ_PORT: ${RABBITMQ_PORT}
      RABBITMQ_USER: ${RABBITMQ_USER}
      RABBITMQ_PASSWORD: ${RABBITMQ_PASSWORD}
      RABBITMQ_VHOST: ${RABBITMQ_VHOST}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_MODEL: ${OPENAI_MODEL}
      OPENAI_MAX_OUTPUT_TOKENS: ${OPENAI_MAX_OUTPUT_TOKENS}
      DEBUG: ${DEBUG}
      LOCAL_DEV: ${LOCAL_DEV}
      CELERY_WORKER_MAX_MEMORY_PER_CHILD: ${CELERY_WORKER_MAX_MEMORY_PER_CHILD}
    restart: always
    networks:
      - main

volumes:
  postgres_data:
  rabbitmq_data:
networks:
  main:
```

**Deliberate omissions vs the reference stack:** no MinIO (`core_html` lives in a Postgres `text` column for the POC), no Langfuse, no Flower, no celery-beat (nothing is scheduled — every task is request-triggered), no static/media volumes (FastAPI serves JSON only; Next.js owns all assets on the host). A second queue (`urgent`) isn't warranted while every task is a generation of the same shape.

**`nginx.conf` essentials** — the sim `core_html` payloads are large and generation is slow, so the defaults need raising:
```nginx
server {
    listen 80;
    client_max_body_size 20M;
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
    }
}
```

**`.env` keys** — every variable the compose file interpolates. Two traps, both silent:

- Docker Compose substitutes an **undefined** variable with an empty string rather than failing, so a missing key surfaces as a confusing runtime error, not a startup error.
- Compose does **not** strip inline `#` comments from values. `OPENAI_API_KEY=  # set me` makes the key literally `"# set me"`, which fails deep inside the SDK as an ASCII-encoding error on the header. Keep every comment on its own line. `.env.example` is the canonical copy.

```bash
POSTGRES_DB=simgen
POSTGRES_USER=simgen
# set me
POSTGRES_PASSWORD=
# service name on the compose network
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=simgen
# set me
RABBITMQ_PASSWORD=
RABBITMQ_VHOST=/
# set me — required from day one
OPENAI_API_KEY=
OPENAI_MODEL=gpt-5.5
OPENAI_MAX_OUTPUT_TOKENS=16384
APP_PORT=8000
WORKERS=4
ALLOWED_HOSTS=api,localhost
CORS_ALLOWED_ORIGINS=http://localhost:3000
DEBUG=true
FAKE_AUTH=true
FAKE_USER_SUB=dev-teacher
LOCAL_DEV=true
CELERY_WORKER_MAX_MEMORY_PER_CHILD=512000
```

The `*_HOST` values are compose **service names**, resolved on the `main` network — not `localhost`. `localhost` only appears in the frontend's `.env.local`, which sits outside Docker and reaches the stack through the published nginx port:

```bash
# web/.env.local
BACKEND_URL=http://localhost:80
```

`CORS_ALLOWED_ORIGINS` is near-vestigial under the BFF — the browser only ever talks to Next.js, so FastAPI sees server-to-server requests. It's kept for direct API poking during development.

**Bring-up:** `docker compose up --build` for the backend, then `npm run dev` in `web/` on the host.

### 11.2 Repository layout

Domain-per-package, mirroring the reference backend: each domain owns its `models.py` (Tortoise), `schemas.py` (Pydantic), and `router.py` (FastAPI).

```
simgen/
├── docker-compose.yml
├── .env                        # backend stack config
├── backend/
│   ├── Dockerfile              # multi-stage: builder → base → app | celery
│   ├── entrypoint.sh           # tortoise migrate, then uvicorn
│   ├── pyproject.toml          # uv-managed; [tool.tortoise] lives here
│   ├── nginx/
│   │   ├── Dockerfile
│   │   └── nginx.conf
│   └── src/
│       ├── main.py             # FastAPI app, lifespan, routers, exception handlers
│       ├── worker.py           # Celery app
│       ├── config/
│       │   ├── database.py     # TORTOISE_ORM, register_orm
│       │   └── settings.py     # pydantic-settings
│       ├── core/
│       │   ├── auth.py         # stub dev user
│       │   └── exceptions.py   # Tortoise → JSON handlers
│       ├── migrations/         # generated by `tortoise makemigrations`, committed
│       ├── course/             # models · schemas · router
│       ├── lab/                # models · schemas · router
│       ├── plan/               # models · schemas · router
│       ├── simulation/         # models · schemas · router (+ feedback)
│       ├── job/                # generation_jobs: models · schemas · router
│       ├── tasks/              # base.py (async bridge) + the three generation tasks
│       └── llm/                # client.py · prompts.py · schemas.py (JSON Schemas)
└── web/                        # Next.js — host-run, not in compose
    ├── .env.local              # BACKEND_URL=http://localhost:80
    └── app/
        ├── page.tsx                          # course list
        ├── courses/[id]/page.tsx             # a course's labs
        ├── courses/[id]/labs/new/page.tsx    # intake
        ├── labs/[id]/plan/page.tsx           # plan review
        ├── labs/[id]/sim/page.tsx            # simulation workspace
        └── api/[...path]/route.ts            # BFF passthrough
```

The Dockerfile is multi-stage — a `builder` stage running `uv sync --frozen`, a `base` stage carrying the prebuilt venv, then `app` (entrypoint: migrate + uvicorn) and `celery` (entrypoint: the worker) on top. Same image content, different entrypoint.

```bash
# backend/entrypoint.sh
#!/bin/bash
set -e
echo "Running database migrations..."
uv run --no-sync tortoise migrate

echo "Starting FastAPI application..."
exec uv run --no-sync uvicorn src.main:app \
  --host 0.0.0.0 --port ${APP_PORT:-8000} \
  --workers ${WORKERS:-4} --loop uvloop --http httptools
```

---

## 12. Build milestones

| # | Milestone | Exit criteria |
|---|---|---|
| 0 | Scaffold + **real-LLM + sandbox spike** | `docker compose up` brings the backend online behind nginx with Tortoise migrations applied on boot; a real OpenAI (`gpt-5.5`) call, dispatched via Celery/RabbitMQ, returns a `{manifest, core_html}` that the host-run Next.js app renders as a working sandboxed sim — via the BFF, end to end |
| 1 | Courses, labs + plan generation job | Teacher creates a course, then a lab from a prose description; a background job produces a versioned plan with inferred subject/topic; malformed JSON fails cleanly, never crashes |
| 2 | Blueprint review & decision | Edit purpose, experience, controls, visuals, readouts, rules, and observations; Accept unlocks generation; Reject creates a new version |
| 3 | Simulation generation (shell/core) | The accepted blueprint's manifest is projected (§6.1); call #2 yields `core_html`; shell renders approved controls and the core honors approved visuals/rules |
| 4 | Refinement loop + versioning | Targeted feedback edit produces a new version; rollback works; ambiguous feedback returns a clarification |

**→ POC ends at milestone 4.** No publish, no deploy, no student-facing features.

---

## 13. Explicitly parked (so it isn't lost)

Reproducibility / "same blueprint → same sim" via generation caching was discussed and **deliberately deferred** for the demo. When it matters (v1), treat the accepted blueprint version as a cache key and reuse the stored artifact rather than trying to make the model deterministic. Not built now.
