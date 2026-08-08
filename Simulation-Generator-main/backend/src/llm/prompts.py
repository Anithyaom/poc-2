"""Prompt text for blueprint generation (call #1) and simulation cores (call #2).

The core contract and the React SandboxedSimFrame/ControlPanel form one protocol.
Change them together or generated controls will silently stop working.
"""

import json

PLAN_SYSTEM_PROMPT = """\
You help a teacher turn a rough request into a precise blueprint for ONE interactive \
simulation. This is not a lesson plan. Do not create readings, classroom activities, \
timings, worksheets, assessments, or teacher notes. Everything you return must help \
the teacher review what the simulation will show, allow, calculate, or teach.

The blueprint is read by a teacher and then used to generate code. Use direct, plain \
language. Never mention JSON, manifests, schemas, component refs, message protocols, \
or implementation details.

## Confirm the request
Infer `inferred_subject` and `inferred_topic` from the teacher's prose. Give the \
simulation a short student-facing `title`, and summarize the specific concept in \
`concept_summary`. Commit to a clear interpretation rather than hedging.

## Match the depth to the audience
The audience names the level. Calibrate to it and never above it.
- School grades: one relationship at a time, whole numbers where possible, everyday \
language, no formal notation.
- Undergraduate: named quantities, standard units, and a stated relationship are \
expected. Two interacting factors are acceptable.
- Graduate: assume the standard result is already known. Probe a limiting case, a \
failure mode, a boundary condition, or a competing regime rather than restating the \
definition. `misconception` should name a subtle or expert-level error, not a \
beginner one.

Depth changes the concept, the ranges, and the language. It never changes the number \
of controls, and it never adds lesson material.

## Define the purpose
`learning_objective` is the single most important understanding the simulation must \
create.

`misconception` is shown to the teacher as "Where students go wrong." Write it as one \
plain sentence describing what students believe or where they get stuck — a wrong \
idea, an incomplete idea, a confusion, or a step they cannot picture. Not every topic \
has a textbook misconception; an incomplete or over-general belief is equally valid. \
Do not use the word "misconception" in the text, and do not address the teacher.

## Specify the experience
Describe only what happens inside the interactive simulation:
- `summary`: the overall experience in 2–3 sentences.
- `initial_state`: exactly what is visible when it opens.
- `student_actions`: concrete interactions available to the student.
- `completion_state`: what completes a run, or how continuous exploration and reset work.

Set `time_stepped` to true when the simulation advances — animating over time, or \
progressing through discrete steps, iterations, trials, or rounds. Set it to false \
when changing a control simply recomputes a static picture. When it is true the \
student gets a Step, Run, Pause and Reset toolbar for free, so never list those as \
controls and never describe drawing them.

## Choose controls carefully
Provide 1–5 controls. Every control must create a meaningful, visible comparison. \
Allowed types are `slider`, `toggle`, `dropdown`, and `number`.
- Slider/number: sensible min, max, step, and numeric default; options is null.
- Toggle: boolean default; min, max, step, unit, and options are null.
- Dropdown: at least two options and a matching default; min, max, and step are null.
- `rationale` tells the teacher what changing the control helps a student discover.

Before choosing numeric bounds, reason through the governing relationship, plausible \
values, visibility of the effect, and a useful default. Defaults must not hide the \
phenomenon. Prefer a few purposeful controls over a configurable dashboard.

## Specify displayed values
`readouts` are computed outputs, never controls. Provide 0–4. Each needs a label, \
optional unit, and description of what it communicates. Values must be distinct and \
legible at the defaults; use a ratio or better unit rather than a value that appears \
to be zero throughout the useful range.

## Commit to what the teacher should see
`expected_observations` contains 2–5 specific outcomes the teacher can use to judge \
whether the generated simulation is correct. Each one must be reachable with the \
controls and readouts you just declared, and must state the control setting it needs. \
At least one must directly demonstrate the objective or challenge `misconception`.

Write these before the visuals and the rules. The remaining two fields exist to make \
these observations visible.

## Specify what appears
`visual_elements` names every important object, diagram, graph, highlight, trail, or \
animation. Each description states its appearance and how its visual state changes. \
Be concrete enough that a code generator does not invent the main visual design, and \
make sure every expected observation is visible in something you name here.

## Lock down behavior
`behavior_rules` are observable rules the generated simulation must implement: how \
controls affect the model, how step/run/reset work, constraints, edge cases, and visual \
state changes. Do not prescribe programming techniques.

Every rule must agree with the controls you declared. If a rule names specific values, \
those values must be reachable from that control's declared range, default, and type — \
a rule listing discrete choices means the control is a `dropdown`, not a `slider`.

Every control and readout `id` is a unique snake_case identifier. No id may be reused. \
IDs are internal plumbing, so labels and prose must remain natural and teacher-friendly.
"""


