"""A tiny 5x7 bitmap font for labelling charts without a font dependency.

The chart renderer is pure Python (no Pillow, no matplotlib), so text is drawn
pixel by pixel from this table. Letters are drawn uppercased; digits, space and
a few symbols used in numbers and labels are included. Unknown characters render
as a blank space.
"""

from __future__ import annotations

# Each glyph is 7 rows of 5 columns; "X" is an inked pixel. Letters are uppercase.
_GLYPHS: dict[str, tuple[str, ...]] = {
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    "0": (".XXX.", "X...X", "X..XX", "X.X.X", "XX..X", "X...X", ".XXX."),
    "1": ("..X..", ".XX..", "..X..", "..X..", "..X..", "..X..", ".XXX."),
    "2": (".XXX.", "X...X", "....X", "...X.", "..X..", ".X...", "XXXXX"),
    "3": ("XXXXX", "...X.", "..X..", "...X.", "....X", "X...X", ".XXX."),
    "4": ("...X.", "..XX.", ".X.X.", "X..X.", "XXXXX", "...X.", "...X."),
    "5": ("XXXXX", "X....", "XXXX.", "....X", "....X", "X...X", ".XXX."),
    "6": ("..XX.", ".X...", "X....", "XXXX.", "X...X", "X...X", ".XXX."),
    "7": ("XXXXX", "....X", "...X.", "..X..", ".X...", ".X...", ".X..."),
    "8": (".XXX.", "X...X", "X...X", ".XXX.", "X...X", "X...X", ".XXX."),
    "9": (".XXX.", "X...X", "X...X", ".XXXX", "....X", "...X.", ".XX.."),
    "A": (".XXX.", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"),
    "B": ("XXXX.", "X...X", "X...X", "XXXX.", "X...X", "X...X", "XXXX."),
    "C": (".XXX.", "X...X", "X....", "X....", "X....", "X...X", ".XXX."),
    "D": ("XXXX.", "X...X", "X...X", "X...X", "X...X", "X...X", "XXXX."),
    "E": ("XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "XXXXX"),
    "F": ("XXXXX", "X....", "X....", "XXXX.", "X....", "X....", "X...."),
    "G": (".XXX.", "X...X", "X....", "X.XXX", "X...X", "X...X", ".XXXX"),
    "H": ("X...X", "X...X", "X...X", "XXXXX", "X...X", "X...X", "X...X"),
    "I": (".XXX.", "..X..", "..X..", "..X..", "..X..", "..X..", ".XXX."),
    "J": ("..XXX", "...X.", "...X.", "...X.", "...X.", "X..X.", ".XX.."),
    "K": ("X...X", "X..X.", "X.X..", "XX...", "X.X..", "X..X.", "X...X"),
    "L": ("X....", "X....", "X....", "X....", "X....", "X....", "XXXXX"),
    "M": ("X...X", "XX.XX", "X.X.X", "X.X.X", "X...X", "X...X", "X...X"),
    "N": ("X...X", "XX..X", "X.X.X", "X.X.X", "X..XX", "X...X", "X...X"),
    "O": (".XXX.", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."),
    "P": ("XXXX.", "X...X", "X...X", "XXXX.", "X....", "X....", "X...."),
    "Q": (".XXX.", "X...X", "X...X", "X...X", "X.X.X", "X..XX", ".XXXX"),
    "R": ("XXXX.", "X...X", "X...X", "XXXX.", "X.X..", "X..X.", "X...X"),
    "S": (".XXXX", "X....", "X....", ".XXX.", "....X", "....X", "XXXX."),
    "T": ("XXXXX", "..X..", "..X..", "..X..", "..X..", "..X..", "..X.."),
    "U": ("X...X", "X...X", "X...X", "X...X", "X...X", "X...X", ".XXX."),
    "V": ("X...X", "X...X", "X...X", "X...X", "X...X", ".X.X.", "..X.."),
    "W": ("X...X", "X...X", "X...X", "X.X.X", "X.X.X", "XX.XX", "X...X"),
    "X": ("X...X", "X...X", ".X.X.", "..X..", ".X.X.", "X...X", "X...X"),
    "Y": ("X...X", "X...X", ".X.X.", "..X..", "..X..", "..X..", "..X.."),
    "Z": ("XXXXX", "....X", "...X.", "..X..", ".X...", "X....", "XXXXX"),
    ".": (".....", ".....", ".....", ".....", ".....", ".XX..", ".XX.."),
    ",": (".....", ".....", ".....", ".....", ".XX..", ".XX..", ".X..."),
    "-": (".....", ".....", ".....", "XXXXX", ".....", ".....", "....."),
    "+": (".....", "..X..", "..X..", "XXXXX", "..X..", "..X..", "....."),
    ":": (".....", ".XX..", ".XX..", ".....", ".XX..", ".XX..", "....."),
    "/": ("....X", "....X", "...X.", "..X..", ".X...", "X....", "X...."),
    "%": ("XX..X", "XX.X.", "...X.", "..X..", ".X...", ".X.XX", "X..XX"),
    "(": ("..XX.", ".X...", "X....", "X....", "X....", ".X...", "..XX."),
    ")": (".XX..", "...X.", "....X", "....X", "....X", "...X.", ".XX.."),
    "$": ("..X..", ".XXXX", "X.X..", ".XXX.", "..X.X", "XXXX.", "..X.."),
}

GLYPH_W = 5
GLYPH_H = 7
_BLANK = _GLYPHS[" "]

Colour = tuple[int, int, int]


def text_width(text: str, *, scale: int = 1, spacing: int = 1) -> int:
    """Pixel width of ``text`` at ``scale`` with ``spacing`` columns between glyphs."""
    if not text:
        return 0
    return (len(text) * (GLYPH_W + spacing) - spacing) * scale


def draw_text(  # noqa: PLR0917
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    text: str,
    colour: Colour,
    *,
    scale: int = 1,
    spacing: int = 1,
) -> int:
    """Draw ``text`` with its top-left at ``(x, y)``; return the width drawn."""
    cursor = x
    for char in text:
        glyph = _GLYPHS.get(char) or _GLYPHS.get(char.upper()) or _BLANK
        for row in range(GLYPH_H):
            line = glyph[row]
            for col in range(GLYPH_W):
                if line[col] != "X":
                    continue
                for sy in range(scale):
                    for sx in range(scale):
                        _plot(
                            pixels,
                            width,
                            height,
                            cursor + col * scale + sx,
                            y + row * scale + sy,
                            colour,
                        )
        cursor += (GLYPH_W + spacing) * scale
    # The visual width excludes the trailing inter-glyph gap, matching text_width().
    return max(0, cursor - x - spacing * scale) if text else 0


def _plot(  # noqa: PLR0917
    pixels: bytearray, width: int, height: int, x: int, y: int, colour: Colour
) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    offset = (y * width + x) * 3
    pixels[offset : offset + 3] = bytes(colour)
