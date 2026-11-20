"""PPTX writer. One 16:9 deck: a title slide, then the sections in order.

Layout uses fixed counts, not font measurement, so the same input always gives
the same slides:

- Slide 1 carries the title, the subtitle and the author.
- Each section starts a slide with its heading as the slide title. The heading
  level is not shown: every section is one slide deep.
- Body text is 18 pt. A line holds 90 characters and a slide holds 14 lines.
  Paragraphs come first, then bullets. Text that does not fit moves to a next
  slide titled "<heading> (continued)". One paragraph longer than a slide is
  cut at a word boundary and carries on there too.
- Table text is 14 pt in equal-width columns. A row is as tall as its longest
  cell, and a cell shows at most six lines; longer text ends with "...". A
  one-line row is 0.35 in, so a slide holds sixteen of them, header included.
  A long table carries on over more slides and repeats its header.
- A section with text and a table puts both on one slide when both fit in the
  body area. Otherwise the text slides come first and the table follows on
  slides titled "<heading> (table)" and then "<heading> (table, continued)".
- A deck is at most ``max_slides()`` slides.

``package`` and ``picture_slide`` are shared with the chart tool, which writes
its one-slide deck through the same master, layouts and theme.
"""

from __future__ import annotations

import struct
import textwrap
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ar_domain.documents.create.spec import FONT, MUTED, RULE, SECOND, CreateError, max_slides
from ar_domain.documents.create.xmlpack import PRODUCER, pack, xml_escape

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from ar_domain.documents.create.spec import DocumentSpec, Section, Table, Theme

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC = "http://purl.org/dc/elements/1.1/"
_APP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_TABLE = "http://schemas.openxmlformats.org/drawingml/2006/table"
_PML = "application/vnd.openxmlformats-officedocument.presentationml"
_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
_NS = f'xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}"'
_IMAGES = {"png": "image/png"}

# Lengths are English Metric Units: 914400 to the inch, 12700 to the point.
_SLIDE_W = 12_192_000
_SLIDE_H = 6_858_000
_MARGIN = 457_200
_CONTENT_W = _SLIDE_W - 2 * _MARGIN
_TITLE_TOP = 320_040
_TITLE_H = 868_680
_RULE_TOP = 1_188_720
_RULE_H = 27_432
_BODY_TOP = 1_280_160
_BODY_H = 5_120_640
_LINE_H = 365_760
_GAP = 137_160
_COVER_TITLE_TOP = 1_828_800
_COVER_TITLE_H = 1_371_600
_COVER_RULE_TOP = 3_246_120
_COVER_RULE_W = 1_828_800
_COVER_TEXT_TOP = 3_337_560
_COVER_TEXT_H = 1_463_040
_SIDE_W = 4_023_360
_SIDE_GAP = 182_880

LINES_PER_SLIDE = 14
CHARS_PER_LINE = 90
CELL_LINES = 6
_BODY_SIZE = 1800
_SMALL_SIZE = 1400
_ROW_PAD = 91_440
_ROW_LINE = 228_600
_CAPTION_H = 320_040
_CELL_INSET_PT = 14.4
_CELL_CHAR_PT = 7.5


@dataclass(frozen=True)
class Slide:
    """One finished slide. ``layout`` is 1 for the title layout, 2 for title and content."""

    xml: str
    layout: int = 2
    images: tuple[str, ...] = ()


@dataclass(frozen=True)
class _Row:
    cells: tuple[str, ...]
    numeric: tuple[bool, ...]
    height: int


@dataclass(frozen=True)
class _Grid:
    caption: str
    header: _Row
    rows: tuple[_Row, ...]

    @property
    def height(self) -> int:
        caption = _CAPTION_H if self.caption else 0
        return caption + self.header.height + sum(row.height for row in self.rows)


