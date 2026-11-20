"""A new docx version of stored passages. The original bytes are not changed.

``redline`` writes Word tracked changes for each replaced anchor. Otherwise the
file is the passages with those anchors replaced.
"""

from __future__ import annotations

from ar_domain.documents.create.xmlpack import pack, xml_escape

_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/settings.xml" '
    'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
    "</Types>"
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
    'Target="word/document.xml"/>'
    "</Relationships>"
)
_DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" '
    'Target="settings.xml"/>'
    "</Relationships>"
)


def render_version(
    passages: list[dict[str, object]],
    changes: list[dict[str, object]],
    *,
    redline: bool,
) -> bytes:
    """Docx bytes for the passages, with the caller's anchor replacements applied."""
    replaced = {
        str(item.get("anchor") or ""): str(item.get("text") or "")
        for item in changes
        if isinstance(item, dict)
    }
    mark = 1
    paragraphs: list[str] = []
    for passage in passages:
        anchor = str(passage.get("anchor") or "")
        old = str(passage.get("text") or "")
        new = replaced.get(anchor, old)
        if redline and anchor in replaced and new != old:
            paragraphs.append(_tracked(old, new, mark))
            mark += 2
        else:
            paragraphs.append(
                f'<w:p><w:r><w:t xml:space="preserve">{xml_escape(new)}</w:t></w:r></w:p>'
            )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(paragraphs)}<w:sectPr/></w:body></w:document>"
    )
    settings = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        + ("<w:trackRevisions/>" if redline else "")
        + "</w:settings>"
    )
    return pack(
        {
            "[Content_Types].xml": _TYPES,
            "_rels/.rels": _RELS,
            "word/_rels/document.xml.rels": _DOC_RELS,
            "word/document.xml": document,
            "word/settings.xml": settings,
        }
    )


def _tracked(old: str, new: str, mark: int) -> str:
    return (
        "<w:p>"
        f'<w:del w:id="{mark}" w:author="Agent" w:date="2026-01-01T00:00:00Z">'
        f'<w:r><w:delText xml:space="preserve">{xml_escape(old)}</w:delText></w:r></w:del>'
        f'<w:ins w:id="{mark + 1}" w:author="Agent" w:date="2026-01-01T00:00:00Z">'
        f'<w:r><w:t xml:space="preserve">{xml_escape(new)}</w:t></w:r></w:ins>'
        "</w:p>"
    )
