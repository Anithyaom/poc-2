"""JSON Schemas for Structured Outputs + the Pydantic models we re-validate with.

Strict-mode rules: every property must appear in `required`, every object needs
`"additionalProperties": false`, and "optional" is a union with null — never
omission. The plan is a teacher-readable simulation blueprint, not a lesson plan.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# --- JSON Schema (sent to the model) ------------------------------------------------


def _parameter_schema(*, with_rationale: bool) -> dict[str, Any]:
    """One definition for both the plan's and the manifest's parameter shape.

    The plan's copy carries an extra teacher-facing `rationale`; everything else
    is identical, because `manifest_from_plan` copies these fields across verbatim.
    Defining them separately is how the two would drift.
    """
    properties: dict[str, Any] = {
        "id": {
            "type": "string",
            "description": "snake_case identifier, used verbatim in sim:init / sim:set",
        },
        "label": {"type": "string", "description": "What the teacher and student see"},
        "type": {"type": "string", "enum": ["slider", "toggle", "dropdown", "number"]},
        "min": {"type": ["number", "null"], "description": "slider/number only, else null"},
        "max": {"type": ["number", "null"], "description": "slider/number only, else null"},
        "step": {"type": ["number", "null"], "description": "slider/number only, else null"},
        "unit": {"type": ["string", "null"], "description": "e.g. 'm', 'm/s^2'; null if unitless"},
        "options": {
            "type": ["array", "null"],
            "description": "dropdown only, else null",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["value", "label"],
            },
        },
        "default": {"type": ["number", "boolean", "string"]},
    }
    required = ["id", "label", "type", "min", "max", "step", "unit", "options", "default"]

    if with_rationale:
        properties["rationale"] = {
            "type": "string",
            "description": (
                "One sentence, in plain teacher-facing language, on what a student "
                "learns by changing this. No jargon, no equations."
            ),
        }
        required.append("rationale")

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


_PARAMETER_SCHEMA = _parameter_schema(with_rationale=False)
_PLAN_PARAMETER_SCHEMA = _parameter_schema(with_rationale=True)

_READOUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "label": {"type": "string"},
        "unit": {"type": ["string", "null"]},
    },
    "required": ["id", "label", "unit"],
}

# One boolean, not a per-simulation list of run buttons. Step/Run/Pause/Reset are
# always the same four actions, so the shell renders a fixed transport bar rather
# than letting the model invent its own transport UI (§4 decision log).
_TIME_STEPPED_SCHEMA = {
    "type": "boolean",
    "description": (
        "True if the simulation advances through time or discrete steps, so the host "
        "renders its Step/Run/Pause/Reset bar. False for a purely static or "
        "instantly-recomputed view."
    ),
}

MANIFEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "concept": {"type": "string"},
        "learning_goal": {"type": "string"},
        "time_stepped": _TIME_STEPPED_SCHEMA,
        "parameters": {"type": "array", "items": _PARAMETER_SCHEMA},
        "readouts": {"type": "array", "items": _READOUT_SCHEMA},
    },
    "required": ["title", "concept", "learning_goal", "time_stepped", "parameters", "readouts"],
}

_SIMULATION_EXPERIENCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string", "description": "What the interactive experience is"},
        "initial_state": {"type": "string", "description": "What appears when it opens"},
        "student_actions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete things a student can do inside the simulation",
        },
        "completion_state": {
            "type": "string",
            "description": "What completes a run, or how continuous exploration works",
        },
    },
    "required": ["summary", "initial_state", "student_actions", "completion_state"],
}

_VISUAL_ELEMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string", "description": "Teacher-facing name for what is drawn"},
        "description": {
            "type": "string",
            "description": "How it looks and how its visual state changes",
        },
    },
    "required": ["name", "description"],
}

_PLAN_READOUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        **_READOUT_SCHEMA["properties"],
        "description": {
            "type": "string",
            "description": "What this value tells the student",
        },
    },
    "required": [*_READOUT_SCHEMA["required"], "description"],
}

PLAN_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string", "description": "The simulation's student-facing title"},
        "inferred_subject": {
            "type": "string",
            "description": "The subject you inferred from the teacher's prose, e.g. 'Physics'",
        },
        "inferred_topic": {
            "type": "string",
            "description": "The specific topic you inferred, e.g. 'Free fall and air resistance'",
        },
        "concept_summary": {
            "type": "string",
            "description": "One plain-language sentence confirming what will be simulated",
        },
        "learning_objective": {
            "type": "string",
            "description": "The primary understanding the simulation should create",
        },
        "misconception": {
            "type": "string",
            "description": "The mistaken idea or source of confusion the simulation addresses",
        },
        "simulation_experience": _SIMULATION_EXPERIENCE_SCHEMA,
        # Written straight after the experience: student_actions and completion_state
        # are exactly the evidence for whether the simulation advances through time.
        "time_stepped": _TIME_STEPPED_SCHEMA,
        "controls": {
            "type": "array",
            "description": "Things students can change",
            "items": _PLAN_PARAMETER_SCHEMA,
        },
        "readouts": {
            "type": "array",
            "description": "Computed values displayed to students",
            "items": _PLAN_READOUT_SCHEMA,
        },
        # Written after controls/readouts so observations can only reference things
        # already committed to, but before visuals/rules so those are designed to
        # make the observations visible. Strict mode generates in this order.
        "expected_observations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Specific discoveries a teacher can verify before approval",
        },
        "visual_elements": {
            "type": "array",
            "description": "Objects, diagrams, highlights, graphs, or animations shown",
            "items": _VISUAL_ELEMENT_SCHEMA,
        },
        "behavior_rules": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observable rules the generated simulation must implement",
        },
    },
    "required": [
        "title",
        "inferred_subject",
        "inferred_topic",
        "concept_summary",
        "learning_objective",
        "misconception",
        "simulation_experience",
        "time_stepped",
        "controls",
        "readouts",
        "expected_observations",
        "visual_elements",
        "behavior_rules",
    ],
}

# --- Call #2: simulation generation -------------------------------------------------

# The manifest is already fixed by the approved plan, so call #2 writes code only.
CORE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "core_html": {
            "type": "string",
            "description": "Complete self-contained HTML document for the sandboxed core",
        },
    },
    "required": ["core_html"],
}


# --- Pydantic (re-validated on our side after parsing) ------------------------------


class ParameterOption(BaseModel):
    value: str
    label: str


class Parameter(BaseModel):
    id: str
    label: str
    type: Literal["slider", "toggle", "dropdown", "number"]
    min: float | None = None
    max: float | None = None
    step: float | None = None
    unit: str | None = None
    options: list[ParameterOption] | None = None
    default: float | bool | str

    @model_validator(mode="after")
    def _coherent_for_type(self) -> "Parameter":
        """The fields a control needs must actually be present for its type.

        Without this a slider with null bounds validates cleanly, and the shell
        falls back to 0–1 — a control that looks right and drives the wrong range.
        It guards teacher edits too: the review screen lets a human retype these,
        and the plan owns the manifest (§6.1), so a bad edit would ship.
        """
        if self.type in ("slider", "number"):
            missing = [f for f in ("min", "max", "step") if getattr(self, f) is None]
            if missing:
                raise ValueError(f"{self.type} {self.id!r} is missing {', '.join(missing)}")
            if self.min >= self.max:
                raise ValueError(f"{self.id!r}: min must be below max")
            if self.step <= 0:
                raise ValueError(f"{self.id!r}: step must be positive")
            if isinstance(self.default, bool) or not isinstance(self.default, int | float):
                raise ValueError(f"{self.id!r}: {self.type} default must be a number")
            if not self.min <= self.default <= self.max:
                raise ValueError(f"{self.id!r}: default {self.default} is outside min/max")

        elif self.type == "toggle":
            if not isinstance(self.default, bool):
                raise ValueError(f"toggle {self.id!r}: default must be true or false")

        elif self.type == "dropdown":
            if not self.options:
                raise ValueError(f"dropdown {self.id!r} has no options")
            values = [o.value for o in self.options]
            if len(values) != len(set(values)):
                raise ValueError(f"dropdown {self.id!r} has duplicate option values")
            if self.default not in values:
                raise ValueError(f"dropdown {self.id!r}: default {self.default!r} is not an option")

        return self


class Readout(BaseModel):
    id: str
    label: str
    unit: str | None = None


class Manifest(BaseModel):
    title: str
    concept: str
    learning_goal: str
    time_stepped: bool
    parameters: list[Parameter] = Field(min_length=1)
    readouts: list[Readout]


class PlanParameter(Parameter):
    rationale: str


class SimulationExperience(BaseModel):
    summary: str
    initial_state: str
    student_actions: list[str] = Field(min_length=1)
    completion_state: str


class VisualElement(BaseModel):
    name: str
    description: str


class PlanReadout(Readout):
    description: str


class Plan(BaseModel):
    title: str
    inferred_subject: str
    inferred_topic: str
    concept_summary: str
    learning_objective: str
    misconception: str
    simulation_experience: SimulationExperience
    time_stepped: bool
    controls: list[PlanParameter] = Field(min_length=1)
    readouts: list[PlanReadout]
    expected_observations: list[str] = Field(min_length=1)
    visual_elements: list[VisualElement] = Field(min_length=1)
    behavior_rules: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_unique(self) -> "Plan":
        for field, items in (("control", self.controls), ("readout", self.readouts)):
            ids = [item.id for item in items]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {field} id")
        control_ids = {control.id for control in self.controls}
        readout_ids = {readout.id for readout in self.readouts}
        clash = control_ids & readout_ids
        if clash:
            raise ValueError(f"ids used as both control and readout: {sorted(clash)}")
        return self


class CoreOutput(BaseModel):
    core_html: str


# --- Plan → manifest projection -----------------------------------------------------


def manifest_from_plan(plan: Plan, component_ref: str = "main") -> Manifest:
    """Build the manifest the teacher approved. Deterministic — no LLM in between.

    This is the whole point of the plan owning the manifest: what ships is exactly
    what was reviewed. The only transformation is dropping the teacher-facing
    `rationale`, which the shell has no use for.
    """
    if component_ref != "main":
        raise KeyError(component_ref)
    return Manifest(
        title=plan.title,
        concept=plan.concept_summary,
        learning_goal=plan.learning_objective,
        time_stepped=plan.time_stepped,
        parameters=[Parameter(**p.model_dump(exclude={"rationale"})) for p in plan.controls],
        readouts=[Readout(**r.model_dump(exclude={"description"})) for r in plan.readouts],
    )