def render_pptx(spec: DocumentSpec) -> bytes:
    """Return the deck for one parsed document. See the module text for the layout rules."""
    slides = [_cover(spec)]
    for section in spec.sections:
        slides.extend(_section(section, spec.theme))
        if len(slides) > max_slides():
            raise CreateError(f"The presentation is over {max_slides()} slides. Split it.")
    return package(
        title=spec.title,
        subtitle=spec.subtitle,
        author=spec.author,
        theme=spec.theme,
        slides=slides,
    )


def package(
    *,
    title: str,
    subtitle: str,
    author: str,
    theme: Theme,
    slides: Sequence[Slide],
    media: Mapping[str, bytes] | None = None,
) -> bytes:
    """Wrap slides in a complete package: master, two layouts, theme and properties.

    ``media`` maps a file name under ``ppt/media`` to its bytes. A slide names the
    images it shows; its relationship ids for them start at ``rId2``.
    """
    images = dict(media or {})
    parts: dict[str, str | bytes] = {
        "[Content_Types].xml": _content_types(len(slides), images),
        "_rels/.rels": _root_rels(),
        "docProps/core.xml": _core(title, subtitle, author),
        "docProps/app.xml": _app(len(slides)),
        "ppt/presentation.xml": _presentation(len(slides)),
        "ppt/_rels/presentation.xml.rels": _presentation_rels(len(slides)),
        "ppt/theme/theme1.xml": _theme(theme),
        "ppt/slideMasters/slideMaster1.xml": _master(theme),
        "ppt/slideMasters/_rels/slideMaster1.xml.rels": _master_rels(),
        "ppt/slideLayouts/slideLayout1.xml": _cover_layout(),
        "ppt/slideLayouts/slideLayout2.xml": _content_layout(),
        "ppt/slideLayouts/_rels/slideLayout1.xml.rels": _layout_rels(),
        "ppt/slideLayouts/_rels/slideLayout2.xml.rels": _layout_rels(),
    }
    for number, slide in enumerate(slides, start=1):
        parts[f"ppt/slides/slide{number}.xml"] = slide.xml
        parts[f"ppt/slides/_rels/slide{number}.xml.rels"] = _slide_rels(slide)
    for name, data in images.items():
        parts[f"ppt/media/{name}"] = data
    return pack(parts)


