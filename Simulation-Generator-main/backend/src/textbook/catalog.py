"""The textbook chapters simgen knows about, and where their PDFs live.

Filenames must match `data/fetch_ncert_pdfs.sh`, which downloads them into `data/pdfs/`.
"""

from typing import NamedTuple

BOOK_TITLE = "Ganita Prakash"
GRADE = 8
SOURCE = "NCERT, Ganita Prakash: Textbook of Mathematics for Grade 8 (NCF-SE 2023)"


class ChapterSource(NamedTuple):
    part: int
    chapter: int
    title: str
    filename: str


CHAPTERS: tuple[ChapterSource, ...] = (
    ChapterSource(1, 1, "A Square and A Cube", "part1_ch01_a_square_and_a_cube.pdf"),
    ChapterSource(1, 2, "Power Play", "part1_ch02_power_play.pdf"),
    ChapterSource(1, 3, "A Story of Numbers", "part1_ch03_a_story_of_numbers.pdf"),
    ChapterSource(1, 4, "Quadrilaterals", "part1_ch04_quadrilaterals.pdf"),
    ChapterSource(1, 5, "Number Play", "part1_ch05_number_play.pdf"),
    ChapterSource(
        1,
        6,
        "We Distribute, Yet Things Multiply",
        "part1_ch06_we_distribute_yet_things_multiply.pdf",
    ),
    ChapterSource(1, 7, "Proportional Reasoning-1", "part1_ch07_proportional_reasoning_1.pdf"),
    ChapterSource(2, 1, "Fractions in Disguise", "part2_ch01_fractions_in_disguise.pdf"),
    ChapterSource(
        2,
        2,
        "The Baudhāyana-Pythagoras Theorem",
        "part2_ch02_the_baudhayana_pythagoras_theorem.pdf",
    ),
    ChapterSource(2, 3, "Proportional Reasoning-2", "part2_ch03_proportional_reasoning_2.pdf"),
    ChapterSource(
        2,
        4,
        "Exploring Some Geometric Themes",
        "part2_ch04_exploring_some_geometric_themes.pdf",
    ),
    ChapterSource(2, 5, "Tales by Dots and Lines", "part2_ch05_tales_by_dots_and_lines.pdf"),
    ChapterSource(2, 6, "Algebra Play", "part2_ch06_algebra_play.pdf"),
    ChapterSource(2, 7, "Area", "part2_ch07_area.pdf"),
)

# Section headings that wrap onto a second line in the PDF, so the extracted heading is
# cut short. Keyed by (part, chapter, section number) -> the full printed title.
SECTION_TITLES: dict[tuple[int, int, str], str] = {
    (1, 4, "4.3"): "More Quadrilaterals with Parallel Opposite Sides",
    (2, 2, "2.7"): "Further Applications of the Baudhāyana-Pythagoras Theorem",
}
