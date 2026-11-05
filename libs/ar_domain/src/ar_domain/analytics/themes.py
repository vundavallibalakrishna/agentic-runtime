"""Palettes for general.chart. Values are RGB tuples, not UI colour tokens."""

from __future__ import annotations

from dataclasses import dataclass

_INK = (
    (37, 99, 168),
    (14, 116, 144),
    (180, 83, 9),
    (22, 101, 52),
    (136, 19, 55),
)


@dataclass(frozen=True)
class ChartTheme:
    name: str
    paper: tuple[int, int, int]
    grid: tuple[int, int, int]
    ink: tuple[int, int, int]
    accents: tuple[tuple[int, int, int], ...]


THEMES: dict[str, ChartTheme] = {
    "ink": ChartTheme("ink", (255, 255, 255), (226, 232, 240), (37, 99, 168), _INK),
    "slate": ChartTheme(
        "slate",
        (248, 250, 252),
        (203, 213, 225),
        (71, 85, 105),
        (
            (71, 85, 105),
            (100, 116, 139),
            (30, 64, 175),
            (14, 116, 144),
            (51, 65, 85),
        ),
    ),
    "forest": ChartTheme(
        "forest",
        (247, 254, 231),
        (190, 242, 100),
        (22, 101, 52),
        (
            (22, 101, 52),
            (21, 128, 61),
            (77, 124, 15),
            (6, 95, 70),
            (132, 204, 22),
        ),
    ),
    "ember": ChartTheme(
        "ember",
        (255, 247, 237),
        (254, 215, 170),
        (194, 65, 12),
        (
            (194, 65, 12),
            (180, 83, 9),
            (185, 28, 28),
            (146, 64, 14),
            (217, 119, 6),
        ),
    ),
    "midnight": ChartTheme(
        "midnight",
        (15, 23, 42),
        (51, 65, 85),
        (125, 211, 252),
        (
            (125, 211, 252),
            (167, 139, 250),
            (251, 191, 36),
            (74, 222, 128),
            (251, 113, 133),
        ),
    ),
}


def theme_for(name: str) -> ChartTheme | None:
    """Return a known theme. An empty name is ink."""
    picked = name.strip().lower() or "ink"
    return THEMES.get(picked)
