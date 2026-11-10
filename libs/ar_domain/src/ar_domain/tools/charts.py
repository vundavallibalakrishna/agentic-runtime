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
_TOP = 54  # room for the title and, for multi-series charts, the legend beneath it
_BOTTOM = 46  # room for category labels
_TICKS = 4  # gridlines/ticks above the baseline
_MAX_POINT_LABELS = 12  # beyond this, labelling every point clutters
_MAX_CATEGORIES = 20
_MAX_SERIES = 8
_MIN_LABEL_BAR_W = 12  # a grouped bar narrower than this has no room for a value label
_MAX_LABELLED_BARS = 16  # beyond this, per-bar labels clutter a grouped chart
_RIGHT_DUAL = 54  # a dual-axis chart needs room on the right for its second axis
_MIN_SEGMENT_LABEL_PCT = 8  # a 100%-stacked segment smaller than this is too thin to label
_MIN_SEGMENT_LABEL_H = 9  # and needs at least this many pixels of height for the text
_MULTI_KINDS = frozenset({"grouped", "stacked", "stacked100", "multiline", "dual"})
_KINDS = frozenset({"bar", "line", "area", "scatter", "pie"}) | _MULTI_KINDS

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


class Scale(NamedTuple):
    """Maps a value to a y pixel over the data range, with a zero baseline."""

    lo: float
    hi: float
    area: Area

    def y(self, value: float) -> int:
        span = self.hi - self.lo or 1.0
        return self.area.y1 - int(self.area.h * (value - self.lo) / span)

    @property
    def zero(self) -> int:
        """The y pixel of value 0 — the baseline bars grow from."""
        return self.y(0.0)


def _scale_for(rows: list[tuple[str, float]], area: Area) -> Scale:
    values = [value for _label, value in rows] or [0.0]
    hi = max(*values, 0.0) if len(values) > 1 else max(values[0], 0.0)
    lo = min(*values, 0.0) if len(values) > 1 else min(values[0], 0.0)
    if hi == lo:
        hi = lo + 1.0
    return Scale(lo, hi, area)


