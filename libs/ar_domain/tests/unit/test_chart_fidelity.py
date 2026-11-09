"""The chart renderer labels its output: title, axis ticks, categories and values.

These guard the fidelity fix — before it, charts were bars with no text, which no
reader (person or vision model) could interpret.
"""

from __future__ import annotations

import struct
import zlib

from ar_domain.analytics import pixfont
from ar_domain.analytics.themes import THEMES
from ar_domain.tools.charts import render_chart

_INK = THEMES["ink"].ink
_WIDTH = 640
_HEIGHT = 360


def _decode(png: bytes) -> list[list[tuple[int, int, int]]]:
    """Decode our own PNG (truecolour, per-row filter 0) back to rows of RGB pixels."""
    idat = b""
    index = 8
    while index < len(png):
        length = struct.unpack(">I", png[index : index + 4])[0]
        tag = png[index + 4 : index + 8]
        if tag == b"IDAT":
            idat += png[index + 8 : index + 8 + length]
        index += 12 + length
    raw = zlib.decompress(idat)
    stride = _WIDTH * 3 + 1
    rows: list[list[tuple[int, int, int]]] = []
    for y in range(_HEIGHT):
        line = raw[y * stride + 1 : (y + 1) * stride]  # drop the leading filter byte
        rows.append([(line[x * 3], line[x * 3 + 1], line[x * 3 + 2]) for x in range(_WIDTH)])
    return rows


def _band_has(rows: list[list[tuple[int, int, int]]], y0: int, y1: int, colour: tuple) -> bool:
    return any(colour in rows[y] for y in range(y0, y1))


def test_pixfont_draws_pixels_and_measures_width() -> None:
    buffer = bytearray(b"\x00\x00\x00" * (20 * 20))
    drawn = pixfont.draw_text(buffer, 20, 20, 1, 1, "7", (255, 0, 0))
    assert drawn == pixfont.text_width("7")
    # The top row of the "7" glyph is solid, so a red pixel lands near the top-left.
    assert any(
        buffer[(y * 20 + x) * 3 : (y * 20 + x) * 3 + 3] == b"\xff\x00\x00"
        for y in range(1, 4)
        for x in range(1, 6)
    )


def test_bar_chart_draws_title_categories_and_values() -> None:
    rows = render_chart(
        "bar",
        [("Q1", 20.0), ("Q2", 95.0), ("Q3", 35.0), ("Q4", 50.0)],
        theme="ink",
        title="Quarterly Revenue",
    )
    pixels = _decode(rows)
    # Title band near the top carries ink text.
    assert _band_has(pixels, 8, 26, _INK), "no title text drawn"
    # Category labels sit below the plot baseline.
    assert _band_has(pixels, _HEIGHT - 40, _HEIGHT - 8, _INK), "no category labels drawn"
    # Value labels and y-axis ticks put ink inside the plot/left margin.
    assert sum(row.count(_INK) for row in pixels) > 200, "too little text for labelled axes"


def test_title_adds_ink_pixels() -> None:
    data = [("A", 3.0), ("B", 6.0)]
    with_title = _decode(render_chart("bar", data, theme="ink", title="Report"))
    without = _decode(render_chart("bar", data, theme="ink", title=""))
    top_with = sum(with_title[y].count(_INK) for y in range(8, 26))
    top_without = sum(without[y].count(_INK) for y in range(8, 26))
    assert top_with > top_without