def plan_user_prompt(
    *, description: str, audience: str, course_title: str, course_subject: str
) -> str:
    """Give call #1 the teacher's prose and its course context."""
    return (
        f"Course: {course_title} ({course_subject})\n"
        f"Audience: {audience}\n\n"
        "The teacher described the simulation they want:\n\n"
        f"{description.strip()}\n\n"
        "Draft the simulation blueprint."
    )


def plan_revision_user_prompt(
    *,
    plan: dict,
    feedback: str,
    audience: str,
    course_title: str,
    course_subject: str,
) -> str:
    """Revise an existing blueprint from the teacher's own words.

    Deliberately reuses PLAN_SYSTEM_PROMPT and PLAN_SCHEMA: a revision is an
    ordinary plan generation with a different user prompt, so every rule already
    in force — audience depth, authoring order, control coherence — still applies.
    """
    return (
        f"Course: {course_title} ({course_subject})\n"
        f"Audience: {audience}\n\n"
        "This simulation blueprint was drafted for the teacher, and the teacher has "
        "asked for changes:\n\n"
        f"{json.dumps(plan, indent=2)}\n\n"
        f"The teacher's words:\n\n{feedback.strip()}\n\n"
        "Return the COMPLETE blueprint with their request applied. Change only what "
        "they asked about and what must follow from it: if a control changes, the "
        "behavior rules and expected observations that mention it must change with it, "
        "or the blueprint contradicts itself. Everything they did not raise must come "
        "back word for word. Do not re-word, re-order, improve, re-title, or re-explain "
        "anything they did not mention — they have already read and approved that text."
    )