def picture_slide(
    *, title: str, lines: Sequence[str], image: str, png: bytes, theme: Theme
) -> Slide:
    """A slide with text on the left and one PNG, kept in proportion, on the right."""
    left = _MARGIN + _SIDE_W + _SIDE_GAP
    room_w = _SLIDE_W - _MARGIN - left
    wide, high = _png_size(png)
    scale = min(room_w / wide, _BODY_H / high)
    width = int(wide * scale)
    height = int(high * scale)
    box = (left + (room_w - width) // 2, _BODY_TOP + (_BODY_H - height) // 2, width, height)
    text = "".join(_para(_run(line, _BODY_SIZE)) for line in lines)
    picture = (
        f'<p:pic><p:nvPicPr><p:cNvPr id="4" name="{xml_escape(image)}"/>'
        '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        '<p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr>{_xfrm(box)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )
    shapes = (
        _heading(title, theme)
        + _shape(3, "Text", 'idx="1"', (_MARGIN, _BODY_TOP, _SIDE_W, _BODY_H), text)
        + picture
    )
    return Slide(xml=_slide(shapes), layout=2, images=(image,))


def _cover(spec: DocumentSpec) -> Slide:
    title = _para(_run(spec.title, spec.theme.title_half_points * 100, bold=True, colour="accent1"))
    under = ""
    if spec.subtitle:
        under += _para(_run(spec.subtitle, 2000, italic=True, colour="tx2"))
    under += _para(_run(spec.author, _SMALL_SIZE, colour="tx2"))
    shapes = _shape(
        2,
        "Title",
        'type="ctrTitle"',
        (_MARGIN, _COVER_TITLE_TOP, _CONTENT_W, _COVER_TITLE_H),
        title,
        anchor="b",
    ) + _shape(
        3,
        "Subtitle",
        'type="subTitle" idx="1"',
        (_MARGIN, _COVER_TEXT_TOP, _CONTENT_W, _COVER_TEXT_H),
        under,
    )
    return Slide(xml=_slide(shapes), layout=1)


def _section(section: Section, theme: Theme) -> list[Slide]:
    pages = _text_pages(section)
    if section.table is None:
        return [
            _content(_numbered(section.heading, "", index), theme, page, None)
            for index, page in enumerate(pages or [[]])
        ]
    caption = section.table.caption if section.table.caption != section.heading else ""
    grids = _grids(section.table, caption)
    if not pages:
        return [
            _content(_numbered(section.heading, "", index), theme, [], grid)
            for index, grid in enumerate(grids)
        ]
    used = _text_height(pages[0]) + _GAP + grids[0].height
    if len(pages) == 1 and len(grids) == 1 and used <= _BODY_H:
        return [_content(section.heading, theme, pages[0], grids[0])]
    slides = [
        _content(_numbered(section.heading, "", index), theme, page, None)
        for index, page in enumerate(pages)
    ]
    slides.extend(
        _content(_numbered(section.heading, "table", index), theme, [], grid)
        for index, grid in enumerate(grids)
    )
    return slides


def _numbered(heading: str, kind: str, index: int) -> str:
    """The slide title: the heading, with a note on every slide after the first of its kind."""
    notes = [kind] if kind else []
    if index:
        notes.append("continued")
    return f"{heading} ({', '.join(notes)})" if notes else heading


def _text_pages(section: Section) -> list[list[tuple[bool, str, int]]]:
    """Split paragraphs and bullets into slides of ``LINES_PER_SLIDE`` lines.

    Each item is (is a bullet, text, lines it takes).
    """
    items: list[tuple[bool, str, int]] = []
    for bullet, texts in ((False, section.paragraphs), (True, section.bullets)):
        for text in texts:
            lines = textwrap.wrap(text, CHARS_PER_LINE) or [""]
            for start in range(0, len(lines), LINES_PER_SLIDE):
                piece = lines[start : start + LINES_PER_SLIDE]
                items.append((bullet, " ".join(piece), len(piece)))
    pages: list[list[tuple[bool, str, int]]] = []
    used = LINES_PER_SLIDE
    for item in items:
        if used + item[2] > LINES_PER_SLIDE:
            pages.append([])
            used = 0
        pages[-1].append(item)
        used += item[2]
    return pages


def _text_height(page: list[tuple[bool, str, int]]) -> int:
    return sum(item[2] for item in page) * _LINE_H


def _grids(table: Table, caption: str) -> list[_Grid]:
    """Split a table into slides. Every slide repeats the header and has at least one row."""
    count = max(1, len(table.columns))
    points = _CONTENT_W / count / 12_700 - _CELL_INSET_PT
    width = max(1, int(points / _CELL_CHAR_PT))
    header = _row(table.columns, (False,) * count, width)
    rows = [
        _row(
            tuple(cell.text for cell in row),
            tuple(cell.number is not None for cell in row),
            width,
        )
        for row in table.rows
    ]
    room = _BODY_H - header.height - (_CAPTION_H if caption else 0)
    grids: list[_Grid] = []
    current: list[_Row] = []
    used = 0
    for row in rows:
        if current and used + row.height > room:
            grids.append(_Grid(caption, header, tuple(current)))
            current = []
            used = 0
        current.append(row)
        used += row.height
    grids.append(_Grid(caption, header, tuple(current)))
    return grids


def _row(texts: tuple[str, ...], numeric: tuple[bool, ...], width: int) -> _Row:
    cells: list[str] = []
    tallest = 1
    for text in texts:
        lines = textwrap.wrap(text, width) or [""]
        clipped = len(lines) > CELL_LINES
        if clipped:
            lines = lines[:CELL_LINES]
            lines[-1] = lines[-1][: max(0, width - 3)] + "..."
        tallest = max(tallest, len(lines))
        cells.append(" ".join(lines) if clipped else text)
    return _Row(tuple(cells), numeric, _ROW_PAD + tallest * _ROW_LINE)


def _content(
    title: str, theme: Theme, page: list[tuple[bool, str, int]], grid: _Grid | None
) -> Slide:
    text = "".join(_para(_run(item[1], _BODY_SIZE), bullet=item[0]) for item in page)
    height = _BODY_H if grid is None else _text_height(page)
    shapes = _heading(title, theme)
    if page or grid is None:
        box = (_MARGIN, _BODY_TOP, _CONTENT_W, height)
        shapes += _shape(3, "Text", 'idx="1"', box, text)
    if grid is not None:
        top = _BODY_TOP + (height + _GAP if page else 0)
        if grid.caption:
            caption = _para(_run(grid.caption, _SMALL_SIZE, italic=True, colour="tx2"))
            shapes += _shape(4, "Caption", "", (_MARGIN, top, _CONTENT_W, _CAPTION_H), caption)
            top += _CAPTION_H
        shapes += _frame(grid, top)
    return Slide(xml=_slide(shapes), layout=2)


def _heading(title: str, theme: Theme) -> str:
    run = _run(title, theme.heading_half_points * 100, bold=True, colour="accent1")
    box = (_MARGIN, _TITLE_TOP, _CONTENT_W, _TITLE_H)
    return _shape(2, "Title", 'type="title"', box, _para(run), anchor="b")


def _frame(grid: _Grid, top: int) -> str:
    count = len(grid.header.cells)
    width = _CONTENT_W // count
    columns = "".join(f'<a:gridCol w="{width}"/>' for _ in range(count))
    rows = _table_row(grid.header, header=True) + "".join(
        _table_row(row, header=False) for row in grid.rows
    )
    height = grid.header.height + sum(row.height for row in grid.rows)
    return (
        '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="5" name="Table"/>'
        '<p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr>'
        "<p:nvPr/></p:nvGraphicFramePr>"
        f'<p:xfrm><a:off x="{_MARGIN}" y="{top}"/><a:ext cx="{width * count}" cy="{height}"/>'
        f'</p:xfrm><a:graphic><a:graphicData uri="{_TABLE}">'
        f'<a:tbl><a:tblPr firstRow="1"/><a:tblGrid>{columns}</a:tblGrid>{rows}</a:tbl>'
        "</a:graphicData></a:graphic></p:graphicFrame>"
    )


def _table_row(row: _Row, *, header: bool) -> str:
    edges = "".join(
        f'<a:{edge} w="6350"><a:solidFill><a:schemeClr val="bg2"/></a:solidFill></a:{edge}>'
        for edge in ("lnL", "lnR", "lnT", "lnB")
    )
    fill = "accent1" if header else "bg1"
    cells = []
    for text, numeric in zip(row.cells, row.numeric, strict=True):
        run = _run(text, _SMALL_SIZE, bold=header, colour="bg1" if header else "tx1")
        align = '<a:pPr algn="r"/>' if numeric else ""
        cells.append(
            f"<a:tc><a:txBody><a:bodyPr/><a:lstStyle/><a:p>{align}{run}</a:p></a:txBody>"
            f'<a:tcPr anchor="ctr">{edges}'
            f'<a:solidFill><a:schemeClr val="{fill}"/></a:solidFill></a:tcPr></a:tc>'
        )
    return f'<a:tr h="{row.height}">{"".join(cells)}</a:tr>'


def _slide(shapes: str) -> str:
    return (
        f"{_HEAD}<p:sld {_NS}><p:cSld>{_tree(shapes)}</p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


def _tree(shapes: str) -> str:
    return (
        "<p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        f"{shapes}</p:spTree>"
    )


def _shape(  # noqa: PLR0917
    number: int,
    name: str,
    placeholder: str,
    box: tuple[int, int, int, int],
    paragraphs: str,
    anchor: str = "t",
) -> str:
    """A text shape. With no placeholder it is a plain text box."""
    if placeholder:
        kind = (
            f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph {placeholder}/></p:nvPr>'
        )
        geometry = ""
    else:
        kind = '<p:cNvSpPr txBox="1"/><p:nvPr/>'
        geometry = '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/>'
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{number}" name="{name}"/>{kind}</p:nvSpPr>'
        f"<p:spPr>{_xfrm(box)}{geometry}</p:spPr>"
        f'<p:txBody><a:bodyPr wrap="square" anchor="{anchor}"><a:normAutofit/></a:bodyPr>'
        f"<a:lstStyle/>{paragraphs or '<a:p/>'}</p:txBody></p:sp>"
    )


def _bar(number: int, box: tuple[int, int, int, int]) -> str:
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{number}" name="Rule"/><p:cNvSpPr/>'
        '<p:nvPr userDrawn="1"/></p:nvSpPr>'
        f'<p:spPr>{_xfrm(box)}<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        '<a:solidFill><a:schemeClr val="accent1"/></a:solidFill>'
        "<a:ln><a:noFill/></a:ln></p:spPr></p:sp>"
    )


def _xfrm(box: tuple[int, int, int, int]) -> str:
    left, top, width, height = box
    return f'<a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>'


def _para(run: str, *, bullet: bool = False) -> str:
    if bullet:
        properties = (
            '<a:pPr marL="342900" indent="-342900"><a:buFontTx/><a:buChar char="&#8226;"/></a:pPr>'
        )
    else:
        properties = '<a:pPr marL="0" indent="0"><a:buNone/></a:pPr>'
    return f"<a:p>{properties}{run}</a:p>"


def _run(
    text: str, size: int, *, bold: bool = False, italic: bool = False, colour: str = "tx1"
) -> str:
    style = f' sz="{size}"' + (' b="1"' if bold else "") + (' i="1"' if italic else "")
    return (
        f'<a:r><a:rPr{style}><a:solidFill><a:schemeClr val="{colour}"/></a:solidFill></a:rPr>'
        f"<a:t>{_text(text)}</a:t></a:r>"
    )


def _text(value: str) -> str:
    return xml_escape("".join(char for char in value if char >= " " or char == "\t"))


def _png_size(data: bytes) -> tuple[int, int]:
    """Width and height from the PNG header. Anything else is taken as 16:9."""
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        wide, high = struct.unpack(">II", data[16:24])
        if wide and high:
            return int(wide), int(high)
    return 16, 9


def _master(theme: Theme) -> str:
    heading = theme.heading_half_points * 100
    title = _shape(2, "Title", 'type="title"', (_MARGIN, _TITLE_TOP, _CONTENT_W, _TITLE_H), "", "b")
    body = _shape(3, "Text", 'type="body" idx="1"', (_MARGIN, _BODY_TOP, _CONTENT_W, _BODY_H), "")
    colours = " ".join(f'accent{index}="accent{index}"' for index in range(1, 7))
    return (
        f"{_HEAD}<p:sldMaster {_NS}><p:cSld>"
        '<p:bg><p:bgRef idx="1001"><a:schemeClr val="bg1"/></p:bgRef></p:bg>'
        f"{_tree(title + body)}</p:cSld>"
        f'<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" {colours} '
        'hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/>'
        '<p:sldLayoutId id="2147483650" r:id="rId2"/></p:sldLayoutIdLst>'
        "<p:txStyles>"
        f'<p:titleStyle><a:lvl1pPr algn="l"><a:buNone/><a:defRPr sz="{heading}" b="1">'
        '<a:solidFill><a:schemeClr val="accent1"/></a:solidFill>'
        '<a:latin typeface="+mj-lt"/></a:defRPr></a:lvl1pPr></p:titleStyle>'
        '<p:bodyStyle><a:lvl1pPr marL="0" indent="0" algn="l">'
        '<a:spcBef><a:spcPts val="600"/></a:spcBef><a:buNone/>'
        f'<a:defRPr sz="{_BODY_SIZE}"><a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
        '<a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr></p:bodyStyle>'
        f'<p:otherStyle><a:lvl1pPr marL="0" algn="l"><a:defRPr sz="{_BODY_SIZE}">'
        '<a:solidFill><a:schemeClr val="tx1"/></a:solidFill>'
        '<a:latin typeface="+mn-lt"/></a:defRPr></a:lvl1pPr></p:otherStyle>'
        "</p:txStyles></p:sldMaster>"
    )


def _cover_layout() -> str:
    shapes = (
        _shape(
            2,
            "Title",
            'type="ctrTitle"',
            (_MARGIN, _COVER_TITLE_TOP, _CONTENT_W, _COVER_TITLE_H),
            "",
            "b",
        )
        + _shape(
            3,
            "Subtitle",
            'type="subTitle" idx="1"',
            (_MARGIN, _COVER_TEXT_TOP, _CONTENT_W, _COVER_TEXT_H),
            "",
        )
        + _bar(4, (_MARGIN, _COVER_RULE_TOP, _COVER_RULE_W, _RULE_H))
    )
    return _layout("title", "Title", shapes)


def _content_layout() -> str:
    shapes = (
        _shape(2, "Title", 'type="title"', (_MARGIN, _TITLE_TOP, _CONTENT_W, _TITLE_H), "", "b")
        + _shape(3, "Text", 'idx="1"', (_MARGIN, _BODY_TOP, _CONTENT_W, _BODY_H), "")
        + _bar(4, (_MARGIN, _RULE_TOP, _CONTENT_W, _RULE_H))
    )
    return _layout("obj", "Title and content", shapes)


def _layout(kind: str, name: str, shapes: str) -> str:
    return (
        f'{_HEAD}<p:sldLayout {_NS} type="{kind}" preserve="1">'
        f'<p:cSld name="{name}">{_tree(shapes)}</p:cSld>'
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"
    )


def _theme(theme: Theme) -> str:
    colours = {
        "dk1": "000000",
        "lt1": "FFFFFF",
        "dk2": MUTED,
        "lt2": RULE,
        "accent1": theme.accent,
        "accent2": SECOND,
        "accent3": theme.accent,
        "accent4": SECOND,
        "accent5": MUTED,
        "accent6": RULE,
        "hlink": SECOND,
        "folHlink": MUTED,
    }
    scheme = "".join(
        f'<a:{name}><a:srgbClr val="{value}"/></a:{name}>' for name, value in colours.items()
    )
    fonts = f'<a:latin typeface="{FONT}"/><a:ea typeface=""/><a:cs typeface=""/>'
    fill = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    line = f'<a:ln w="6350">{fill}</a:ln>'
    name = xml_escape(theme.name)
    return (
        f'{_HEAD}<a:theme xmlns:a="{_A}" name="{name}"><a:themeElements>'
        f'<a:clrScheme name="{name}">{scheme}</a:clrScheme>'
        f'<a:fontScheme name="{name}"><a:majorFont>{fonts}</a:majorFont>'
        f"<a:minorFont>{fonts}</a:minorFont></a:fontScheme>"
        f'<a:fmtScheme name="{name}">'
        f"<a:fillStyleLst>{fill * 3}</a:fillStyleLst>"
        f"<a:lnStyleLst>{line * 3}</a:lnStyleLst>"
        f"<a:effectStyleLst>{'<a:effectStyle><a:effectLst/></a:effectStyle>' * 3}"
        f"</a:effectStyleLst><a:bgFillStyleLst>{fill * 3}</a:bgFillStyleLst>"
        "</a:fmtScheme></a:themeElements></a:theme>"
    )


def _presentation(count: int) -> str:
    slides = "".join(
        f'<p:sldId id="{255 + number}" r:id="rId{2 + number}"/>' for number in range(1, count + 1)
    )
    return (
        f"{_HEAD}<p:presentation {_NS}>"
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slides}</p:sldIdLst>"
        f'<p:sldSz cx="{_SLIDE_W}" cy="{_SLIDE_H}"/>'
        f'<p:notesSz cx="{_SLIDE_H}" cy="{_SLIDE_W}"/>'
        "</p:presentation>"
    )


