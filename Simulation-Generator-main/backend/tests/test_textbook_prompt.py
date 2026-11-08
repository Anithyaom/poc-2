"""Grounding must never change the prompt of a lab without a source, and must never
send the plan model more textbook than the cap allows."""

import pytest

from src.lab.models import Lab
from src.llm.prompts import (
    plan_revision_user_prompt,
    plan_user_prompt,
    strip_diagram_labels,
    textbook_source_block,
    truncate_words,
)
from src.tasks import plan as plan_task
from src.textbook.library import SourceSection


def make_section(text: str) -> SourceSection:
    return SourceSection(
        ref="gp8:p2:c2:s4",
        book="Ganita Prakash",
        grade=8,
        part=2,
        chapter=2,
        chapter_title="The Baudhāyana-Pythagoras Theorem",
        number="2.4",
        title="Combining Two Different Squares",
        page_start=41,
        page_end=47,
        text=text,
    )


ARGS = dict(
    description="Show why squares combine.",
    audience="Grade 8",
    course_title="Maths 8",
    course_subject="Mathematics",
)


def test_short_text_is_kept_whole():
    assert truncate_words("one two\nthree", 10) == ("one two\nthree", False)


def test_truncation_cuts_at_a_line_break_within_the_cap():
    text = "\n".join(f"line {i} has five words" for i in range(100))  # 500 words
    out, cut = truncate_words(text, 52)
    assert cut
    assert len(out.split()) == 50  # ten whole lines; the eleventh would exceed 52
    assert out.endswith("line 9 has five words")


def test_one_huge_line_is_cut_mid_line_rather_than_dropped():
    out, cut = truncate_words(" ".join(["w"] * 1000), 100)
    assert cut and len(out.split()) == 100


def test_block_names_the_section_and_marks_truncation():
    block = textbook_source_block(make_section("word " * 2000), max_words=300)
    assert 'section 2.4 "Combining Two Different Squares" (pp. 41–47)' in block
    assert "only its opening is included" in block
    excerpt = block.split("<textbook_excerpt>")[1]
    assert len(excerpt.split()) < 300 + 20


def test_untruncated_block_has_no_truncation_note():
    block = textbook_source_block(make_section("A short section."), max_words=300)
    assert "only its opening" not in block
    assert "A short section." in block


def test_ungrounded_prompts_are_unchanged():
    assert plan_user_prompt(**ARGS) == plan_user_prompt(**ARGS, source=None)
    assert "Textbook source" not in plan_user_prompt(**ARGS)
    revision = dict(
        plan={"title": "T"},
        feedback="Change it.",
        audience="Grade 8",
        course_title="Maths 8",
        course_subject="Mathematics",
    )
    assert "Textbook source" not in plan_revision_user_prompt(**revision)


def test_grounded_prompts_carry_the_block_before_the_instruction():
    block = textbook_source_block(make_section("Body."), max_words=300)
    user = plan_user_prompt(**ARGS, source=block)
    assert user.index("Show why squares combine.") < user.index(block)
    assert user.endswith("Draft the simulation blueprint.")
    revision = plan_revision_user_prompt(
        plan={"title": "T"},
        feedback="Use the book's example.",
        audience="Grade 8",
        course_title="Maths 8",
        course_subject="Mathematics",
        source=block,
    )
    assert block in revision and revision.index(block) < revision.index("Return the COMPLETE")


def test_task_sends_no_block_for_an_ungrounded_lab():
    assert plan_task._source_block(Lab(source_ref=None)) is None


def test_task_refuses_to_draft_when_the_section_cannot_be_loaded(monkeypatch):
    monkeypatch.setattr(plan_task, "resolve_ref", lambda ref: None)
    with pytest.raises(plan_task.SourceUnavailable):
        plan_task._source_block(Lab(source_ref="gp8:p2:c2:s4"))


def test_task_caps_the_excerpt_with_the_configured_budget(monkeypatch):
    monkeypatch.setattr(plan_task, "resolve_ref", lambda ref: make_section("word " * 5000))
    monkeypatch.setattr(plan_task.settings, "textbook_excerpt_max_words", 120)
    block = plan_task._source_block(Lab(source_ref="gp8:p2:c2:s4"))
    assert len(block.split("<textbook_excerpt>")[1].split()) < 140


def test_diagram_labels_are_dropped_but_short_prose_and_formulas_stay():
    text = "\n".join(
        [
            "Join the two squares.",
            "a",
            "b",
            "b – a",
            "90 – x",
            "+ →",
            "1.",
            "XWa",
            "Why?",
            "Area A",
            "a2 + b2 = c2.",
            "the areas of T,",
            "If",
            "As",
        ]
    )
    assert strip_diagram_labels(text).splitlines() == [
        "Join the two squares.",
        "Why?",
        "Area A",
        "a2 + b2 = c2.",
        "the areas of T,",
        "If",
        "As",
    ]


def test_labels_do_not_count_against_the_budget():
    text = "\n".join(["Real sentence of five words."] * 10 + ["a"] * 500)
    block = textbook_source_block(make_section(text), max_words=60)
    assert "only its opening" not in block
