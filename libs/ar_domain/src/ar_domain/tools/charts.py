"""Bar, line, area, scatter and pie charts as PNG files in the run workspace.

The renderer is pure Python (no Pillow or matplotlib). It labels every chart so a
reader — a person or a vision model — can tell the categories and read the values:
a title, gridlines with y-axis tick values, a category label per bar or point, and
the value on each bar. Text is drawn from the 5x7 bitmap font in ``analytics.pixfont``.
"""

from __future__ import annotations

import struct
import zlib
from itertools import pairwise
from typing import TYPE_CHECKING, NamedTuple

from ar_common.sandboxkit import confine
from ar_domain.analytics import pixfont
from ar_domain.analytics.slide import render_slide
from ar_domain.analytics.themes import THEMES, ChartTheme, theme_for

if TYPE_CHECKING:
    from typing import Any

_WIDTH = 640
_HEIGHT = 360
_LEFT = 58  # room for y-axis tick labels
_RIGHT = 20
_TOP = 40  # room for the title
_BOTTOM = 46  # room for category labels
_TICKS = 4  # gridlines/ticks above the baseline
_KINDS = frozenset({"bar", "line", "area", "scatter", "pie"})

Colour = tuple[int, int, int]


class Area(NamedTuple):
    """The plot rectangle, inside the margins that hold the labels."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def w(self) -> int:
        return self.x1 - self.x0

    @property
    def h(self) -> int:
        return self.y1 - self.y0


def dispatch_chart(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object] | None:
    if name != "chart":
        return None
    rows = _rows(arguments)
    if not rows:
        return _error(
            "validation_failed", "chart needs rows, or xKey and yKey over a list of objects"
        )
    kind = str(arguments.get("kind") or "bar").lower()
    if kind not in _KINDS:
        return _error("validation_failed", "kind must be bar, line, area, scatter or pie")
    theme = theme_for(str(arguments.get("theme") or "ink"))
    if theme is None:
        return _error("validation_failed", "theme must be ink, slate, forest, ember or midnight")
    title = str(arguments.get("title") or kind)
    png = render_chart(kind, rows, theme=theme.name, title=title)
    slide = _flag(arguments.get("slide") or arguments.get("deck"))
    from ar_domain.tools.general import _prepare, _store_file  # noqa: PLC0415

    root = _prepare(store, arguments)
    target = confine(root, "/workspace/outputs/chart.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png)
    saved = _store_file(store, arguments, name="chart.png", data=png)
    files = [saved]
    if slide:
        narrative = str(arguments.get("narrative") or "")
        deck = render_slide(title=title[:200], narrative=narrative[:2000], png=png)
        deck_path = confine(root, "/workspace/outputs/chart.pptx")
        deck_path.write_bytes(deck)
        files.append(_store_file(store, arguments, name="chart.pptx", data=deck))
    note = " Wrote a slide." if slide else ""
    return {
        "text": f"Drew a {kind} chart ({len(rows)} points, {theme.name}).{note}",
        "structured": {
            "presentation": {
                "kind": "chart",
                "chart": kind,
                "theme": theme.name,
                "title": title,
                "files": files,
                "truncated": False,
            }
        },
        "is_error": False,
    }


def render_chart(
    kind: str, rows: list[tuple[str, float]], *, theme: str = "ink", title: str = ""
) -> bytes:
    """Return a labelled PNG. Colours come from the named theme."""
    chosen = theme_for(theme) or THEMES["ink"]
    width, height = _WIDTH, _HEIGHT
    pixels = bytearray(chosen.paper * (width * height))
    area = Area(_LEFT, _TOP, width - _RIGHT, height - _BOTTOM)
    peak = max((value for _label, value in rows), default=1) or 1
    if kind == "pie":
        _pie(pixels, width, height, rows, chosen)
        _pie_legend(pixels, width, height, rows, chosen)
    else:
        _grid(pixels, width, height, area, peak, chosen)
        if kind == "scatter":
            _scatter(pixels, width, area, rows, peak, chosen)
        elif kind == "line":
            _line(pixels, width, area, rows, peak, chosen.ink)
            _point_labels(pixels, width, height, area, rows, peak, chosen)
        elif kind == "area":
            _area(pixels, width, height, area, rows, peak, chosen)
            _point_labels(pixels, width, height, area, rows, peak, chosen)
        else:
            _bars(pixels, width, height, area, rows, peak, chosen)
        _x_labels(pixels, width, height, area, rows, chosen)
    if title:
        _title(pixels, width, height, title, chosen)
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        start = y * width * 3
        raw.extend(pixels[start : start + width * 3])
    return _png(width, height, bytes(raw))


def _rows(arguments: dict[str, object]) -> list[tuple[str, float]]:
    raw = arguments.get("rows")
    if not isinstance(raw, list):
        return []
    x_key = str(arguments.get("xKey") or arguments.get("x_key") or "")
    y_key = str(arguments.get("yKey") or arguments.get("y_key") or "")
    found: list[tuple[str, float]] = []
    for index, item in enumerate(raw):
        if isinstance(item, dict):
            label = str(item.get(x_key) or item.get("label") or item.get("x") or index)
            value = item.get(y_key) if y_key else None
            if value is None:
                value = item.get("value") or item.get("y") or _first_number(item)
            number = _number(value)
            if number is None:
                continue
            found.append((label, number))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            number = _number(item[1])
            if number is None:
                continue
            found.append((str(item[0]), number))
        else:
            number = _number(item)
            if number is not None:
                found.append((str(index), number))
    return found[:40]


def _first_number(row: dict[str, object]) -> object:
    for value in row.values():
        if _number(value) is not None:
            return value
    return None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _fmt(value: float) -> str:
    """A short label for an axis tick or a bar value."""
    if value == int(value):
        return str(int(value))
    rounded = round(value, 1)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.1f}"


def _title(pixels: bytearray, width: int, height: int, title: str, theme: ChartTheme) -> None:
    text = title.strip()
    while text and pixfont.text_width(text, scale=2) > width - 16:
        text = text[:-1]
    start = max(4, (width - pixfont.text_width(text, scale=2)) // 2)
    pixfont.draw_text(pixels, width, height, start, 10, text, theme.ink, scale=2)


def _grid(  # noqa: PLR0917
    pixels: bytearray, width: int, height: int, area: Area, peak: float, theme: ChartTheme
) -> None:
    for tick in range(_TICKS + 1):
        frac = tick / _TICKS
        yy = area.y1 - int(area.h * frac)
        for x in range(area.x0, area.x1):
            _dot(pixels, width, x, yy, theme.grid)
        label = _fmt(peak * frac)
        label_w = pixfont.text_width(label)
        pixfont.draw_text(pixels, width, height, area.x0 - 6 - label_w, yy - 3, label, theme.ink)
    for y in range(area.y0, area.y1 + 1):
        _dot(pixels, width, area.x0, y, theme.ink)


def _bars(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    area: Area,
    rows: list[tuple[str, float]],
    peak: float,
    theme: ChartTheme,
) -> None:
    slot = area.w / max(1, len(rows))
    bar_w = max(3, int(slot * 0.6))
    for index, (_label, value) in enumerate(rows):
        bar_h = int(area.h * (max(0.0, value) / peak))
        center = area.x0 + int(slot * (index + 0.5))
        left = center - bar_w // 2
        colour = theme.accents[index % len(theme.accents)]
        top = area.y1 - bar_h
        for y in range(top, area.y1):
            for x in range(left, left + bar_w):
                _dot(pixels, width, x, y, colour)
        label = _fmt(value)
        label_x = center - pixfont.text_width(label) // 2
        label_y = top - 9 if top - 9 >= area.y0 else top + 2
        pixfont.draw_text(pixels, width, height, label_x, label_y, label, theme.ink)


def _line(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    area: Area,
    rows: list[tuple[str, float]],
    peak: float,
    colour: Colour,
) -> None:
    for start, end in pairwise(_points(area, rows, peak)):
        _segment(pixels, width, start, end, colour)


def _area(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    area: Area,
    rows: list[tuple[str, float]],
    peak: float,
    theme: ChartTheme,
) -> None:
    points = _points(area, rows, peak)
    colour = theme.accents[0]
    if len(points) == 1:
        _bars(pixels, width, height, area, rows, peak, theme)
        return
    for start, end in pairwise(points):
        span = max(1, end[0] - start[0])
        for step in range(span + 1):
            y = start[1] + (end[1] - start[1]) * step // span
            x = start[0] + (end[0] - start[0]) * step // span
            for yy in range(min(y, area.y1), area.y1):
                _dot(pixels, width, x, yy, colour)
    _line(pixels, width, area, rows, peak, theme.ink)


def _scatter(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    area: Area,
    rows: list[tuple[str, float]],
    peak: float,
    theme: ChartTheme,
) -> None:
    for x, y in _points(area, rows, peak):
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                _dot(pixels, width, x + dx, y + dy, theme.ink)


def _point_labels(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    area: Area,
    rows: list[tuple[str, float]],
    peak: float,
    theme: ChartTheme,
) -> None:
    if len(rows) > 12:
        return
    for (x, y), (_label, value) in zip(_points(area, rows, peak), rows, strict=True):
        label = _fmt(value)
        label_x = x - pixfont.text_width(label) // 2
        label_y = y - 11 if y - 11 >= area.y0 else y + 6
        pixfont.draw_text(pixels, width, height, label_x, label_y, label, theme.ink)


def _x_labels(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    area: Area,
    rows: list[tuple[str, float]],
    theme: ChartTheme,
) -> None:
    slot = area.w / max(1, len(rows))
    max_chars = max(1, int(slot) // (pixfont.GLYPH_W + 1))
    for index, (label, _value) in enumerate(rows):
        text = str(label).upper()[:max_chars]
        center = area.x0 + int(slot * (index + 0.5))
        start = center - pixfont.text_width(text) // 2
        pixfont.draw_text(pixels, width, height, start, area.y1 + 6, text, theme.ink)


def _points(area: Area, rows: list[tuple[str, float]], peak: float) -> list[tuple[int, int]]:
    span = max(1, len(rows) - 1)
    points: list[tuple[int, int]] = []
    for index, (_label, value) in enumerate(rows):
        x = area.x0 + int(area.w * index / span) if len(rows) > 1 else area.x0 + area.w // 2
        y = area.y1 - int(area.h * (max(0.0, value) / peak))
        points.append((x, y))
    return points


def _pie(
    pixels: bytearray,
    width: int,
    height: int,
    rows: list[tuple[str, float]],
    theme: ChartTheme,
) -> None:
    total = sum(max(0.0, value) for _label, value in rows) or 1
    cx, cy, radius = width // 3, height // 2 + 6, min(width, height) // 3
    start = 0.0
    for index, (_label, value) in enumerate(rows):
        sweep = 360.0 * max(0.0, value) / total
        colour = theme.accents[index % len(theme.accents)]
        _wedge(pixels, width, cx, cy, radius, start, start + sweep, colour)
        start += sweep


def _pie_legend(
    pixels: bytearray,
    width: int,
    height: int,
    rows: list[tuple[str, float]],
    theme: ChartTheme,
) -> None:
    total = sum(max(0.0, value) for _label, value in rows) or 1
    x = width - 180
    y = _TOP + 6
    for index, (label, value) in enumerate(rows[:10]):
        colour = theme.accents[index % len(theme.accents)]
        for dy in range(8):
            for dx in range(8):
                _dot(pixels, width, x + dx, y + dy, colour)
        pct = round(100.0 * max(0.0, value) / total)
        text = f"{str(label).upper()[:14]} {pct}%"
        pixfont.draw_text(pixels, width, height, x + 12, y, text, theme.ink)
        y += 16


def _wedge(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    cx: int,
    cy: int,
    radius: int,
    start: float,
    end: float,
    colour: Colour,
) -> None:
    import math  # noqa: PLC0415

    for y in range(cy - radius, cy + radius):
        for x in range(cx - radius, cx + radius):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy > radius * radius:
                continue
            angle = (math.degrees(math.atan2(dy, dx)) + 360) % 360
            if start <= angle < end or (end > 360 and angle < end - 360):
                _dot(pixels, width, x, y, colour)


def _segment(
    pixels: bytearray,
    width: int,
    start: tuple[int, int],
    end: tuple[int, int],
    colour: Colour,
) -> None:
    steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]), 1)
    for step in range(steps + 1):
        x = start[0] + (end[0] - start[0]) * step // steps
        y = start[1] + (end[1] - start[1]) * step // steps
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                _dot(pixels, width, x + dx, y + dy, colour)


def _dot(pixels: bytearray, width: int, x: int, y: int, colour: Colour) -> None:
    if x < 0 or y < 0 or x >= width or y >= _HEIGHT:
        return
    offset = (y * width + x) * 3
    pixels[offset : offset + 3] = bytes(colour)


def _png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "pptx"}


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