def _presentation_rels(count: int) -> str:
    slides = "".join(
        f'<Relationship Id="rId{2 + number}" Type="{_R}/slide" Target="slides/slide{number}.xml"/>'
        for number in range(1, count + 1)
    )
    return (
        f'{_HEAD}<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_R}/slideMaster" '
        'Target="slideMasters/slideMaster1.xml"/>'
        f'<Relationship Id="rId2" Type="{_R}/theme" Target="theme/theme1.xml"/>'
        f"{slides}</Relationships>"
    )


def _master_rels() -> str:
    return (
        f'{_HEAD}<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_R}/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
        f'<Relationship Id="rId2" Type="{_R}/slideLayout" '
        'Target="../slideLayouts/slideLayout2.xml"/>'
        f'<Relationship Id="rId3" Type="{_R}/theme" Target="../theme/theme1.xml"/>'
        "</Relationships>"
    )


def _layout_rels() -> str:
    return (
        f'{_HEAD}<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_R}/slideMaster" '
        'Target="../slideMasters/slideMaster1.xml"/>'
        "</Relationships>"
    )


def _slide_rels(slide: Slide) -> str:
    images = "".join(
        f'<Relationship Id="rId{index}" Type="{_R}/image" Target="../media/{xml_escape(name)}"/>'
        for index, name in enumerate(slide.images, start=2)
    )
    return (
        f'{_HEAD}<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_R}/slideLayout" '
        f'Target="../slideLayouts/slideLayout{slide.layout}.xml"/>'
        f"{images}</Relationships>"
    )


