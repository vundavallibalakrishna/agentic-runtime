"""Bar, line, area, scatter and pie charts as PNG files in the run workspace."""

from __future__ import annotations

import struct
import zlib
from itertools import pairwise
from typing import TYPE_CHECKING

from ar_common.sandboxkit import confine
from ar_domain.analytics.slide import render_slide
from ar_domain.analytics.themes import THEMES, ChartTheme, theme_for

if TYPE_CHECKING:
    from typing import Any

_WIDTH = 640
_HEIGHT = 360
_KINDS = frozenset({"bar", "line", "area", "scatter", "pie"})


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
    png = render_chart(kind, rows, theme=theme.name)
    slide = _flag(arguments.get("slide") or arguments.get("deck"))
    from ar_domain.tools.general import _prepare, _store_file  # noqa: PLC0415

    root = _prepare(store, arguments)
    target = confine(root, "/workspace/outputs/chart.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(png)
    saved = _store_file(store, arguments, name="chart.png", data=png)
    files = [saved]
    title = str(arguments.get("title") or kind)
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


def render_chart(kind: str, rows: list[tuple[str, float]], *, theme: str = "ink") -> bytes:
    """Return a PNG. Colours come from the named theme."""
    chosen = theme_for(theme) or THEMES["ink"]
    width, height = _WIDTH, _HEIGHT
    pixels = bytearray(chosen.paper * (width * height))
    _frame(pixels, width, height, chosen)
    peak = max((value for _label, value in rows), default=1) or 1
    if kind == "pie":
        _pie(pixels, width, height, rows, chosen)
    elif kind == "scatter":
        _scatter(pixels, width, height, rows, peak, chosen)
    elif kind == "line":
        _line(pixels, width, height, rows, peak, chosen.ink)
    elif kind == "area":
        _area(pixels, width, height, rows, peak, chosen)
    else:
        _bars(pixels, width, height, rows, peak, chosen)
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


def _frame(pixels: bytearray, width: int, height: int, theme: ChartTheme) -> None:
    for x in range(48, width - 16):
        _dot(pixels, width, x, height - 28, theme.grid)
    for y in range(16, height - 28):
        _dot(pixels, width, 48, y, theme.grid)


def _bars(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    rows: list[tuple[str, float]],
    peak: float,
    theme: ChartTheme,
) -> None:
    slot = max(1, (width - 80) // max(1, len(rows)))
    for index, (_label, value) in enumerate(rows):
        bar = int((height - 56) * (value / peak))
        left = 56 + index * slot
        colour = theme.accents[index % len(theme.accents)]
        for y in range(height - 28 - bar, height - 28):
            for x in range(left, min(width - 8, left + max(2, slot - 6))):
                _dot(pixels, width, x, y, colour)


def _line(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    rows: list[tuple[str, float]],
    peak: float,
    colour: tuple[int, int, int],
) -> None:
    points = _points(width, height, rows, peak)
    for start, end in pairwise(points):
        _segment(pixels, width, start, end, colour)


def _area(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    rows: list[tuple[str, float]],
    peak: float,
    theme: ChartTheme,
) -> None:
    points = _points(width, height, rows, peak)
    baseline = height - 28
    colour = theme.accents[0]
    if len(points) == 1:
        _bars(pixels, width, height, rows, peak, theme)
        return
    for start, end in pairwise(points):
        span = max(1, end[0] - start[0])
        for step in range(span + 1):
            y = start[1] + (end[1] - start[1]) * step // span
            x = start[0] + (end[0] - start[0]) * step // span
            top = min(y, baseline)
            for yy in range(top, baseline):
                _dot(pixels, width, x, yy, colour)
    _line(pixels, width, height, rows, peak, theme.ink)


def _scatter(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    rows: list[tuple[str, float]],
    peak: float,
    theme: ChartTheme,
) -> None:
    for x, y in _points(width, height, rows, peak):
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                _dot(pixels, width, x + dx, y + dy, theme.ink)


def _points(
    width: int, height: int, rows: list[tuple[str, float]], peak: float
) -> list[tuple[int, int]]:
    span = max(1, len(rows) - 1)
    points: list[tuple[int, int]] = []
    for index, (_label, value) in enumerate(rows):
        x = 56 + int((width - 80) * index / span)
        y = height - 28 - int((height - 56) * (value / peak))
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
    cx, cy, radius = width // 2, height // 2, min(width, height) // 3
    start = 0.0
    for index, (_label, value) in enumerate(rows):
        sweep = 360.0 * max(0.0, value) / total
        colour = theme.accents[index % len(theme.accents)]
        _wedge(pixels, width, cx, cy, radius, start, start + sweep, colour)
        start += sweep


def _wedge(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    cx: int,
    cy: int,
    radius: int,
    start: float,
    end: float,
    colour: tuple[int, int, int],
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
    colour: tuple[int, int, int],
) -> None:
    steps = max(abs(end[0] - start[0]), abs(end[1] - start[1]), 1)
    for step in range(steps + 1):
        x = start[0] + (end[0] - start[0]) * step // steps
        y = start[1] + (end[1] - start[1]) * step // steps
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                _dot(pixels, width, x + dx, y + dy, colour)


def _dot(pixels: bytearray, width: int, x: int, y: int, colour: tuple[int, int, int]) -> None:
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