_CORE_RUNTIME_CONTRACT = """\
You generate a complete, self-contained HTML simulation core. You do NOT generate \
control UI: no sliders, dropdowns, toggles, number inputs, or parameter labels, and \
no Step, Run, Play, Pause, or Reset buttons. The host renders all of those from the \
approved manifest. When the blueprint tells the student to press Step or Run, that \
button already exists in the host's own toolbar — implement the message it sends, \
never a button of your own.

## HTML and sandbox rules
- Start with `<!doctype html>` and put all HTML, CSS, and JavaScript in one document.
- Use no external resources: no CDN, fonts, images, fetch, XHR, or WebSockets.
- Include this tag verbatim in `<head>`:
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src \
'unsafe-inline'; style-src 'unsafe-inline'; img-src data:;">
- Render into a responsive canvas or DOM scene that fills the viewport.
- Use `requestAnimationFrame` and elapsed time for animation, not frame count.
- Catch runtime failures and report them with `sim:error`.

## Visual design — use the host's tokens, never your own colours
A `<style>` block defining these CSS custom properties is injected into your \
document's `<head>` automatically. They are always present. Style everything with \
them and never write a hex colour, a named colour, or a font stack of your own:
- `--sim-surface`, `--sim-surface-2` — the scene, and inset panels or plot backgrounds.
- `--sim-ink`, `--sim-ink-2` — primary and secondary text.
- `--sim-grid` — axes and gridlines. Keep them recessive; they are never the subject.
- `--sim-primary`, `--sim-secondary`, `--sim-tertiary` — pick by MEANING: the object \
under study, what it is compared against, and a third tracked quantity.
- `--sim-inactive` — excluded, unreached, or contextual elements.
- `--sim-good`, `--sim-warn`, `--sim-critical` — state only. Never as a fourth series.
- `--sim-font`, `--sim-mono`, `--sim-text-sm`, `--sim-text`, `--sim-text-lg`, \
`--sim-space`, `--sim-radius`, `--sim-stroke`.

In canvas code read them once with `getComputedStyle(document.documentElement)\
.getPropertyValue('--sim-primary')` rather than hard-coding the value.

Track at most three quantities by colour; beyond three the colours stop being \
distinguishable to colourblind readers, so combine, fold, or draw a second small \
view instead. Colour may never be the only thing distinguishing two elements — \
label every distinct element visibly. Use one axis per plot and never two different \
y-scales in the same chart.

## Layout — nothing may overlap anything else
The host gives you one region and no scrollbars, so everything you draw has to fit \
inside it at any window size. Lay the region out in bands and give each piece its \
own space:
- Reserve a title band at the top of every panel. Never draw a value, a legend, or \
an annotation into it.
- Keep axis labels, tick labels, and data labels inside the panel that owns them. If \
a label would cross an edge, shorten it or move it inside — never let it clip.
- Anchor floating annotations to the thing they describe and offset them so they \
never sit on a curve, an axis, or another label.
- Measure text before you place it (`ctx.measureText`) rather than assuming a width. \
Long units and negative signs are what actually collide.
- Two panels side by side need a visible gap between them, and each needs a minimum \
width — below it, stack them vertically instead.
- Re-layout on resize. Compute positions from the current canvas size every frame; \
never hard-code pixel coordinates that assume one window size.

## Ambition — build a scene, not a diagram
A teacher is judging whether this is worth putting in front of a class, so aim well \
above a single moving shape. Within the blueprint's own visual elements — never \
inventing subject matter it did not ask for:
- **Show history, not just the present instant.** A trail, a plotted series, a ghost \
of the previous run, or a small table of completed trials turns one moment into \
evidence of a pattern.
- **Link the views.** When two panels show the same system, make the connection \
explicit: a marker on the plot at the current instant, matched colours for matched \
objects, a highlight that moves in both at once.
- **Annotate the moment that matters.** Mark the peak, the crossing, the measured \
interval, the step being compared. A bracket or caret naming what a student is meant \
to notice is worth more than a smoother animation.
- **Make state legible without motion.** Paused, mid-run, complete, excluded, or \
out-of-range should each be visibly different when the simulation is standing still.
- **Show the numbers you already send.** A readout drawn beside the object it belongs \
to is far clearer than the same number only in the host panel, so long as it is \
identical to what you post in `sim:readout`.

Spend effort on making the approved expected observations unmistakable. Never spend \
it on decoration: no gradients, shadows, textures, logos, or ornamental framing.

## postMessage protocol
The core runs in a sandboxed iframe. Listen for:
- `{ type: 'sim:init', params }` — apply all initial values.
- `{ type: 'sim:set', id, value }` — apply one changed control.
- `{ type: 'sim:reset' }` — restore manifest defaults and return to the opening state.
- `{ type: 'sim:play' }` and `{ type: 'sim:pause' }` — start and halt time advancing.
- `{ type: 'sim:step' }` — advance exactly one step, then hold still.

When the manifest sets `time_stepped` to true you must implement all four of \
`sim:play`, `sim:pause`, `sim:step`, and `sim:reset`, and the simulation must open \
paused. A step is one meaningful unit of the model — one frame of integration, one \
comparison, one iteration — not a fixed wall-clock slice.

Post to `window.parent` with target origin `'*'`:
- `{ type: 'sim:ready' }` once the message listener is attached.
- `{ type: 'sim:readout', values }` at roughly 10 updates per second.
- `{ type: 'sim:error', message }` for a runtime failure.

Use every manifest control and readout id verbatim. Implement quantitatively correct \
relationships, real units where applicable, and visual scaling that makes the approved \
expected observations clearly visible.
"""


SIM_CORE_CONTRACT = """\
You receive an approved simulation blueprint and its fixed manifest. Honor the \
blueprint's experience, visual elements, behavior rules, and expected observations \
without adding or removing controls. Return `core_html` only; the manifest has already \
been approved and must not be regenerated.

""" + _CORE_RUNTIME_CONTRACT


def sim_core_user_prompt(*, plan: dict, manifest: dict) -> str:
    """Give call #2 the approved blueprint and the manifest projected from it.

    Both, not one: the manifest fixes the ids and ranges the core must use, and the
    blueprint carries everything the manifest deliberately drops — the visuals, the
    behaviour rules, and the observations the teacher approved. Sending only the
    manifest would ask the model to invent the simulation's substance; sending only
    the blueprint would let it drift off the ids the shell drives it with.
    """
    return (
        "Generate the simulation core for this approved blueprint.\n\n"
        f"## Approved blueprint\n{json.dumps(plan, indent=2)}\n\n"
        "## Fixed manifest — already approved by the teacher\n"
        "These ids, ranges, and defaults are binding. Use every id verbatim and do not "
        "add, remove, or re-range anything.\n"
        f"{json.dumps(manifest, indent=2)}\n\n"
        "Return core_html only."
    )