def _content_types(count: int, media: Mapping[str, bytes]) -> str:
    extensions = sorted({name.rsplit(".", 1)[-1].lower() for name in media})
    images = "".join(
        f'<Default Extension="{extension}" ContentType="{_IMAGES[extension]}"/>'
        for extension in extensions
    )
    slides = "".join(
        f'<Override PartName="/ppt/slides/slide{number}.xml" ContentType="{_PML}.slide+xml"/>'
        for number in range(1, count + 1)
    )
    return (
        f'{_HEAD}<Types xmlns="{_CT}">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f"{images}"
        f'<Override PartName="/ppt/presentation.xml" '
        f'ContentType="{_PML}.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        f'ContentType="{_PML}.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        f'ContentType="{_PML}.slideLayout+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout2.xml" '
        f'ContentType="{_PML}.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        f"{slides}"
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _root_rels() -> str:
    return (
        f'{_HEAD}<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_R}/officeDocument" Target="ppt/presentation.xml"/>'
        f'<Relationship Id="rId2" Type="{_PKG}/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        f'<Relationship Id="rId3" Type="{_R}/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _core(title: str, subtitle: str, author: str) -> str:
    return (
        f'{_HEAD}<cp:coreProperties xmlns:cp="{_CP}" xmlns:dc="{_DC}">'
        f"<dc:title>{_text(title)}</dc:title>"
        f"<dc:creator>{_text(author)}</dc:creator>"
        f"<dc:description>{_text(subtitle)}</dc:description>"
        f"<cp:lastModifiedBy>{_text(PRODUCER)}</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )


def _app(count: int) -> str:
    return (
        f'{_HEAD}<Properties xmlns="{_APP}"><Application>{_text(PRODUCER)}</Application>'
        f"<Slides>{count}</Slides></Properties>"
    )
