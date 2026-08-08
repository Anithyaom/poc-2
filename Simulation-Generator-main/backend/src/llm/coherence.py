"""The plan cross-check: do the blueprint's own words agree with its own controls?

Schema validation proves each control is *internally* coherent — a slider has
bounds, a dropdown has options. It cannot see that `behavior_rules` describes a
control the teacher will never be able to operate: a slider whose rule lists five
specific choices, or a range that cannot reach the number a rule names.

Heuristic by necessity — prose is prose. Every rule here is written to stay
**silent** when unsure. A false positive blocks a good blueprint, which is worse
than the contradiction it prevents, so each check needs two independent signals
before it speaks: the control must be named *and* the numbers must be provably
unusable. A vague rule is deliberately allowed straight through.
"""

import re

from src.llm.schemas import Plan, PlanParameter

# A number the prose actually writes out. Deliberately no exponent form and no
# thousands separators: prose that reaches for those is not what this catches.
_NUMBER = r"-?\d+(?:\.\d+)?"

# "8, 16, 32, 64, or 128" — three or more numbers read as a list of choices.
# Two is not a list; it is far more often a range ("between 5 and 20").
_SEPARATOR = r"\s*(?:,\s*or|,\s*and|,|or|and)\s*"
_RUN = re.compile(rf"{_NUMBER}(?:{_SEPARATOR}{_NUMBER}){{2,}}")

# How far from the control's name a number must sit to be considered a claim
# *about that control*. A rule sentence is usually well inside this; a second
# sentence about something else usually is not.
_WINDOW = 80

# Prose that *excludes* a value agrees with a range that excludes it. A real
# blueprint says "the simulation should not allow a starting angle of 0°" right
# beside a slider that starts at 2° — the rule is the reason for the bound, not a
# contradiction of it. Any negation in the window buys silence.
_NEGATION = re.compile(
    r"\b(?:not|never|cannot|can't|won't|doesn't|don't|exclude[sd]?|excluding|avoid[s]?"
    r"|disallow[s]?|prevent[s]?|forbid[s]?|without|neither|nor)\b",
    re.IGNORECASE,
)


def check_coherence(plan: Plan) -> list[str]:
    """Return teacher-readable contradictions. Empty means the blueprint agrees.

    Only numeric controls are checked. A toggle has nothing to contradict and a
    dropdown already enumerates its own choices.
    """
    problems: list[str] = []
    prose = [*plan.behavior_rules, plan.simulation_experience.initial_state]

    for control in plan.controls:
        if control.type not in ("slider", "number"):
            continue
        for line in prose:
            for window in _windows(line, control.label):
                problems.extend(_check_window(control, window))

    # The same control can be named by several rules; say each thing once.
    return list(dict.fromkeys(problems))


def _windows(line: str, label: str) -> list[str]:
    """The stretches of a rule that talk about this control, by name."""
    return [
        line[max(0, match.start() - _WINDOW) : match.end() + _WINDOW]
        for match in re.finditer(re.escape(label), line, re.IGNORECASE)
    ]


def _check_window(control: PlanParameter, window: str) -> list[str]:
    """Two checks, in order. Enumeration wins — it is the more specific diagnosis."""
    if _NEGATION.search(window):
        return []

    run = _RUN.search(window)
    if run:
        listed = [float(n) for n in re.findall(_NUMBER, run.group())]
        if any(_unreachable(control, value) for value in listed):
            return [
                f"“{control.label}” is offered as {_as_control(control)}, but a rule "
                f"below it lists set choices ({_fmt_all(listed)}) — and some of those "
                f"cannot be reached. A control with set choices needs to be a dropdown."
            ]
        # Every listed value is reachable, so the slider genuinely works. Say nothing:
        # a rule may name examples without meaning them as the only options.
        return []

    named = _named_with_unit(control, window)
    outside = [value for value in named if not control.min <= value <= control.max]
    if outside:
        return [
            f"“{control.label}” can only be set between {_fmt(control.min)} and "
            f"{_fmt(control.max)}{_unit_suffix(control)}, but a rule names "
            f"{_fmt_all(outside)}{_unit_suffix(control)}."
        ]
    return []


def _named_with_unit(control: PlanParameter, window: str) -> list[float]:
    """Numbers written in this control's own unit — e.g. `20 m/s` for a m/s slider.

    Requiring the unit is what keeps the range check quiet. A rule about launch
    speed routinely names a distance in the same breath ("at 20 m/s it travels
    40 m"); without this, that 40 reads as an out-of-range speed and a perfectly
    good blueprint is rejected. A control with no unit gets no range check at all.
    """
    if not control.unit:
        return []
    pattern = rf"({_NUMBER})\s*{re.escape(control.unit)}(?![\w/^])"
    return [float(n) for n in re.findall(pattern, window, re.IGNORECASE)]


def _unreachable(control: PlanParameter, value: float) -> bool:
    """Outside the range, or between two stops the student can actually reach."""
    if not control.min <= value <= control.max:
        return True
    steps = (value - control.min) / control.step
    return abs(steps - round(steps)) > 1e-6


def _as_control(control: PlanParameter) -> str:
    """Say what the teacher sees on the review screen, never the schema's word."""
    return (
        "a slider the student drags" if control.type == "slider" else "a number the student types"
    )


def _fmt(value: float) -> str:
    return f"{value:g}"


def _fmt_all(values: list[float]) -> str:
    return ", ".join(_fmt(v) for v in values)


def _unit_suffix(control: PlanParameter) -> str:
    return f" {control.unit}" if control.unit else ""
