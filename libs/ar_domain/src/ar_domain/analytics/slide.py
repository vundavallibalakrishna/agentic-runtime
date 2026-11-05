"""One-slide PPTX that carries a chart PNG plus a short narrative.

The package is Office Open XML written with the standard library. A desktop
PowerPoint open is not part of the unit proof.
"""

from __future__ import annotations

import io
import zipfile

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC = "http://purl.org/dc/elements/1.1/"
_WHEN = (2026, 1, 1, 0, 0, 0)


def render_slide(*, title: str, narrative: str, png: bytes) -> bytes:
    """Return a one-slide deck. The chart image is ``ppt/media/chart.png``."""
    parts: dict[str, bytes] = {
        "[Content_Types].xml": _content_types().encode(),
        "_rels/.rels": _root_rels().encode(),
        "docProps/core.xml": _core(title).encode(),
        "docProps/app.xml": _app().encode(),
        "ppt/presentation.xml": _presentation().encode(),
        "ppt/_rels/presentation.xml.rels": _presentation_rels().encode(),
        "ppt/slides/slide1.xml": _slide(title, narrative).encode(),
        "ppt/slides/_rels/slide1.xml.rels": _slide_rels().encode(),
        "ppt/media/chart.png": png,
    }
    return _pack(parts)


def _slide(title: str, narrative: str) -> str:
    lines = [line.strip() for line in narrative.splitlines() if line.strip()]
    if not lines:
        lines = ["Chart."]
    body = "".join(f"<a:p><a:r><a:t>{_xml(line)}</a:t></a:r></a:p>" for line in lines[:12])
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:sld xmlns:a="{_A}" xmlns:r="{_R}" xmlns:p="{_P}">'
        "<p:cSld><p:spTree>"
        '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        "<p:grpSpPr/>"
        '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Title"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        "<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>"
        f"<a:p><a:r><a:t>{_xml(title)}</a:t></a:r></a:p>"
        "</p:txBody></p:sp>"
        '<p:sp><p:nvSpPr><p:cNvPr id="3" name="Body"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
        f"<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>{body}</p:txBody></p:sp>"
        '<p:pic><p:nvPicPr><p:cNvPr id="4" name="chart"/>'
        '<p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr>'
        '<p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        '<p:spPr><a:xfrm><a:off x="457200" y="2743200"/>'
        '<a:ext cx="8229600" cy="3429000"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
        "</p:spTree></p:cSld></p:sld>"
    )


def _content_types() -> str:
    slide = "application/vnd.openxmlformats-officedocument.presentationml"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_CT}">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        f'<Override PartName="/ppt/presentation.xml" ContentType="{slide}.presentation.main+xml"/>'
        f'<Override PartName="/ppt/slides/slide1.xml" ContentType="{slide}.slide+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _root_rels() -> str:
    office = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{office}/officeDocument" Target="ppt/presentation.xml"/>'
        f'<Relationship Id="rId2" Type="{office}/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        "</Relationships>"
    )


def _presentation() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<p:presentation xmlns:p="{_P}" xmlns:r="{_R}">'
        '<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst>'
        '<p:sldSz cx="12192000" cy="6858000" type="screen16x9"/>'
        "</p:presentation>"
    )


def _presentation_rels() -> str:
    kind = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId1" Type="{kind}" Target="slides/slide1.xml"/>'
        "</Relationships>"
    )


def _slide_rels() -> str:
    kind = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}">'
        f'<Relationship Id="rId2" Type="{kind}" Target="../media/chart.png"/>'
        "</Relationships>"
    )


def _core(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{_CP}" xmlns:dc="{_DC}">'
        f"<dc:title>{_xml(title)}</dc:title><dc:creator>Agentic Runtime</dc:creator>"
        "</cp:coreProperties>"
    )


def _app() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">'
        "<Application>Agentic Runtime</Application><Slides>1</Slides></Properties>"
    )


def _xml(value: str) -> str:
    text = "".join(ch for ch in value if ch >= " " or ch in "\n\t")
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _pack(parts: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as book:
        for name in sorted(parts):
            info = zipfile.ZipInfo(filename=name, date_time=_WHEN)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            info.create_system = 0
            book.writestr(info, parts[name])
    return buffer.getvalue()
