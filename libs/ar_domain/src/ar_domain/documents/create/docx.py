"""DOCX writer. Heading styles match the library reader (Heading1, Heading2)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.documents.create.xmlpack import pack, xml_escape

if TYPE_CHECKING:
    from ar_domain.documents.create.spec import DocumentSpec, Section, Table

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC = "http://purl.org/dc/elements/1.1/"
_APP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_REL_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def render_docx(spec: DocumentSpec) -> bytes:
    parts = {
        "[Content_Types].xml": _content_types(header=spec.theme.show_header),
        "_rels/.rels": _root_rels(),
        "word/document.xml": _document(spec),
        "word/styles.xml": _styles(spec),
        "word/numbering.xml": _numbering(),
        "word/_rels/document.xml.rels": _doc_rels(header=spec.theme.show_header),
        "docProps/core.xml": _core(spec),
        "docProps/app.xml": _app(),
    }
    if spec.theme.show_header:
        parts["word/header1.xml"] = _header(spec)
    return pack(parts)


def _document(spec: DocumentSpec) -> str:
    blocks = [_title(spec.title, spec.theme.title_half_points)]
    if spec.subtitle:
        blocks.append(_subtitle(spec.subtitle))
    blocks.append(_meta(spec.author))
    for section in spec.sections:
        blocks.extend(_section(section, spec.theme.heading_half_points))
    blocks.append(_sect_pr(header=spec.theme.show_header))
    body = "".join(blocks)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W}" xmlns:r="{_R}"><w:body>{body}</w:body></w:document>'
    )


def _section(section: Section, heading_size: int) -> list[str]:
    size = heading_size if section.level == 1 else max(24, heading_size - 4)
    blocks = [_heading(section.heading, section.level, size)]
    blocks.extend(_paragraph(text) for text in section.paragraphs)
    blocks.extend(_bullet(text) for text in section.bullets)
    if section.table is not None:
        if section.table.caption and section.table.caption != section.heading:
            blocks.append(_caption(section.table.caption))
        blocks.append(_table(section.table))
    return blocks


def _title(text: str, half_points: int) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>'
        f'<w:r><w:rPr><w:b/><w:sz w:val="{half_points}"/>'
        f'<w:szCs w:val="{half_points}"/></w:rPr>{_t(text)}</w:r></w:p>'
    )


def _subtitle(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>'
        f'<w:r><w:rPr><w:i/><w:color w:val="5B6775"/><w:sz w:val="22"/></w:rPr>'
        f"{_t(text)}</w:r></w:p>"
    )


def _meta(author: str) -> str:
    return (
        '<w:p><w:r><w:rPr><w:color w:val="5B6775"/><w:sz w:val="18"/></w:rPr>'
        f"{_t(author)}</w:r></w:p>"
    )


def _heading(text: str, level: int, half_points: int) -> str:
    style = "Heading1" if level == 1 else "Heading2"
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>'
        f'<w:r><w:rPr><w:b/><w:sz w:val="{half_points}"/>'
        f'<w:szCs w:val="{half_points}"/></w:rPr>{_t(text)}</w:r></w:p>'
    )


def _paragraph(text: str) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr><w:r>{_t(text)}</w:r></w:p>'


def _bullet(text: str) -> str:
    return (
        '<w:p><w:pPr><w:pStyle w:val="ListBullet"/>'
        '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>'
        f"<w:r>{_t(text)}</w:r></w:p>"
    )


def _caption(text: str) -> str:
    return (
        '<w:p><w:r><w:rPr><w:i/><w:color w:val="5B6775"/><w:sz w:val="18"/></w:rPr>'
        f"{_t(text)}</w:r></w:p>"
    )


def _table(table: Table) -> str:
    width = 9000 // max(1, len(table.columns))
    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in table.columns)
    header = _row(table.columns, header=True)
    body = "".join(_row(tuple(cell.text for cell in row), header=False) for row in table.rows)
    borders = "".join(
        f'<w:{edge} w:val="single" w:sz="4" w:space="0" w:color="D0D7E2"/>'
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV")
    )
    return (
        '<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/>'
        f"<w:tblBorders>{borders}</w:tblBorders></w:tblPr>"
        f"<w:tblGrid>{grid}</w:tblGrid>{header}{body}</w:tbl>"
    )


def _row(values: tuple[str, ...], *, header: bool) -> str:
    cells = "".join(_cell(value, header=header) for value in values)
    return f"<w:tr>{cells}</w:tr>"


def _cell(text: str, *, header: bool) -> str:
    if header:
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="1F4E79"/>'
        run = f'<w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>{_t(text)}'
    else:
        shade = '<w:shd w:val="clear" w:color="auto" w:fill="FFFFFF"/>'
        run = _t(text)
    return f"<w:tc><w:tcPr>{shade}</w:tcPr><w:p><w:r>{run}</w:r></w:p></w:tc>"


def _t(text: str) -> str:
    return f'<w:t xml:space="preserve">{xml_escape(text)}</w:t>'


def _sect_pr(*, header: bool) -> str:
    reference = '<w:headerReference w:type="default" r:id="rIdHeader"/>' if header else ""
    return (
        f"<w:sectPr>{reference}"
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" '
        'w:header="708" w:footer="708" w:gutter="0"/>'
        "</w:sectPr>"
    )


def _header(spec: DocumentSpec) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:hdr xmlns:w="{_W}"><w:p><w:r>'
        f'<w:rPr><w:color w:val="{spec.theme.accent}"/><w:sz w:val="18"/></w:rPr>'
        f"{_t(spec.title)}</w:r></w:p></w:hdr>"
    )


def _styles(spec: DocumentSpec) -> str:
    accent = spec.theme.accent
    title = spec.theme.title_half_points
    heading = spec.theme.heading_half_points
    second = max(24, heading - 4)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{_W}">'
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>'
        '<w:sz w:val="22"/><w:szCs w:val="22"/>'
        "</w:rPr></w:rPrDefault></w:docDefaults>"
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">'
        '<w:name w:val="Normal"/><w:qFormat/></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title">'
        '<w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/>'
        f'<w:rPr><w:b/><w:color w:val="{accent}"/>'
        f'<w:sz w:val="{title}"/><w:szCs w:val="{title}"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Subtitle">'
        '<w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/>'
        '<w:rPr><w:i/><w:color w:val="5B6775"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1">'
        '<w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:qFormat/>'
        f'<w:rPr><w:b/><w:color w:val="{accent}"/>'
        f'<w:sz w:val="{heading}"/><w:szCs w:val="{heading}"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2">'
        '<w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:qFormat/>'
        f'<w:rPr><w:b/><w:color w:val="2E75B6"/>'
        f'<w:sz w:val="{second}"/><w:szCs w:val="{second}"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="ListBullet">'
        '<w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/>'
        '<w:pPr><w:ind w:left="720"/></w:pPr></w:style>'
        "</w:styles>"
    )


def _numbering() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:numbering xmlns:w="{_W}">'
        '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>'
        '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
        '<w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
        '<w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>'
        '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>'
    )


def _content_types(*, header: bool) -> str:
    header_override = (
        '<Override PartName="/word/header1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>'
        if header
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_CT}">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/numbering.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
        f"{header_override}"
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{_REL_OFFICE}/officeDocument" '
        'Target="word/document.xml"/>'
        f'<Relationship Id="rId2" Type="{_PKG}/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        f'<Relationship Id="rId3" Type="{_REL_OFFICE}/extended-properties" '
        'Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _doc_rels(*, header: bool) -> str:
    header_rel = (
        f'<Relationship Id="rIdHeader" Type="{_REL_OFFICE}/header" Target="header1.xml"/>'
        if header
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rIdStyles" Type="{_REL_OFFICE}/styles" Target="styles.xml"/>'
        f'<Relationship Id="rIdNumbering" Type="{_REL_OFFICE}/numbering" Target="numbering.xml"/>'
        f"{header_rel}</Relationships>"
    )


def _core(spec: DocumentSpec) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{_CP}" xmlns:dc="{_DC}">'
        f"<dc:title>{xml_escape(spec.title)}</dc:title>"
        f"<dc:creator>{xml_escape(spec.author)}</dc:creator>"
        f"<dc:description>{xml_escape(spec.subtitle)}</dc:description>"
        "<cp:lastModifiedBy>Agentic Runtime</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )


def _app() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Properties xmlns="{_APP}"><Application>Agentic Runtime</Application></Properties>'
    )