def dispatch_chart(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object] | None:
    if name != "chart":
        return None
    kind = str(arguments.get("kind") or "bar").lower()
    if kind not in _KINDS:
        return _error(
            "validation_failed", "kind must be bar, line, area, scatter, pie, grouped or stacked"
        )
    theme = theme_for(str(arguments.get("theme") or "ink"))
    if theme is None:
        return _error("validation_failed", "theme must be ink, slate, forest, ember or midnight")
    title = str(arguments.get("title") or kind)
    if kind in _MULTI_KINDS:
        multi = _multi(arguments)
        if multi is None:
            return _error(
                "validation_failed",
                "grouped and stacked charts need rows with a category key and one or more "
                "numeric series (give seriesKeys, or let every numeric column be a series)",
            )
        categories, series = multi
        if kind == "dual":
            requested = arguments.get("rightKeys") or arguments.get("right_keys")
            right = {str(k) for k in requested} if isinstance(requested, list) else set()
            png = render_dual(categories, series, right, theme=theme.name, title=title)
        else:
            png = render_multi(kind, categories, series, theme=theme.name, title=title)
        count = len(categories)
        plotted: dict[str, object] = {
            "categories": categories,
            "series": [{"name": name, "values": values} for name, values in series],
        }
    else:
        rows = _rows(arguments)
        if not rows:
            return _error(
                "validation_failed", "chart needs rows, or xKey and yKey over a list of objects"
            )
        png = render_chart(kind, rows, theme=theme.name, title=title)
        count = len(rows)
        plotted = {"rows": [{"label": label, "value": value} for label, value in rows]}
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
        "text": f"Drew a {kind} chart ({count} points, {theme.name}).{note}",
        "structured": {
            "presentation": {
                "kind": "chart",
                "chart": kind,
                "theme": theme.name,
                "title": title,
                "files": files,
                "truncated": False,
                **plotted,
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
    scale = _scale_for(rows, area)
    if kind == "pie":
        _pie(pixels, width, height, rows, chosen)
        _pie_legend(pixels, width, height, rows, chosen)
    else:
        _grid(pixels, width, height, scale, chosen)
        if kind == "scatter":
            _scatter(pixels, width, scale, rows, chosen)
        elif kind == "line":
            _line(pixels, width, scale, rows, chosen.ink)
            _point_labels(pixels, width, height, scale, rows, chosen)
        elif kind == "area":
            _area(pixels, width, height, scale, rows, chosen)
            _point_labels(pixels, width, height, scale, rows, chosen)
        else:
            _bars(pixels, width, height, scale, rows, chosen)
        _x_labels(pixels, width, height, area, rows, chosen)
    if title:
        _title(pixels, width, height, title, chosen)
    return _encode(pixels, width, height)


def render_multi(
    kind: str, categories: list[str], series: Series, *, theme: str = "ink", title: str = ""
) -> bytes:
    """Return a grouped or stacked bar chart PNG with a series legend."""
    chosen = theme_for(theme) or THEMES["ink"]
    width, height = _WIDTH, _HEIGHT
    pixels = bytearray(chosen.paper * (width * height))
    area = Area(_LEFT, _TOP, width - _RIGHT, height - _BOTTOM)
    if kind == "stacked100":
        scale = Scale(0.0, 100.0, area)
    elif kind == "stacked":
        totals = [
            sum(max(0.0, values[i]) for _name, values in series) for i in range(len(categories))
        ]
        scale = Scale(0.0, max(totals, default=1.0) or 1.0, area)
    else:
        flat = [value for _name, values in series for value in values] or [0.0]
        hi = max(*flat, 0.0) if len(flat) > 1 else max(flat[0], 0.0)
        lo = min(*flat, 0.0) if len(flat) > 1 else min(flat[0], 0.0)
        scale = Scale(lo, hi + 1.0 if hi == lo else hi, area)
    _grid(pixels, width, height, scale, chosen, percent=kind == "stacked100")
    if kind in {"stacked", "stacked100"}:
        _stacked_bars(
            pixels, width, height, scale, categories, series, chosen, percent=kind == "stacked100"
        )
    elif kind == "multiline":
        _multi_lines(pixels, width, height, scale, series, chosen)
    else:
        _grouped_bars(pixels, width, height, scale, categories, series, chosen)
    _x_labels(pixels, width, height, area, [(c, 0.0) for c in categories], chosen)
    _legend(pixels, width, height, series, chosen)
    if title:
        _title(pixels, width, height, title, chosen)
    return _encode(pixels, width, height)


def render_dual(
    categories: list[str],
    series: Series,
    right_names: set[str],
    *,
    theme: str = "ink",
    title: str = "",
) -> bytes:
    """Return a dual-axis chart: bars on the left axis, line(s) on the right axis."""
    chosen = theme_for(theme) or THEMES["ink"]
    width, height = _WIDTH, _HEIGHT
    pixels = bytearray(chosen.paper * (width * height))
    area = Area(_LEFT, _TOP, width - _RIGHT_DUAL, height - _BOTTOM)
    if not right_names and len(series) > 1:
        right_names = {series[-1][0]}  # by default the last series is the right-axis line
    left = [item for item in series if item[0] not in right_names]
    right = [item for item in series if item[0] in right_names]
    if not left:  # everything was assigned to the right; keep the first series as bars
        left, right = series[:1], series[1:]
    left_scale = _scale_for_values([v for _n, vals in left for v in vals], area)
    right_scale = _scale_for_values([v for _n, vals in right for v in vals], area)
    right_colour = chosen.accents[len(left) % len(chosen.accents)]
    _grid(pixels, width, height, left_scale, chosen)
    _grouped_bars(pixels, width, height, left_scale, categories, left, chosen)
    _right_axis(pixels, width, height, right_scale, right_colour)
    _dual_lines(pixels, width, height, right_scale, right, chosen, len(left))
    _x_labels(pixels, width, height, area, [(c, 0.0) for c in categories], chosen)
    legend = [*left, *[(f"{name} (R)", vals) for name, vals in right]]
    _legend(pixels, width, height, legend, chosen)
    if title:
        _title(pixels, width, height, title, chosen)
    return _encode(pixels, width, height)


def _scale_for_values(values: list[float], area: Area) -> Scale:
    vals = values or [0.0]
    hi = max(*vals, 0.0) if len(vals) > 1 else max(vals[0], 0.0)
    lo = min(*vals, 0.0) if len(vals) > 1 else min(vals[0], 0.0)
    return Scale(lo, hi + 1.0 if hi == lo else hi, area)


def _right_axis(pixels: bytearray, width: int, height: int, scale: Scale, colour: Colour) -> None:
    # The right axis, its ticks and numbers take the line's colour, so it is unmistakable which
    # scale the line is read against (and which numbers belong to the line, not the bars).
    area = scale.area
    for y in range(area.y0, area.y1 + 1):
        _dot(pixels, width, area.x1, y, colour)
    for tick in range(_TICKS + 1):
        value = scale.lo + (scale.hi - scale.lo) * tick / _TICKS
        yy = scale.y(value)
        pixfont.draw_text(pixels, width, height, area.x1 + 6, yy - 3, _fmt(value), colour)


def _dual_lines(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    scale: Scale,
    series: Series,
    theme: ChartTheme,
    offset: int,
) -> None:
    area = scale.area
    count = len(series[0][1]) if series else 0
    slot = area.w / max(1, count)
    xs = [area.x0 + int(slot * (i + 0.5)) for i in range(count)]  # align with bar group centres
    for si, (_name, values) in enumerate(series):
        colour = theme.accents[(offset + si) % len(theme.accents)]
        points = [(xs[i], scale.y(values[i])) for i in range(len(values))]
        for start, end in pairwise(points):
            _segment(pixels, width, start, end, colour)
        for i, (px, py) in enumerate(points):
            _fill(pixels, width, px - 2, px + 3, py - 2, py + 3, colour)
            text = _fmt(values[i])
            tx = px - pixfont.text_width(text) // 2
            ty = py - 11 if py - 11 >= area.y0 else py + 6
            pixfont.draw_text(pixels, width, height, tx, ty, text, colour)


def _encode(pixels: bytearray, width: int, height: int) -> bytes:
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


Series = list[tuple[str, list[float]]]


def _multi(arguments: dict[str, object]) -> tuple[list[str], Series] | None:
    """Parse wide-format rows into (categories, [(series name, values)]) for grouped/stacked."""
    raw = arguments.get("rows")
    rows = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    if not rows:
        return None
    x_key = str(arguments.get("xKey") or arguments.get("x_key") or "")
    requested = arguments.get("seriesKeys") or arguments.get("series_keys")
    keys: list[str] = []
    if isinstance(requested, list):
        keys = [str(k) for k in requested if str(k)]
    if not keys:
        label_keys = {x_key, "label", "x"} if x_key else {"label", "x"}
        for key, value in rows[0].items():
            if str(key) not in label_keys and _number(value) is not None:
                keys.append(str(key))
    keys = keys[:_MAX_SERIES]
    if not keys:
        return None
    rows = rows[:_MAX_CATEGORIES]
    categories = [
        str(row.get(x_key) or row.get("label") or row.get("x") or index)
        for index, row in enumerate(rows)
    ]
    series: Series = [(key, [_number(row.get(key)) or 0.0 for row in rows]) for key in keys]
    return categories, series


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
    """A short label for an axis tick or a bar value, abbreviating thousands/millions."""
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return _trim(value / 1_000_000) + "M"
    if magnitude >= 1_000:
        return _trim(value / 1_000) + "K"
    return _trim(value)


def _trim(value: float) -> str:
    """A number with at most one decimal and no trailing ``.0``."""
    rounded = round(value, 1)
    return str(int(rounded)) if rounded == int(rounded) else f"{rounded:.1f}"


def _title(pixels: bytearray, width: int, height: int, title: str, theme: ChartTheme) -> None:
    text = title.strip()
    while text and pixfont.text_width(text, scale=2) > width - 16:
        text = text[:-1]
    start = max(4, (width - pixfont.text_width(text, scale=2)) // 2)
    pixfont.draw_text(pixels, width, height, start, 10, text, theme.ink, scale=2)


def _grid(
    pixels: bytearray,
    width: int,
    height: int,
    scale: Scale,
    theme: ChartTheme,
    *,
    percent: bool = False,
) -> None:
    area = scale.area
    for tick in range(_TICKS + 1):
        frac = tick / _TICKS
        value = scale.lo + (scale.hi - scale.lo) * frac
        yy = scale.y(value)
        for x in range(area.x0, area.x1):
            _dot(pixels, width, x, yy, theme.grid)
        label = f"{_fmt(value)}%" if percent else _fmt(value)
        label_w = pixfont.text_width(label)
        pixfont.draw_text(pixels, width, height, area.x0 - 6 - label_w, yy - 3, label, theme.ink)
    for y in range(area.y0, area.y1 + 1):
        _dot(pixels, width, area.x0, y, theme.ink)
    if scale.lo < 0 < scale.hi:  # emphasise the zero baseline when values cross it
        for x in range(area.x0, area.x1):
            _dot(pixels, width, x, scale.zero, theme.ink)


def _bars(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    scale: Scale,
    rows: list[tuple[str, float]],
    theme: ChartTheme,
) -> None:
    area = scale.area
    slot = area.w / max(1, len(rows))
    bar_w = max(3, int(slot * 0.6))
    base = scale.zero
    for index, (_label, value) in enumerate(rows):
        center = area.x0 + int(slot * (index + 0.5))
        left = center - bar_w // 2
        colour = theme.accents[index % len(theme.accents)]
        tip = scale.y(value)
        top, bottom = (tip, base) if value >= 0 else (base, tip)
        for y in range(top, bottom):
            for x in range(left, left + bar_w):
                _dot(pixels, width, x, y, colour)
        label = _fmt(value)
        label_x = center - pixfont.text_width(label) // 2
        label_y = top - 9 if value >= 0 and top - 9 >= area.y0 else bottom + 2
        pixfont.draw_text(pixels, width, height, label_x, label_y, label, theme.ink)


def _fill(  # noqa: PLR0917
    pixels: bytearray, width: int, left: int, right: int, top: int, bottom: int, colour: Colour
) -> None:
    for y in range(top, bottom):
        for x in range(left, right):
            _dot(pixels, width, x, y, colour)


def _grouped_bars(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    scale: Scale,
    categories: list[str],
    series: Series,
    theme: ChartTheme,
) -> None:
    area = scale.area
    slot = area.w / max(1, len(categories))
    group_w = slot * 0.8
    bar_w = max(2, int(group_w / max(1, len(series))))
    base = scale.zero
    label = bar_w >= _MIN_LABEL_BAR_W and len(categories) * len(series) <= _MAX_LABELLED_BARS
    for ci in range(len(categories)):
        group_left = area.x0 + slot * ci + (slot - group_w) / 2
        for si, (_name, values) in enumerate(series):
            value = values[ci]
            colour = theme.accents[si % len(theme.accents)]
            left = int(group_left + si * bar_w)
            tip = scale.y(value)
            top, bottom = (tip, base) if value >= 0 else (base, tip)
            _fill(pixels, width, left, left + max(2, bar_w - 1), top, bottom, colour)
            if label:
                text = _fmt(value)
                tx = left + (bar_w - pixfont.text_width(text)) // 2
                pixfont.draw_text(pixels, width, height, tx, top - 9, text, theme.ink)


def _stacked_bars(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    scale: Scale,
    categories: list[str],
    series: Series,
    theme: ChartTheme,
    *,
    percent: bool = False,
) -> None:
    area = scale.area
    slot = area.w / max(1, len(categories))
    bar_w = max(4, int(slot * 0.55))
    for ci in range(len(categories)):
        center = area.x0 + int(slot * (ci + 0.5))
        left = center - bar_w // 2
        raw_total = sum(max(0.0, values[ci]) for _name, values in series)
        factor = (100.0 / raw_total) if percent and raw_total else 1.0
        cumulative = 0.0
        for si, (_name, values) in enumerate(series):
            value = max(0.0, values[ci]) * factor
            colour = theme.accents[si % len(theme.accents)]
            lower, upper = scale.y(cumulative + value), scale.y(cumulative)
            _fill(pixels, width, left, left + bar_w, lower, upper, colour)
            if (
                percent
                and value >= _MIN_SEGMENT_LABEL_PCT
                and upper - lower >= _MIN_SEGMENT_LABEL_H
            ):
                seg = f"{round(value)}%"
                sx = center - pixfont.text_width(seg) // 2
                pixfont.draw_text(pixels, width, height, sx, lower + 2, seg, theme.paper)
            cumulative += value
        total = "100%" if percent else _fmt(cumulative)
        tx = center - pixfont.text_width(total) // 2
        pixfont.draw_text(pixels, width, height, tx, scale.y(cumulative) - 9, total, theme.ink)


def _legend(pixels: bytearray, width: int, height: int, series: Series, theme: ChartTheme) -> None:
    items = [
        (name[:12], theme.accents[i % len(theme.accents)]) for i, (name, _v) in enumerate(series)
    ]
    gap, square = 14, 8
    widths = [square + 3 + pixfont.text_width(name) + gap for name, _c in items]
    total = sum(widths) - gap if widths else 0
    x = max(4, (width - total) // 2)
    y = _TOP - 13
    for (name, colour), item_w in zip(items, widths, strict=True):
        _fill(pixels, width, x, x + square, y, y + square, colour)
        pixfont.draw_text(pixels, width, height, x + square + 3, y, name.upper(), theme.ink)
        x += item_w


def _multi_lines(  # noqa: PLR0917
    pixels: bytearray, width: int, height: int, scale: Scale, series: Series, theme: ChartTheme
) -> None:
    area = scale.area
    count = len(series[0][1]) if series else 0
    xs = [
        area.x0 + (int(area.w * i / (count - 1)) if count > 1 else area.w // 2)
        for i in range(count)
    ]
    # Few enough points to label each value — the surest way to read which line is higher.
    label = count * len(series) <= _MAX_LABELLED_BARS
    for si, (_name, values) in enumerate(series):
        colour = theme.accents[si % len(theme.accents)]
        points = [(xs[i], scale.y(values[i])) for i in range(len(values))]
        for start, end in pairwise(points):
            _segment(pixels, width, start, end, colour)
        for i, (px, py) in enumerate(points):  # a marker at each vertex, easy to trace
            _fill(pixels, width, px - 2, px + 3, py - 2, py + 3, colour)
            if label:
                text = _fmt(values[i])
                tx = px - pixfont.text_width(text) // 2
                ty = py - 11 if py - 11 >= area.y0 else py + 6
                pixfont.draw_text(pixels, width, height, tx, ty, text, colour)


def _line(
    pixels: bytearray,
    width: int,
    scale: Scale,
    rows: list[tuple[str, float]],
    colour: Colour,
) -> None:
    for start, end in pairwise(_points(scale, rows)):
        _segment(pixels, width, start, end, colour)


def _area(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    scale: Scale,
    rows: list[tuple[str, float]],
    theme: ChartTheme,
) -> None:
    points = _points(scale, rows)
    colour = theme.accents[0]
    base = scale.zero
    if len(points) == 1:
        _bars(pixels, width, height, scale, rows, theme)
        return
    for start, end in pairwise(points):
        span = max(1, end[0] - start[0])
        for step in range(span + 1):
            y = start[1] + (end[1] - start[1]) * step // span
            x = start[0] + (end[0] - start[0]) * step // span
            lo_y, hi_y = (y, base) if y <= base else (base, y)
            for yy in range(lo_y, hi_y):
                _dot(pixels, width, x, yy, colour)
    _line(pixels, width, scale, rows, theme.ink)


def _scatter(
    pixels: bytearray,
    width: int,
    scale: Scale,
    rows: list[tuple[str, float]],
    theme: ChartTheme,
) -> None:
    for x, y in _points(scale, rows):
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                _dot(pixels, width, x + dx, y + dy, theme.ink)


def _point_labels(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    scale: Scale,
    rows: list[tuple[str, float]],
    theme: ChartTheme,
) -> None:
    if len(rows) > _MAX_POINT_LABELS:
        return
    area = scale.area
    for (x, y), (_label, value) in zip(_points(scale, rows), rows, strict=True):
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


def _points(scale: Scale, rows: list[tuple[str, float]]) -> list[tuple[int, int]]:
    area = scale.area
    span = max(1, len(rows) - 1)
    points: list[tuple[int, int]] = []
    for index, (_label, value) in enumerate(rows):
        x = area.x0 + int(area.w * index / span) if len(rows) > 1 else area.x0 + area.w // 2
        points.append((x, scale.y(value)))
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
