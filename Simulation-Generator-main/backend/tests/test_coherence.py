"""The cross-check is judged on its silence.

Every case below that asserts *no* problem is the real subject of this file: a
false positive rejects a blueprint a teacher would have been happy with, which is
worse than the contradiction the check exists to catch. The two loud cases prove
it has not simply been muted.

Several of the silent cases are taken from blueprints already in the database —
they are regressions, not hypotheticals.
"""

from src.llm.coherence import check_coherence
from src.llm.schemas import Plan


def make_plan(*, controls: list[dict], rules: list[str], initial_state: str = "It opens.") -> Plan:
    """A minimally valid blueprint. Only controls and prose matter here."""
    return Plan(
        title="T",
        inferred_subject="Physics",
        inferred_topic="Topic",
        concept_summary="Summary.",
        learning_objective="Objective.",
        misconception="Misconception.",
        simulation_experience={
            "summary": "Summary.",
            "initial_state": initial_state,
            "student_actions": ["Drag the slider."],
            "completion_state": "It runs continuously.",
        },
        time_stepped=True,
        controls=[{"rationale": "Because.", **control} for control in controls],
        readouts=[],
        expected_observations=["Something happens."],
        visual_elements=[{"name": "Scene", "description": "A scene."}],
        behavior_rules=rules,
    )


def slider(**overrides) -> dict:
    return {
        "id": "n",
        "label": "Number of items",
        "type": "slider",
        "min": 0,
        "max": 100,
        "step": 1,
        "unit": None,
        "options": None,
        "default": 16,
        **overrides,
    }


# --- The check speaks -----------------------------------------------------------------


def test_a_slider_whose_rule_lists_unreachable_choices_is_a_dropdown():
    plan = make_plan(
        controls=[slider()],
        rules=["Number of items may be 8, 16, 32, 64, or 128."],
    )
    (problem,) = check_coherence(plan)
    assert "dropdown" in problem
    assert "Number of items" in problem


def test_a_rule_naming_a_value_outside_the_range():
    plan = make_plan(
        controls=[
            slider(id="v", label="Launch speed", min=5, max=30, step=1, unit="m/s", default=20)
        ],
        rules=["At a Launch speed of 45 m/s the projectile clears the wall."],
    )
    (problem,) = check_coherence(plan)
    assert "45" in problem
    assert "5 and 30" in problem


def test_choices_off_the_step_grid_are_unreachable_too():
    plan = make_plan(
        controls=[slider(min=0, max=100, step=10)],
        rules=["Number of items may be 10, 25, or 50."],
    )
    assert check_coherence(plan)


def test_one_message_per_problem_however_many_rules_repeat_it():
    plan = make_plan(
        controls=[slider()],
        rules=[
            "Number of items may be 8, 16, 32, 64, or 128.",
            "Number of items may be 8, 16, 32, 64, or 128, whichever the student picks.",
        ],
    )
    assert len(check_coherence(plan)) == 1


# --- The check stays quiet ------------------------------------------------------------


def test_a_coherent_blueprint_says_nothing():
    plan = make_plan(
        controls=[slider()],
        rules=["Halving Number of items removes one step from the search."],
    )
    assert check_coherence(plan) == []


def test_examples_a_slider_can_actually_reach_are_examples_not_choices():
    plan = make_plan(
        controls=[slider()],
        rules=["Try Number of items at 8, 16, or 32 to see the pattern."],
    )
    assert check_coherence(plan) == []


def test_a_rule_that_excludes_a_value_agrees_with_a_range_that_excludes_it():
    """Verbatim from `What Sets a Pendulum's Period?` — the first false positive."""
    plan = make_plan(
        controls=[
            slider(id="a", label="Starting angle", min=2, max=80, step=1, unit="°", default=10)
        ],
        rules=[
            "The simulation should not allow a Starting angle of 0°, because then no "
            "visible swing or period measurement would occur."
        ],
    )
    assert check_coherence(plan) == []


def test_another_quantity_in_the_same_sentence_is_not_this_control():
    """`at 20 m/s it travels 40 m` — 40 is a distance, not an out-of-range speed."""
    plan = make_plan(
        controls=[
            slider(id="v", label="Launch speed", min=5, max=30, step=1, unit="m/s", default=20)
        ],
        rules=["At a Launch speed of 20 m/s the projectile travels 40.79 m and rises 10.2 m."],
    )
    assert check_coherence(plan) == []


def test_a_control_with_no_unit_gets_no_range_check():
    """Without a unit there is no way to tell which number is about this control."""
    plan = make_plan(
        controls=[slider()],
        rules=["Number of items governs the search, which finishes in 7 comparisons."],
    )
    assert check_coherence(plan) == []


def test_rules_that_never_name_the_control_are_left_alone():
    plan = make_plan(
        controls=[slider()],
        rules=["The list is drawn as 8, 16, 32, 64, or 128 boxes across the top."],
    )
    assert check_coherence(plan) == []


def test_toggles_and_dropdowns_have_nothing_to_contradict():
    plan = make_plan(
        controls=[
            {
                "id": "trail",
                "label": "Show trail",
                "type": "toggle",
                "min": None,
                "max": None,
                "step": None,
                "unit": None,
                "options": None,
                "default": True,
            },
            {
                "id": "size",
                "label": "List size",
                "type": "dropdown",
                "min": None,
                "max": None,
                "step": None,
                "unit": None,
                "options": [{"value": "8", "label": "8"}, {"value": "16", "label": "16"}],
                "default": "8",
            },
        ],
        rules=["Show trail may be 1, 2, or 3.", "List size may be 8, 16, 32, or 64."],
    )
    assert check_coherence(plan) == []


def test_the_opening_state_is_checked_like_a_rule():
    plan = make_plan(
        controls=[
            slider(id="a", label="Starting angle", min=2, max=80, step=1, unit="°", default=10)
        ],
        rules=["The pendulum swings."],
        initial_state="It opens with the Starting angle at 95° on Earth gravity.",
    )
    assert check_coherence(plan)
