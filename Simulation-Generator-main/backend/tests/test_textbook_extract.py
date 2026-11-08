"""The textbook parser fails silently: a missed header becomes body text, a missed
heading merges two sections, a shifted page number cites the wrong page. Each case
below is a layout actually seen in the Ganita Prakash Grade 8 PDFs.
"""

from src.textbook.extract import answer_key_start, build_chapter, clean_page

FOOTER = "01_Chapter 1.indd   201_Chapter 1.indd   2 20-12-2025   16:28:4720-12-2025   16:28:47"


def test_strips_header_page_number_and_footer():
    raw = f"Ganita Prakash | Grade 8 | Part-II \n2\nSome body text , here.\n{FOOTER}\n"
    lines, page = clean_page(raw, index=1, chapter=1, title="Fractions in Disguise")
    assert lines == ["Some body text, here."]
    assert page == 2


def test_strips_chapter_running_title_and_reprint_footer():
    raw = "A Square and A Cube\n3\nBody.\nReprint 2026-27\n"
    lines, page = clean_page(raw, index=2, chapter=1, title="A Square and A Cube")
    assert lines == ["Body."]
    assert page == 3


def test_strips_running_header_emitted_mid_page():
    raw = "Ganita Prakash | Grade 8 | Part-II\n72\nFern\nExploring Some Geometric Themes\nMore."
    lines, _ = clean_page(raw, index=2, chapter=4, title="Exploring Some Geometric Themes")
    assert lines == ["Fern", "More."]


def test_removes_split_title_banner_on_first_page_only():
    raw = "1.1 Fractions as Percentages\nYou might have heard.\nFRACTIONS IN \nDISGUISE1\n"
    lines, page = clean_page(raw, index=0, chapter=1, title="Fractions in Disguise")
    assert lines == ["1.1 Fractions as Percentages", "You might have heard."]
    assert page is None


def test_keeps_lone_number_that_is_not_in_header_position():
    raw = "Area\n149\nThe side is\n7\nunits long."
    lines, _ = clean_page(raw, index=1, chapter=7, title="Area")
    assert lines == ["The side is", "7", "units long."]


def test_splits_sections_and_numbers_pages_from_printed_numbers():
    pages = [
        "Opening text.\n2.1 First Idea\nAlpha.",
        "Ganita Prakash | Grade 8\n20\nBeta.\n2.2 Second Idea\nGamma.",
        "Power Play\n21\nDelta.",
    ]
    ch = build_chapter(pages, part=1, chapter=2, title="Power Play")
    assert (ch.page_start, ch.page_end) == (19, 21)
    assert ch.intro == "Opening text."
    assert [(s.number, s.title, s.page_start, s.page_end) for s in ch.sections] == [
        ("2.1", "First Idea", 19, 20),
        ("2.2", "Second Idea", 20, 21),
    ]
    assert ch.sections[1].text == "Gamma.\nDelta."


def test_ignores_numbers_that_look_like_headings_but_break_the_sequence():
    pages = ["2.1 First Idea\nWeigh it.\n2.5 Kilograms of rice is heavy.\n3.2 Other Chapter"]
    ch = build_chapter(pages, part=1, chapter=2, title="Power Play")
    assert [s.number for s in ch.sections] == ["2.1"]
    assert "2.5 Kilograms of rice is heavy." in ch.sections[0].text


def test_keeps_a_repeated_section_number_as_printed():
    pages = [
        "2.1 A\nx.\n2.2 B\nx.\n2.3 C\nx.\n2.4 Powers of 10\nx.\n"
        "2.5 Did You Ever Wonder?\nx.\n2.5 A Pinch of History\nx."
    ]
    ch = build_chapter(pages, part=1, chapter=2, title="Power Play")
    assert [(s.number, s.title) for s in ch.sections][4:] == [
        ("2.5", "Did You Ever Wonder?"),
        ("2.5", "A Pinch of History"),
    ]


def test_completes_wrapped_heading_and_drops_its_continuation():
    pages = [
        "2.1 Doubling a Square\nx.\n"
        "2.2 Further Applications of the Baudhāyana -\nPythagor\nas Theorem\nThe theorem."
    ]
    ch = build_chapter(
        pages,
        part=2,
        chapter=2,
        title="The Baudhāyana-Pythagoras Theorem",
        section_titles={"2.2": "Further Applications of the Baudhāyana-Pythagoras Theorem"},
    )
    assert ch.sections[1].title == "Further Applications of the Baudhāyana-Pythagoras Theorem"
    assert ch.sections[1].text == "The theorem."


def test_answer_key_is_split_off_and_excluded_from_page_range():
    pages = [
        "1.1 Square Numbers\nBody.",
        "Ganita Prakash | Grade 8\n2\nMore body.",
        "1\nPage No. 2\nDoes every number have an even number of factors?\nAns. No",
        "2\nPage No. 7\nAns. 2n",
    ]
    assert answer_key_start(pages) == 2
    ch = build_chapter(pages, part=1, chapter=1, title="A Square and A Cube")
    assert ch.page_end == 2
    assert ch.sections[0].text == "Body.\nMore body."
    assert "Ans. No" in ch.answers and "Ans. No" not in ch.sections[0].text


def test_one_misread_page_number_does_not_shift_the_chapter():
    pages = [
        "1.1 Start\nA.",
        "Ganita Prakash | Grade 8\n2\nB.",
        "A Square and A Cube\n9\nC.",  # a diagram label in the page-number position
        "Ganita Prakash | Grade 8\n4\nD.",
    ]
    ch = build_chapter(pages, part=1, chapter=1, title="A Square and A Cube")
    assert (ch.page_start, ch.page_end) == (1, 4)
