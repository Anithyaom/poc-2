# simgen POC — Engineering Handoff

| | |
|---|---|
| **Project** | simgen — AI-supported virtual science lab (authoring pipeline POC) |
| **Handed off by** | _[your name]_ |
| **Handed off to** | _[owner / team]_ |
| **Date** | _[fill in]_ |
| **Status** | **Milestones 0–3 complete and browser-verified.** Milestone 4 (the refinement loop, LLM call #3) is the remaining pipeline stage. |
| **Source of truth** | `SIMGEN_POC_SPEC.md` |
| **Last revised** | 2026-08-01 — milestone 3 complete, all seven slices: the coherence gate, the `simulations` table, LLM call #2, the validation gate with host-injected design tokens, the three-region workspace, layout and ambition rules in the core contract, and the milestone-0 spike deleted |

---

## 1. TL;DR

simgen lets a creator use AI to draft a teacher-readable simulation blueprint, approve it, generate a **working interactive simulation** from it, and then refine that simulation by leaving natural-language feedback — all from the frontend. The blueprint is not a lesson plan: every section directs what the simulation teaches, shows, controls, calculates, or does. The two generative steps run as **background jobs** (Celery + RabbitMQ); the frontend enqueues work and polls for the result. Simulations use a **shell/core split**: AI writes the sandboxed core while React renders the controls.

---

## 2. What you're inheriting (state, context & history)

### 2.1 What is built right now

Milestones 0, 1 and 2 are complete and were exercised end to end against `gpt-5.5` — not a mock. Section numbering below is unchanged from earlier revisions, so `§4` is still the decision log.

| Area | State |
|---|---|
| Compose stack | `nginx`, `api`, `celery-worker-generation`, `postgres`, `rabbitmq`, `redis` all build and run; `entrypoint.sh` applies migrations on boot |
| Schema | `courses`, `labs`, `plan_versions` (incl. `revision_feedback`), `generation_jobs`, `simulations`. Six migrations, committed — `0004` is data-only (the `time_stepped` backfill), `0005` creates `simulations` plus a hand-written partial unique index, `0006` drops `spike_simulations` |
| LLM call #1 | Built and schema-validated, in two modes: **draft** from prose, and **revise** an existing blueprint from teacher feedback. Same system prompt and schema for both — a revision is an ordinary generation with a different user prompt. Produces one simulation blueprint: purpose, expected observations, experience, controls, readouts, visuals, behavior rules |
| LLM call #2 | Built. The accepted blueprint projects its manifest, `SIM_CORE_CONTRACT` + `sim_core_user_prompt` request `core_html` alone, and `validate_core` gates the result before anything is persisted. Verified live: two real simulations generated, both passing the gate single-shot |
| LLM call #3 | **Not built** — milestone 4 |
| Frontend | Course list, course detail, prose intake (grades 6–12, Undergraduate, Graduate), two-tier blueprint review, and the simulation workspace at `/labs/[id]/sim` — three regions: approved blueprint, sandboxed core, control panel. Sections render as a document and become focused forms only while editing; visuals and behavior rules sit in one collapsed block. All server reads use `cache: 'no-store'` + `force-dynamic` |
| Verified | course → lab → plan → reject → regenerate → edit → accept → **simulation on screen**, with append-only versioning holding at every step |

**The milestone-0 spike is deleted.** It went prose → simulation in one call, deliberately skipping the plan stage, to prove the risky plumbing (real LLM → Celery → sandboxed iframe) before any pipeline sat on top. `src/spike/`, `src/tasks/spike.py`, `web/app/spike/`, `SIMULATION_SCHEMA`, `SimulationOutput` and `SPIKE_SYSTEM_PROMPT` are gone; migration `0006` drops `spike_simulations`. Two `spike_simulation` rows remain in `generation_jobs` and read back fine — `job_type` is a plain `CharField`, so history survives the enum member's removal. Its task shape — job row → running → validate → persist → succeeded, one retry, raw response kept on failure — is the template every real generation task follows, including milestone 4's.

**`backend/scripts/try_plan.py`** runs LLM call #1 against the real model with no database, no Celery, and no browser, and prints the plan as a teacher reads it plus the manifest that would ship. It is the fastest loop for prompt iteration; milestone 1's real task supersedes it, but it stays useful.

### 2.2 Session stopping point

**This session closed milestone 3 end to end.** Details are in §2.2.1; the state to resume from:

- **The pipeline is whole.** Prose → blueprint → review → accept → simulation on screen, all through the BFF, all against live `gpt-5.5`. Three real simulations exist in the dev database.
- **Browser-verified by the owner**, who judged the generated simulations *"pretty good for the first use"* and *"works well"* — the first time the shell/core split has been assessed on the thing it exists to produce rather than on the plumbing.
- **`backend/tests/` exists** — 12 tests over `check_coherence`. Small deliberately: pure functions whose regressions are silent. `validate_core` deserves the same treatment and has none yet.
- **The stack was brought down at the end of the session.** `docker compose up --build` and `cd web && npm run dev` to resume. Migration `0006` is applied to the dev database; a rebuild from scratch reapplies all six.
- **Nothing is deployed and nothing is merged to `main`.** The work is on `milestone-3-simulation-generation`, which also carries the unmerged transport-bar commits.

**Next: milestone 4** — the full brief, including the three genuinely new problems and the two decisions it should force, is at the end of §6. Read §5 items 8–11 before touching the workspace UI; all four are deliberate deferrals with a stated reason, and item 8 is now decidable.

**The previous session** reviewed a real generated blueprint (binary search) as a teacher would read it and restructured the review screen around what that exposed. Reasoning is in §4.2.

- **The review screen is two-tier.** Order on screen is 01 what it teaches · 02 what students should notice · 03 how it works · 04 what students can change · 05 values displayed, then one collapsed block — *"What the simulation will show and do"* — holding `visual_elements` and `behavior_rules`. Default view is ~1.5 screens instead of seven. Every field is still present, still editable, and still sent to call #2.
- **`misconception` displays as "Where students go wrong."** Field name unchanged everywhere; display label only.
- **`PLAN_SCHEMA` property order changed** so `expected_observations` is generated after controls/readouts and before visuals/rules. `Plan`'s field order mirrors it, and a check asserts the two cannot drift. No migration — `plan_json` is a dict.
- **Audience now runs to `Undergraduate` and `Graduate`**, and `PLAN_SYSTEM_PROMPT` carries an explicit depth ladder. Verified live: identical prose at Graduate produced an invariant-based objective with rotated-sorted and single-inversion cases where Grade 9 produced sorted vs. scrambled.
- Earlier sessions' facts that still hold: the retired classroom lesson-plan rows remain in version history and the review screen asks for a fresh blueprint rather than converting them; manual edits still use `accept_with_modifications` while an unchanged accept uses `accept`.
- Frontend lint, TypeScript, and the production build pass. Backend Ruff, strict Structured Outputs checks, schema/model order check, and plan-to-manifest projection checks pass. Two live `gpt-5.5` blueprints generated and validated.
- **Request changes ships**, closing milestone 2. `POST /api/plans/{id}/revisions` + the `revise_plan` task revise the current blueprint from the teacher's own words, carrying unsaved section edits along. Reasoning in §4.3.
- Verified through the running stack, not only statically: one revision-with-edits produced v1 drafted → v2 human-authored → v3 revised-with-feedback-stored, with the lab still `plan_review` and `active_plan_id` untouched. 409 on a non-pending source, 422 on empty feedback. `revise_plan` registers under both import orders (§7.1).
- Browser-verified by the owner: the two-tier review, the three-action bar, and a revision with a manual edit riding along.
- **Known wart:** the feedback textarea clears on submit, so a *failed* revision loses what the teacher typed.
- **Not verified:** no automated tests exist for any of this. `PlanEditor` and `PlanWorkspace` have none, and there is no test for the revision route or task — every check so far has been manual or one-shot. *(Partly addressed since: `backend/tests/` now covers `check_coherence`. The frontend and the routes still have nothing.)*

### 2.2.1 Milestone 3, slices 1–5

The plan is `docs/plan/milestone-3-simulation-generation.html`. All seven slices shipped; 6 and 7 were held back deliberately until real cores existed to judge them against.

- **The coherence gate ships** (§5 item 7). Runs inside the plan task, retries once with the contradictions fed back, then fails the job with a teacher-readable reason.
- **`simulations` exists**, append-only, with a **hand-written partial unique index** (`uniq_simulations_current`) that Tortoise cannot express: `unique_together` on `(lab_id, component_ref)` would forbid a second *historical* row too. Without the partial index the "exactly one current version" rule lives only in task code, and a crash between "insert v2" and "demote v1" leaves two current rows.
- **Call #2 is a single-shot generation behind a deterministic gate.** `validate_core` checks the document is complete, the CSP is present and blocks the network, every handshake message is handled, all four transport messages are handled when `time_stepped`, no control UI is drawn, and every approved id is used. A failure retries once *with the specific problems fed back* — a grounded verdict, never self-critique. A second failure is a failed job.
- **Design tokens are injected, not requested.** `inject_tokens` writes a host-authored `<style data-simgen-tokens>` block into the core's `<head>` after the gate passes. The prompt tells the model to use the variables; the injection guarantees they exist. Both real cores came back with **zero hex literals** outside that block. The marker is what makes a stored core restyleable later without regenerating it — keep it.
- **The workspace is three regions**, all host-rendered except the middle: approved blueprint, sandboxed core, control panel. `BlueprintContext` shows only objective / what to notice / where students go wrong — no model wrote any of it at generation time.
- **Accepting a blueprint now enqueues the simulation** and lands the teacher on it. Already-accepted labs get a "Build the simulation" button instead.

**Slices 6 and 7 followed, once real cores existed to judge:**

- **Layout rules, written against an observed defect.** The first pendulum core overlaid a readout on a panel title and clipped a label at the right edge. The tokens pinned palette and type; composition was unconstrained. `_CORE_RUNTIME_CONTRACT` now requires a reserved title band, labels kept inside their panel, anchored and offset annotations, `ctx.measureText` before placement, a minimum panel width before stacking, and positions recomputed on resize.
- **An ambition section**: history over instants, linked views, annotated moments, state legible without motion, readouts drawn beside their objects — all bounded by the blueprint's own visual elements, with decoration explicitly excluded.
- **`scripts/show_prompts.py`** prints exactly what each call receives, with each message's source and size, and can run call #2 against a real blueprint without touching the database. That is the loop for tuning the contract — a real call is ~135s, so the alternative is a two-minute round trip through the stack per edit.
- **The spike is deleted** (see §2.1), and with it the last two-field `{manifest, core_html}` schema.

**Measured, not estimated:** all three generations passed the gate first try, at 99s, 124s and 135s. Accept-to-simulation is therefore about two minutes of spinner (§5 item 2 is where that hurts).

**One number worth watching:** the regenerated pendulum core came back at 14.9k chars against the original's 23.3k, despite the ambition section. Either the layout rules crowded out the scene, or the second attempt was simply tighter code. The owner judged the result good in the browser, so nothing was changed — but if later cores also come back thinner, move the ambition section *above* the layout section, or shorten the layout rules. Prompt sections compete for attention.

**The 409 guard is live and firing.** `POST /api/labs/{id}/simulations:generate` re-validates the accepted `plan_json` as a `Plan`, not merely that it exists. The Osmosis lab (`d5351f47`) is `plan_accepted` holding a retired lesson-plan row and correctly returns *"This blueprint predates the current format."* Without the guard that is a 500, or worse a failed job the teacher has to interpret.

### 2.3 Two spec details, now settled by execution

Both were written from a reference repo and reasoning rather than from running code. Both are confirmed:

- **Tortoise CLI** — `tortoise-orm 1.1.7` ships `init` / `makemigrations` / `migrate` and reads `[tool.tortoise] tortoise_orm` from the `pyproject.toml` in its cwd. `tortoise init` must be run once to create the migrations package. Spec §11.0 was correct.
- **Model id** — `gpt-5.5`, confirmed against the live models endpoint (`owned_by=system`). `verify_model()` runs at API startup, so a typo fails loudly at boot rather than inside a worker.

### 2.4 History

- **The vision is bigger than the POC.** The full product is a hybrid cloud + on-device AI lab for the Global South (student tutoring, hints, quizzes, progress tracking, offline models). **None of that is in the POC.** The POC is only the *creator-side authoring pipeline*, up to and including the refinement loop. Don't let vision features leak in.
- **There was a prior plan and codebase — we did not build on them.** An inherited `AI_virtual_lab.md` plan existed with a 13-week production framing. Two problems drove a fresh start:
  1. It marked its plan-generation phase "done" while **never once calling a real LLM** — everything was tested against a mock because no API key was present. Checked boxes were softer than they looked.
  2. It carried production weight (Terraform, managed infra, normalized spec tables, a generic renderer) inappropriate for a POC.
- **So this is a clean rebuild, scoped hard.** The scope, stack, and simulation architecture were all reset. The reasoning for each reset is in the decision log below — read it before changing anything, so good decisions don't get quietly undone.

**Related documents**
- `SIMGEN_POC_SPEC.md` — the detailed technical spec (architecture, data model, API, LLM contracts, shell/core protocol). **This is the build reference.**
- `docs/plan/blueprint-review-restructure.html` — the approved implementation plan for the review restructure, including mockups and the before/after section order.
- `docs/plan/blueprint-request-changes.html` — the approved implementation plan for the revision flow, including the version-sequence mockup.
- `SIMGEN_POC_PLAN.md` — the earlier phased POC plan; useful as a lighter narrative of the same scope.
- `AI_virtual_lab.md` — the inherited plan. Historical context only; superseded.

---

## 3. Scope — the line

**In:** courses & labs navigation → prose intake → plan generation (LLM #1) → accept/reject → simulation generation (LLM #2) → sandboxed interactive runtime → feedback-driven scoped edits (LLM #3) → version history + rollback.

**Out:** publishing/deployment, real auth/multi-user, all student-facing features, local/offline models, production infra, generation caching/determinism, normalized spec tables + generic renderer.

Full detail in `SIMGEN_POC_SPEC.md` §1. When a request feels like it's past "refine the finished simulation," it's v1, not POC.

---

## 4. Decision log

The decisions already made, and *why* — so they don't get relitigated from scratch.

| Decision | Rationale | Status |
|---|---|---|
| **Fresh start**, not build-on-inherited | Inherited code's "done" work was unverified (no real LLM call); production weight unfit for a POC | Locked |
| **AI generates runnable sim code**, not a structured spec + generic renderer | Produces genuinely good sims fast; avoids building a rendering engine; makes feedback = "patch the code" | Locked |
| **Shell/core split** — AI writes only the sandboxed core; React renders the controls | Consistent UI across every sim without an interpreter; shrinks the generation surface; safe sandboxing | Locked |
| **Run controls are a fixed shell transport bar behind one boolean** — the plan declares `time_stepped`, and when true the shell renders the same Step/Run/Pause/Reset bar for every simulation | Step/Run/Pause/Reset are always the same four actions, so a per-simulation `action` parameter list is over-general: it would let the model invent its own transport UI and grow the shared parameter factory a type with no min/max/default. A single flag keeps "the LLM never generates control UI" literally true and gives every animated sim identical time control. `sim:play`/`sim:pause`/`sim:reset` already exist in the protocol; only `sim:step` is new. Rejected alternatives: a generic `action` type (expressive but inconsistent per sim), and letting the core draw its own buttons (no schema work, but the split stops holding) | Locked |
| **The plan owns the manifest** — LLM #1 declares the sim's controls in manifest shape; they are projected into `manifest_json` by deterministic code, and LLM #2 generates `core_html` alone | Makes the plan review screen a real approval gate: what the teacher signed off is exactly what ships. Drift between plan and manifest becomes structurally impossible rather than something to trust call #2 about, and it shrinks call #2's output to one field — cheaper, faster, fewer validation failures. Cost: the plan-stage model fixes ranges before anything reasons about rendering, mitigated by the prompt forcing explicit physics reasoning and by letting the teacher edit ranges at review. Call #3 may still change the manifest — the plan owns the *initial* one | Locked (spec §6.1) |
| **FastAPI + Celery + RabbitMQ** async generation | Plan/sim LLM calls take real seconds; must not block a request. FastAPI stays thin, workers do the work | Locked |
| **OpenAI `gpt-5.5`**, not Anthropic Claude | Provider switch made at resume. Strongest code generation for `core_html`; Structured Outputs (`strict: true`) constrain the model to our schema rather than merely asking for JSON | Locked |
| **Next.js (App Router)**, not React + Vite | Server Components remove client-side fetch waterfalls on reads; route handlers give us a BFF without a second service | Locked |
| **Next.js is a BFF proxy** — browser never calls FastAPI directly | No CORS surface, no backend URL in client bundles, and a natural seam for real auth later | Locked |
| **Backend dockerised, frontend is not** | Next.js HMR is materially worse through a bind-mounted container on macOS, and fast UI iteration is the POC's point. Frontend reaches the stack at the published nginx port, so containerising it later changes nothing | Locked for POC |
| **nginx as the sole entry point** (`:80`) | FastAPI stays off published ports; one place for TLS/auth/timeouts. Generation is slow, so `proxy_read_timeout` is raised to 300s | Locked |
| **Tortoise ORM ≥ 1.0 with its built-in migrations** — no Alembic, no Aerich | Tortoise 1.0 ships native Django-style migrations (`tortoise makemigrations` / `tortoise migrate`); a second migration tool earns nothing. Pattern proven in `Construct-Lab/Desi-Connections` | Locked |
| **Domain-per-package backend layout** (`src/course/`, `src/lab/`, …) each owning `models.py` · `schemas.py` · `router.py` | Same shape as the reference backend, so the two projects read alike | Locked |
| **`courses` → `labs`** (`modules` renamed to `labs`) | Matches how teachers actually navigate: course list → a course → create a lab. Terminology now matches the conversation | Locked |
| **Intake is free-text English prose + a grade select** | A teacher describing a lab in their own words is the natural entry; the model infers subject/topic and echoes them into the plan for confirmation, so a bad inference costs one rejection, not a form redesign | Locked |
| **Frontend polls a `generation_jobs` table** for status | UI never depends on Celery internals; simple and robust | Locked (SSE is an optional upgrade) |
| **Real OpenAI call is milestone 0**, not deferred | Direct fix for the inherited plan's core failure; retires the biggest risk first | Locked |
| **Auth is a stub** (fixed dev user) | Out of POC scope; endpoints written so real auth drops in later | Locked for POC |
| **Reproducibility / generation caching parked** | Deliberately deferred for the demo; use the accepted blueprint version as a future cache key | Parked, documented |

### 4.1 Decisions made during the build (milestones 0–2)

| Decision | Rationale | Status |
|---|---|---|
| **The plan is only a simulation blueprint** — interpretation, objective, experience, controls, visuals, readouts, behavior rules, and expected observations | Its sole purpose is to direct simulation generation in a structure teachers can review. Lesson sequencing, readings, timings, activities, and teacher notes were removed because they do not constrain the generated artifact | Locked |
| **One blueprint describes one simulation** — no `components[]` / `simulations[]` indirection | The POC generates one simulation per lab. A singular shape is easier for teachers to edit and gives call #2 direct visual and behavioral requirements | Locked |
| **`PLAN_SCHEMA` and `MANIFEST_SCHEMA` share one parameter-object factory** (`_parameter_schema`) | The plan's parameters are copied verbatim into the manifest. Defining the two shapes separately is precisely how they would drift | Locked |
| **`edits` on a plan decision is the whole edited plan, not a patch** | Simpler and safer for a POC: the edited document is re-validated by the same `Plan` model the LLM output goes through, so a teacher cannot save a plan the generator could not have produced — including the binding parameter ranges | Locked for POC |
| **An edited acceptance writes a new version** and marks the generated one `superseded` | Versioning is append-only, and the *accepted* row is what the manifest is projected from — so it has to be the edited one, not the drafted one | Locked |
| **All non-simulation lesson material stays out** | The blueprint is not a lesson planner. Readings, discussions, assessments, worksheets, timings, and teacher notes do not contribute to simulation generation | Locked |
| **npm, not pnpm** | `registry.npmjs.org`'s Cloudflare IPs are unreachable from the current network (DNS resolves, TCP times out). `.npmrc` points at the `registry.yarnpkg.com` mirror, which is a full mirror of the same registry. Delete `.npmrc` once direct access works | Environmental, revisit |
| **Blueprint review is read-first, edit-second** | Sections render as a document by default. One section becomes a focused form when its Edit button is pressed; controls remain structured cards. JSON, internal IDs, and manifest terminology stay hidden | Locked for POC |
| **One Accept button that picks its own verb** | It reads "Accept blueprint" or "Accept with my changes" depending on whether anything was edited, and sends `accept` or `accept_with_modifications` accordingly | Locked for POC |
| **Compose `depends_on` uses healthchecks** | `entrypoint.sh` runs `tortoise migrate` immediately, so `api` must wait for Postgres to be *accepting connections*, not merely started. Spec §11.1's plain `depends_on` crash-loops on a cold volume | Locked |

### 4.2 Decisions made restructuring the blueprint review

The full binary-search blueprint ran to roughly seven screens, and about 60% of that was `visual_elements` + `behavior_rules` — sections a teacher cannot meaningfully approve or reject as prose. The fix was ordering and disclosure, not deletion.

| Decision | Rationale | Status |
|---|---|---|
| **Blueprint review is two-tier** — the teacher's decision surface is visible; `visual_elements` and `behavior_rules` sit in one collapsed block titled *"What the simulation will show and do"* | Rules like "binary search keeps a low end and a high end for the current possible range" are a spec for the code, not a judgement a teacher can make: a teacher who knows the topic doesn't need them, and one who doesn't can't check them. But **deleting them is not an option** — call #2 needs them or it invents its own visual design, and the teacher's approval would no longer cover what ships. Both sections stay in the blueprint, stay editable, and stay in call #2's prompt; they just stop competing for attention with the decision. Default view is ~1.5 screens instead of seven | Locked for POC |
| **No generator vocabulary in teacher-facing copy** | The collapsed block is titled for what it *is to a teacher* ("the visuals and rules the simulation is built from"), never "what the generator will be told". Teachers know a simulation gets built from the blueprint; they should not have to hold a mental model of a code generator to review it | Locked |
| **A collapsed block may never hide a live form** | Editing `visuals`/`behavior` force-opens the block, and closing the block cancels an edit inside it. Otherwise a teacher edits a section, collapses it, presses Accept, and ships changes they can no longer see | Locked |
| **`misconception` displays as "Where students go wrong"** — field name unchanged in `PLAN_SCHEMA`, the `Plan` model, and `lib/types.ts` | "Misconception" is standard in physics lab prep and alien elsewhere; it also reads as a judgement of the student. The label was narrower than the content the model actually produces — *"students think binary search is just a faster way to search any list"* is an incomplete idea, not a false belief. The prompt was reworded to accept incomplete or over-general beliefs, and told not to use the word itself. Renaming the field would cost a migration and buy nothing | Locked |
| **Review order is not authoring order** | On screen, `expected_observations` moves to section 02 so the teacher reads the objective and its acceptance test together — it was last, after the two longest sections, and it is the most useful section on the page. In `PLAN_SCHEMA` it moves only *behind* controls/readouts and *ahead* of visuals/rules: strict Structured Outputs generates in property order, so observations can then reference only controls already committed to, while visuals and rules get designed to make those observations visible. Verified live — observations now name their setup ("With List order set to Single inversion and Target value set to 13…") | Locked |
| **Audience extends to `Undergraduate` and `Graduate`**, and the prompt calibrates depth to the audience string | `audience` is already free text in a `CharField(64)`, so this is a select-list change with no migration. The prompt gains an explicit depth ladder: school grades get one relationship at a time; graduate assumes the standard result is known and must probe a limiting case, failure mode, or competing regime. Confirmed against `gpt-5.5` — the same prose at Graduate produced an invariant-based objective with rotated-sorted and single-inversion cases, where Grade 9 produced sorted vs. scrambled. Depth changes the concept and the ranges, never the number of controls | Locked |
| **Behaviour rules must agree with the declared controls** | Added to the prompt after the binary-search blueprint shipped `Number of items` as `0–100 step 1 default 50` while its own rules demanded powers of two (8–128). A rule enumerating discrete values means the control is a `dropdown`, not a `slider`. Prompt pressure alone was never a guarantee, so `check_coherence` now enforces it deterministically (§5 item 7) | Locked; validated |

---

### 4.3 Decisions made building blueprint request-changes

| Decision | Rationale | Status |
|---|---|---|
| **A revision is an ordinary plan generation with a different user prompt** — same `PLAN_SYSTEM_PROMPT`, same `PLAN_SCHEMA`, same `Plan` validation, same one-retry rule | Every rule already in force (audience depth, authoring order, control coherence) applies to revisions for free, and there is no second contract to keep in sync. It is also why the whole feature is one day of work rather than a week | Locked |
| **The preservation instruction permits consequential edits and forbids cosmetic ones** | "Preserve everything not mentioned" alone is wrong in both directions: it invites the model to re-word prose the teacher already approved, *and* it would leave rules referencing a control that just changed — a self-contradicting blueprint, the exact defect class in §7.1. The prompt therefore requires dependent rules and observations to move with a changed control, and forbids re-wording, re-ordering, re-titling or re-explaining anything untouched. Verified: a control-addition revision returned `title`, `concept_summary`, `learning_objective`, `misconception` and all readouts byte-identical, while re-parameterising 6 rules that had hardcoded a fixed list length | Locked |
| **Unsaved section edits are sent with the feedback, not blocked** | The first design disabled Request changes while edits were pending, telling the teacher to "accept them first" — but accepting *ends* the review, so the only real option was discarding their work. Editing a range by hand and asking for a graph are natural to want together | Locked |
| **Those edits are persisted as their own pending version before the model runs** | The revision route writes the edited plan as a new `PENDING` row (superseding the source) and revises from *that*. Nothing is lost in any branch: if the model call fails the edits already exist as a reviewable row, which is strictly better than the status quo where unsaved edits live only in React state. Cost is one extra row per revision-with-edits — acceptable, and consistent with append-only versioning rather than a special case bolted onto it | Locked |
| **`PENDING`, not `ACCEPTED`, on that intermediate row** | `accept_with_modifications` performs the identical write with `ACCEPTED` and ends the review. Getting this wrong would mean asking for changes silently approves the blueprint | Locked |
| **Write the revision first, supersede the source second** | If the model call fails, the source row is still `PENDING` and the teacher still has a reviewable blueprint. Never retire a row before its replacement exists | Locked |
| **`revision_feedback` is stored on the produced row** (migration `0003`, one nullable text column) | Without it, history shows *that* v4 replaced v3 but never *why* — which is the question append-only versioning exists to answer, and the first thing you want when a revision goes wrong. Cheaper now than once there are rows worth explaining | Locked |
| **Reject is demoted but still plainly a button** | Request changes is now the normal response to "this isn't right"; reject-and-redraft discards the blueprint and returns to the original prose, which stays correct only for a genuinely misread request. First attempt styled it as bare muted text — that read as *disabled*, not secondary. A destructive action must be subordinate, not camouflaged: same border weight and padding as its peers, muted colour and right-alignment carrying the demotion | Locked |

---

## 5. Open decisions and queued follow-ups

Items 1–5 and 8–11 still need an owner's call. Items 6 and 7 are done:

1. **Redis as Celery result backend — keep or cut?** It's the clean default but one extra container. Cutting it means leaning entirely on the `generation_jobs` table for status. Recommendation: keep for now.
2. **Polling vs WebSocket/SSE for job status.** POC ships with polling at 1.5 s. Plan generation takes **60–120 s** in practice, so the progress state is on screen long enough to matter. Decide whether push is worth adding for demo polish.
3. **Auth stub scope.** Confirm a single fixed dev user is acceptable for every demo scenario, or whether a trivial login is needed. `courses.owner_sub` is the column real auth will key off.
4. **Token ceilings & budget.** Model is settled (`gpt-5.5`). Plan generation fits comfortably; `OPENAI_MAX_OUTPUT_TOKENS` is 16384 and untested against a large `core_html`, which is milestone 3's first risk.
5. **Artifact storage.** `core_html` sits in a Postgres `text` column for the POC. If blobs grow or versions pile up, MinIO is the drop-in (it's in the reference stack already) — not needed now.
6. ~~**Blueprint request-changes workflow.**~~ **Done** — shipped as `POST /api/plans/{id}/revisions` + `revise_plan`. See §4.3. One wart left open: the feedback textarea is cleared on submit, so a failed revision loses what the teacher typed. Cheap to fix (hold the text until the job succeeds); it is a bad moment in a demo.
7. ~~**Plan-stage coherence review.**~~ **Done** — shipped as `src/llm/coherence.py`, wired into both the generation and revision paths of `src/tasks/plan.py`. A blueprint whose own rules contradict its own controls now retries once *with the specific contradictions fed back*, then fails the job with a teacher-readable reason. Two things worth knowing:

   - **It is tuned for silence, and that tuning is the whole design.** The check speaks only when the control is named by the rule *and* the numbers are provably unusable. Two guards do most of that work: the out-of-range check only counts numbers written in the control's own unit (so "at 20 m/s it travels 40 m" does not read 40 as an out-of-range speed), and **any negation in the sentence buys silence**. The second guard came from a real false positive — `What Sets a Pendulum's Period?` says *"the simulation should not allow a starting angle of 0°"* next to a 2–80° slider, which is the rule **agreeing** with the bound, not contradicting it. Both cases are regression tests.
   - **Verified against all 14 stored blueprints: zero problems reported.** Ten parse as a `Plan`; the check is silent on every one. That is the intended result — none of them contain the contradiction it hunts (the binary-search plan that motivated it was superseded), and a check that fires on real, accepted work is a check that blocks teachers. The synthetic contradictions in `backend/tests/test_coherence.py` are what prove it still speaks.

   Open sub-question, deliberately left alone: **the check does not run on the teacher's own edits.** `accept_with_modifications` writes a hand-edited control straight through, so a human can still introduce exactly the contradiction this catches. Blocking a teacher from their own edit is a much harsher act than failing a model's output, and there is no warn-without-blocking channel on the review screen yet. Revisit when there is one.

8. **Should the transport bar simply be on for every simulation?** The owner's stated preference, on first seeing the review screen: *"the transport bar should be there for all simulations."* Worth taking seriously — it would delete `time_stepped` from the plan schema, the prompt, the review screen and the manifest, and remove a whole class of "the model judged it wrong" failure. Every simulation would get identical chrome, which is the shell's entire argument. What has to be answered first is what the four buttons *do* in a simulation that does not advance: a pH readout has no step to take, so Step and Run either do nothing (a dead control, which teaches students the UI lies) or the core is required to invent a notion of time it does not have. There is a middle option — always render the bar, but disable it when the manifest says the simulation is static — which keeps the layout identical without pretending. **No longer blocked:** this was deferred until real generated simulations existed to judge against, and three now do (two time-stepped, one not). Decide it at the start of milestone 4 — see §6. Deciding it also unblocks item 9.

9. **The `time_stepped` checkbox is poor UX.** Confirmed in the browser by the owner. It is currently a bare checkbox at the bottom of section 03, styled unlike every other control on a screen that is otherwise carefully designed, and its read-only form ("Playback — the simulation updates instantly") is wordier than the thing it describes. Deliberately deferred, not forgotten. Note that item 8 may delete this control outright, so **do not restyle it before item 8 is decided** — that would be work thrown away.

10. **Two version counters are on screen and neither says which it is.** The workspace header reads `V1` (the *simulation* version) while the blueprint screen reads "Simulation blueprint v2 accepted" (the *plan* version). They are independent counters — regenerating a simulation from the same blueprint gives simulation v2 from blueprint v2 — and the owner read the pair as one sequence on first sight. Cheapest fix: `Simulation v1 · from blueprint v2` in the header, which costs nothing and removes the ambiguity outright. Worth doing alongside the version rail in milestone 4 rather than alone, since that rail makes the distinction visible anyway.

11. **The generated region's layout has no constraints yet, and it shows.** In the first pendulum core, `measured period: 2.46 s` overlapped the "Angle–time graph" panel title and `small-angle prediction:` was clipped by the right edge. The palette and type scale are pinned by the injected tokens (§7.6); the *composition* — how many panels, where overlay text sits, whether anything reserves space for a title — is still entirely the model's call. This is slice 6 territory, not a bug to patch in one core: the fix is a layout rule in `_CORE_RUNTIME_CONTRACT` (reserve a title band, never overlay text on a plot's header row, never let a label run past the plot area), which then applies to every simulation. Judge it against a handful of cores before writing the rule, or it will be tuned to one.

---

## 6. Getting started (day 1)

**Prerequisites**
- Docker + docker compose (backend stack).
- Node + npm (the Next.js app runs on the host, **not** in Docker).
- **`OPENAI_API_KEY` set in `.env`.** This is non-negotiable — milestone 0 is meaningless without a live key, and its absence is exactly what hollowed out the inherited plan.

**Bring-up:**

```bash
cp .env.example .env          # then set POSTGRES_PASSWORD, RABBITMQ_PASSWORD, OPENAI_API_KEY
docker compose up --build     # backend stack
cd web && npm run dev         # frontend on the host → http://localhost:3000
```

The frontend talks to `BACKEND_URL=http://localhost:80` (nginx) from its route handlers — server-side only, never a `NEXT_PUBLIC_` var.

**Migrations** run from `backend/`. The compose `*_HOST` values are service names, so host-run commands need an override:

```bash
POSTGRES_HOST=localhost uv run tortoise makemigrations   # review + commit the generated file
POSTGRES_HOST=localhost uv run tortoise migrate          # also run by entrypoint.sh on boot
```

**Tests** run from `backend/`, need nothing running, and finish in under a second:

```bash
uv run pytest
```

The suite covers pure functions only — `check_coherence` today, `validate_core` when it lands. Those are the two places a silent regression is most expensive and the two that are cheapest to pin down. Everything else is still exercised by running the stack.

**Iterating on the plan prompt** — no stack required:

```bash
cd backend
PYTHONPATH=. uv run python scripts/try_plan.py "your prose" --subject Chemistry --audience "Grade 11"
```

**Build order** (detail in `SIMGEN_POC_SPEC.md` §12):

| # | Milestone | Done when | State |
|---|---|---|---|
| 0 | Scaffold + real-LLM + sandbox spike | Real OpenAI call via Celery renders a sandboxed sim end to end, through the BFF | **Done** |
| 1 | Courses, labs + plan generation job | Course → lab from a prose description; background job yields a versioned plan with inferred subject/topic; malformed JSON fails cleanly | **Done** |
| 2 | Blueprint review & decision | Two-tier review, focused section editing, versioned Accept / Request changes / Reject decisions | **Done** and browser-verified. Restructured (§4.2); feedback-driven revision shipped (§4.3) |
| 3 | Simulation generation (shell/core) | Accepted blueprint projects its manifest; call #2 receives the full blueprint and yields `core_html`; shell renders approved controls, core honors approved visuals and rules | **Done** and browser-verified. All seven slices; the spike is deleted |
| 4 | Refinement loop + versioning | Targeted feedback edit → new version; rollback works; ambiguous feedback → clarification | Next |

**Before milestone 3 — transport bar plumbing. Done.** All five steps shipped; spec §7.4 is now the contract. Nothing here blocks milestone 3 any more.

1. ~~`time_stepped: bool` in `PLAN_SCHEMA` and `MANIFEST_SCHEMA`~~ — carried by `manifest_from_plan`. In `PLAN_SCHEMA` it sits directly after `simulation_experience`, so the model decides it having just written `student_actions` and `completion_state`. Both schemas re-checked strict-mode legal.
2. ~~`sim:step` added to the protocol~~ — spec §7.3, alongside `sim:play` / `sim:pause` / `sim:reset`.
3. ~~Fixed Step/Run/Pause/Reset bar in `ControlPanel`~~ — one `TransportBar`, four buttons, rendered only when `time_stepped`. The panel's own "Reset to defaults" button hides in that case; two Resets would invite two meanings.
4. ~~The core must not draw its own run buttons~~ — forbidden by name in `_CORE_RUNTIME_CONTRACT`, and since milestone 3 also enforced by `validate_core` rather than left to the prompt.
5. ~~`PLAN_SYSTEM_PROMPT` sets the flag~~ — and is told never to list run controls as controls.

Two things this exposed that were not in the plan:

- **Run commands needed a channel that did not exist.** `SandboxedSimFrame` only pushed parameter *state*; a step is a one-shot *event*. It now exposes an imperative `send(command)` handle (React 19 `ref`-as-prop), dropped before `sim:ready` since the core has no listener yet.
- **Nothing ever posted `sim:reset`.** Reset used to only set React values back to defaults, which cannot clear elapsed time, trails, or step counters inside the core. Reset is now both halves — defaults *and* `sim:reset`. That was a latent bug in the existing shell, not new work.
- **A new required field breaks the rows already in the table.** All 14 existing `plan_versions` predated `time_stepped`, so an old blueprint would have 422'd on accept-with-modifications (`edits` is typed `Plan`) and failed manifest projection at milestone 3. Migration `0004` is a data-only backfill setting it `false`, which is truthful rather than merely safe — those blueprints were authored when nothing could step. The field stays strictly required, so a malformed model response still fails loudly. **Check stored rows against any future required field**; schema-legal and data-legal are different questions, and only the second one needs the database running.

**One consequence to know about:** the backfill cannot guess, so it set `false` everywhere — including three *accepted* plans that plainly step. Those three (`Binary Search: Halving the Hunt`, `What Sets a Pendulum's Period?`, `Equilibrium Still Moves`) were afterwards corrected to `true` by **direct SQL against the dev database, not a migration** — their own `student_actions` say "Press Step" / "Press Run", so the value was read off the blueprint rather than guessed. That repair does **not** reproduce: rebuild this database from migrations alone and all three return to `false`, correctly, and need re-ticking. The rule the repair followed, if you need it again:

```sql
UPDATE plan_versions pv SET plan_json = jsonb_set(plan_json, '{time_stepped}', 'true'::jsonb, true)
  FROM labs l WHERE l.active_plan_id = pv.id AND pv.plan_json ? 'concept_summary'
   AND lower(pv.plan_json->'simulation_experience'->>'student_actions') ~ '(press step|press run|press start|press play|pause)';
```

A fourth accepted plan (`Osmosis…`) still fails `Plan` validation for an unrelated, pre-existing reason — it is one of the retired classroom lesson-plan rows (§2.2), not a blueprint. It cannot be repaired and is the natural test fixture for milestone 3's "this blueprint predates the current format" guard.

**Verified:** frontend lint, `tsc`, and production build pass; backend Ruff passes; a written check asserts both schemas are strict-legal, that `Plan`/`Manifest` field order still mirrors their schemas, and that the flag survives projection in both states. Against live `gpt-5.5`: a projectile blueprint returned `time_stepped: true` and — notably — stopped listing "press Run" as a student action, while a static pH blueprint returned `false`. `ruff format --check` still reports `prompts.py` and `tasks/plan.py`, but both were already non-conforming beforehand; left alone rather than mixed into this change.

**Since resolved:** the transport bar has been browser-verified by the owner driving a real generated core. Three cores implement `sim:step` and the full handshake, and `backend/tests/` is now a real (if small) suite.

### Next session — milestone 4, the refinement loop (LLM call #3)

What it delivers: a teacher looks at the generated simulation, types *"make the trail fade faster"* or *"add a mass slider"*, and gets a new version — plus rollback to any earlier one. It is the last pipeline stage in the POC. **Anything past it is v1** (§3).

**Do this first.** PR [#1](https://github.com/Ahead-LLM/Simulation-Generator/pull/1) — `milestone-3-simulation-generation` → `main` — is open and unmerged, and carries nine commits (the transport bar plus all of milestone 3). Merge it before starting; nothing should be built on top of an unmerged branch that size.

**Already in place — milestone 4 is smaller than milestone 3 was:**

1. **The data model is ready.** `simulations` already carries `version`, `is_current` and `change_summary`, so **no migration is needed** to write a v+1 or to flip the current row. `simulation_feedback` does not exist yet and is the one new table.
2. **`_run` in `src/tasks/simulation.py` already demotes-then-inserts**, guarded by the partial unique index. The edit task should reuse that ordering exactly rather than inventing its own — getting it backwards fails the insert.
3. **Rollback needs no LLM call at all.** `POST /api/simulations/{id}/activate` just flips `is_current`.

**The three genuinely new problems:**

4. **One schema, two outcomes.** Feedback produces either an edit or a request for clarification ("which trail do you mean?"). Strict Structured Outputs cannot express "one of two shapes", so this is a **single** schema with an `outcome` discriminator, not two alternatives (spec §6, §8).
5. **Call #3 may legitimately change the manifest.** "Add a mass slider" means new controls. This is the one place the blueprint stops owning the manifest — which is exactly why v1 is append-only and rollback-able. Do not treat a manifest change as a bug to prevent; treat losing the approved v1 as the bug.
6. **`validate_core` still has no tests, and call #3's output must pass the same gate.** The gate is about to become load-bearing in a second place while being the one pure function with zero coverage (`check_coherence` has 12). Write `tests/test_validate.py` *before* extending it — same shape: pure function, fixture cores, no stack.

**Two decisions this milestone should force:**

7. **§5 item 8 — should the transport bar be on for every simulation?** The owner's stated preference is yes. It was deferred until real cores existed to judge against; **three now do**, so this is decidable and no longer needs to wait. Deciding it also unblocks §5 item 9, which must not be restyled first.
8. **§5 item 2 — polling vs SSE.** Accept-to-simulation is already ~2 minutes and an edit round trip adds another, so this is where the wait starts to hurt. A staged progress message costs nothing and buys most of the perceived improvement.

**Also open, lower priority:** §5 item 10 (the two indistinguishable version counters) is best fixed while building the version rail, since the rail makes the distinction visible anyway. §5 item 11 (layout rules for the generated region) should be judged against more cores before being tightened further — and note the size drop recorded in §2.2.1.

**Compose services to expect:** `nginx`, `api`, `celery-worker-generation`, `rabbitmq`, `redis`, `postgres`. No `frontend` service — that runs on the host. No `flower`, `celery-beat`, MinIO, or Langfuse; see `SIMGEN_POC_SPEC.md` §11.1 for why each was left out.

---

## 7. Risks & landmines

### 7.1 Hit during milestones 0–2 — real, not predicted

- **Docker Compose does not strip inline `#` comments from `.env` values.** The spec's original `OPENAI_API_KEY=  # set me` made the key literally `"# set me"`, which surfaced as a `UnicodeEncodeError` on an HTTP header deep inside httpx — nothing that names the actual problem. Keep every comment on its own line; `.env.example` is the canonical copy.
- **Recreate containers after editing `.env`.** A running container keeps the environment it started with. Adding the key and clicking Generate without `docker compose up -d --force-recreate api celery-worker-generation` reproduces the "key is not set" failure with a key sitting right there in the file.
- **A physically correct readout can still be unreadable.** One generated chemistry plan chose an Arrhenius fraction as a `%` readout; at its own default settings that is `3×10⁻⁹ %`, which rendered as `0.00` across the entire parameter space and looks exactly like a broken simulation. Two fixes now exist: the shell's `formatReadout` switches to exponential/precision formatting outside `1e-3 … 1e6`, and the prompt requires readouts to be legible **at the defaults**, recommending a ratio against starting conditions for quantities that are naturally astronomical.
- **A slider with null bounds used to validate.** Nothing checked that a `slider` actually had `min`/`max`/`step`, and `ControlPanel` falls back to `0–1` — a control that looks correct and silently drives the wrong range. `Parameter` now has a type-coherence validator (bounds present, `min < max`, positive step, default in range, boolean toggle defaults, dropdown default among its options). This matters more than it looks: teachers hand-edit these fields on the review screen, and the plan owns the manifest.
- **A blueprint can contradict itself, and the manifest believes the control.** The binary-search plan declared `Number of items` as a `slider`, `0–100`, step 1, default 50 — while its own `behavior_rules` said "list size choices use powers of two: 8, 16, 32, 64, 128" and its `initial_state` said the simulation opens with 16. `manifest_from_plan` copies the *control* verbatim, so the shell would ship the 0–100 slider and the core would receive rules it cannot satisfy (`0` items is also degenerate). The model picked `slider` where the rules demanded a `dropdown`. The prompt now requires rules to agree with declared controls and states that enumerated values mean a dropdown. **Fixed:** `check_coherence` reads numbers out of `behavior_rules`/`initial_state` and tests them against each control's range, step grid and type; a disagreement retries once with the specific contradictions fed back, then fails the job. See §5 item 7 for how hard it works to stay quiet, and why that matters more than what it catches.
- **Run controls had nowhere to live.** The same plan listed Step, Run, Pause and Reset under `student_actions`, but `_parameter_schema` allows only `slider | toggle | dropdown | number`, so the shell could not render them and the core would have had to draw its own buttons — breaking the shell/core split for every time-stepped simulation. **Decided and now built:** a fixed shell transport bar behind one `time_stepped` boolean (§4), specified in spec §7.4.
- **`worker.py` and `src/tasks/*` import each other.** The cycle resolves under both entry orders (worker-first for the Celery process, `main`-first for the API process) because `app` is defined before the bottom imports — but it is fragile. If you add a task, check `app.tasks` under both import orders rather than assuming.

### 7.2 Anticipated

- **No API key = fake progress.** The single most important lesson from the inherited plan. Verify against the real model, not a mock, from milestone 0 onward.
- **Next.js caching hides fresh generations.** Server Component `fetch` is cached by default; a regenerated plan or sim will render stale. Use `cache: 'no-store'` and `export const dynamic = 'force-dynamic'` on every route that reads an artifact. This is the most likely "why didn't it update?" bug in this stack.
- **Celery is sync, Tortoise is async.** Every task must open its own event loop and call `Tortoise.init` / `close_connections` *inside* the task — never at worker startup. A prefork child inheriting a loop or asyncpg pool across the fork fails with confusing "attached to a different loop" errors. Bridge helper is sketched in spec §11.0.
- **Never run `makemigrations` in the container entrypoint.** The entrypoint runs `tortoise migrate` only. Generated migrations are reviewed and committed by a developer; letting a running image invent schema is how drift starts.
- **Strict Structured Outputs has schema rules.** Every property must be listed in `required` and every object needs `"additionalProperties": false`; "optional" is expressed as a union with `null`. Call #3's two outcomes (edit vs. clarification) therefore share **one** schema with a discriminator, not two alternative shapes — see spec §6.
- **Trusting LLM output.** Every generation must be schema-validated before it's persisted; malformed JSON is a retryable, logged failure — never a crash. The raw response is stored for debugging.
- **Sandbox discipline.** The sim core runs generated code. Keep `sandbox="allow-scripts"` **without** `allow-same-origin`, and keep the network-blocking CSP inside the core. Don't loosen these for convenience.
- **Contract drift between shell and core.** The manifest parameter `id`s and the `postMessage` protocol (`sim:init` / `sim:set` / `sim:ready` / `sim:readout`) are the interface. If the generation prompt and the React shell drift apart, controls silently stop driving the sim. Treat §7 of the spec as the contract. **Now proven and enforced on one side:** three real cores honour the full handshake, and `validate_core` fails any that does not. It cannot catch a change made on the *React* side, so the spec is still the thing to keep both halves honest.
- **Giving the model a good example invites copying.** An illustrative teacher note in the plan prompt came back nearly verbatim in the first generated plan. Replacing the example with a *discriminator* the model has to apply to its own output ("a note that would fit any lesson on any topic is not worth writing") fixed it. Prefer tests over templates when prompting.
- **Scope creep toward the vision.** The out-of-scope list is the guardrail; anything past the refinement loop is v1.

---

## 8. Definition of done (POC)

A creator can: enter a topic → get an AI-drafted plan → accept it → generate a working, interactive, sandboxed simulation → refine it with plain-language feedback that produces a new version → and roll back to any prior version. All generation runs as background jobs with visible progress. No publish, no deploy, no student features.

**Progress against that sentence:** everything up to and including "accept it" works today, against the real model, with append-only versioning. What remains is generating the simulation from the accepted plan (milestone 3) and the refinement loop with rollback (milestone 4).

---

## 9. Glossary

- **Shell** — the host-owned (React) control UI: sliders, toggles, layout, readouts, rendered from the manifest. Identical across all sims.
- **Core** — the LLM-generated, sandboxed simulation itself (`core_html`): canvas + logic that receives parameters and renders.
- **Manifest** — the JSON contract describing a sim's title, concept, adjustable parameters, and readouts; drives the shell and scopes feedback.
- **Generation job** — a background task (plan, simulation, or edit) tracked in `generation_jobs` and polled by the frontend.
- **`is_current`** — the flag marking the active simulation version for the blueprint's internal `main` component.
- **Simulation blueprint** — the teacher-readable generation contract: purpose, experience, controls, visuals, readouts, behavior rules, and expected observations.
- **Projection** — turning an accepted blueprint's controls and readouts into `manifest_json` with `manifest_from_plan`. Deterministic code, no LLM: what the teacher approved is what ships.
- **The spike** — the milestone-0 throwaway at `/spike` that went prose → simulation in one call, skipping the plan. It proved the plumbing and was deleted at the end of milestone 3. Referenced here because older commits and comments still mention it.
