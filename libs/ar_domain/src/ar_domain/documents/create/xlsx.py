"""XLSX writer. Text uses shared strings so the library reader can open the file."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.documents.create.spec import Cell
from ar_domain.documents.create.xmlpack import pack, xml_escape

if TYPE_CHECKING:
    from ar_domain.documents.create.spec import DocumentSpec, Sheet

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC = "http://purl.org/dc/elements/1.1/"
_APP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_SHEET = "application/vnd.openxmlformats-officedocument.spreadsheetml"


class _Strings:
    def __init__(self) -> None:
        self.values: list[str] = []
        self._index: dict[str, int] = {}

    def add(self, text: str) -> int:
        found = self._index.get(text)
        if found is not None:
            return found
        found = len(self.values)
        self.values.append(text)
        self._index[text] = found
        return found

    def xml(self) -> str:
        items = "".join(f"<si><t>{xml_escape(value)}</t></si>" for value in self.values)
        count = len(self.values)
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<sst xmlns="{_NS}" count="{count}" uniqueCount="{count}">{items}</sst>'
        )


def render_xlsx(spec: DocumentSpec) -> bytes:
    strings = _Strings()
    sheets = spec.sheets
    parts: dict[str, str] = {
        "[Content_Types].xml": _content_types(len(sheets)),
        "_rels/.rels": _root_rels(),
        "xl/workbook.xml": _workbook(sheets),
        "xl/_rels/workbook.xml.rels": _workbook_rels(len(sheets)),
        "xl/styles.xml": _styles(spec.theme.accent),
        "xl/sharedStrings.xml": strings.xml(),
        "docProps/core.xml": _core(spec),
        "docProps/app.xml": _app(),
    }
    for index, sheet in enumerate(sheets, start=1):
        parts[f"xl/worksheets/sheet{index}.xml"] = _worksheet(sheet, strings)
    parts["xl/sharedStrings.xml"] = strings.xml()
    return pack(parts)


def _worksheet(sheet: Sheet, strings: _Strings) -> str:
    width = len(sheet.columns)
    rows = [_header_row(sheet.columns, strings)]
    rows.extend(
        _body_row(index, row, width, strings) for index, row in enumerate(sheet.rows, start=2)
    )
    last_row = max(1, len(sheet.rows) + 1)
    last_col = _letter(max(0, width - 1))
    ref = f"A1:{last_col}{last_row}"
    cols = "".join(
        f'<col min="{index}" max="{index}" width="{_width(sheet, index - 1)}" customWidth="1"/>'
        for index in range(1, width + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{_NS}" xmlns:r="{_OFFICE}">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        "</sheetView></sheetViews>"
        f'<dimension ref="{ref}"/>'
        f"<cols>{cols}</cols>"
        f"<sheetData>{''.join(rows)}</sheetData>"
        f'<autoFilter ref="{ref}"/>'
        "</worksheet>"
    )


def _header_row(columns: tuple[str, ...], strings: _Strings) -> str:
    cells = []
    for index, name in enumerate(columns):
        pointer = strings.add(name)
        ref = f"{_letter(index)}1"
        cells.append(f'<c r="{ref}" s="1" t="s"><v>{pointer}</v></c>')
    return f'<row r="1">{"".join(cells)}</row>'


def _body_row(row_index: int, row: tuple[Cell, ...], width: int, strings: _Strings) -> str:
    cells = []
    for index in range(width):
        cell = row[index] if index < len(row) else Cell("", None)
        ref = f"{_letter(index)}{row_index}"
        cells.append(_cell_xml(ref, cell, strings))
    return f'<row r="{row_index}">{"".join(cells)}</row>'


def _cell_xml(ref: str, cell: Cell, strings: _Strings) -> str:
    if cell.number is not None and cell.text:
        return f'<c r="{ref}" s="3"><v>{_number(cell.number)}</v></c>'
    if not cell.text:
        return f'<c r="{ref}" s="2"/>'
    pointer = strings.add(cell.text)
    return f'<c r="{ref}" s="2" t="s"><v>{pointer}</v></c>'


def _number(value: float) -> str:
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return format(value, ".15g")


def _width(sheet: Sheet, index: int) -> int:
    header = len(sheet.columns[index]) if index < len(sheet.columns) else 8
    longest = header
    for row in sheet.rows:
        if index < len(row):
            longest = max(longest, min(len(row[index].text), 40))
    return min(40, max(10, longest + 2))


def _letter(index: int) -> str:
    number = index + 1
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _workbook(sheets: tuple[Sheet, ...]) -> str:
    items = "".join(
        f'<sheet name="{xml_escape(sheet.name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<workbook xmlns="{_NS}" xmlns:r="{_OFFICE}">'
        f"<sheets>{items}</sheets></workbook>"
    )


def _workbook_rels(count: int) -> str:
    items = [
        f'<Relationship Id="rId{index}" Type="{_OFFICE}/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, count + 1)
    ]
    items.append(f'<Relationship Id="rId{count + 1}" Type="{_OFFICE}/styles" Target="styles.xml"/>')
    items.append(
        f'<Relationship Id="rId{count + 2}" Type="{_OFFICE}/sharedStrings" '
        'Target="sharedStrings.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Relationships xmlns="{_PKG}">{"".join(items)}</Relationships>'
    )


def _styles(accent: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{_NS}">'
        '<fonts count="2">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font>'
        "</fonts>"
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        f'<fill><patternFill patternType="solid"><fgColor rgb="FF{accent}"/></patternFill></fill>'
        "</fills>"
        '<borders count="2">'
        "<border><left/><right/><top/><bottom/><diagonal/></border>"
        "<border>"
        '<left style="thin"><color rgb="FFD0D7E2"/></left>'
        '<right style="thin"><color rgb="FFD0D7E2"/></right>'
        '<top style="thin"><color rgb="FFD0D7E2"/></top>'
        '<bottom style="thin"><color rgb="FFD0D7E2"/></bottom>'
        "<diagonal/>"
        "</border>"
        "</borders>"
        '<cellStyleXfs count="1">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        "</cellStyleXfs>"
        '<cellXfs count="4">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" '
        'applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">'
        '<alignment horizontal="left" vertical="center"/>'
        "</xf>"
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" '
        'applyBorder="1" applyAlignment="1">'
        '<alignment horizontal="right"/>'
        "</xf>"
        "</cellXfs>"
        "</styleSheet>"
    )


def _content_types(count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        f'ContentType="{_SHEET}.worksheet+xml"/>'
        for index in range(1, count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Types xmlns="{_CT}">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Override PartName="/xl/workbook.xml" ContentType="{_SHEET}.sheet.main+xml"/>'
        f'<Override PartName="/xl/styles.xml" ContentType="{_SHEET}.styles+xml"/>'
        f'<Override PartName="/xl/sharedStrings.xml" ContentType="{_SHEET}.sharedStrings+xml"/>'
        f"{sheets}"
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
        f'<Relationship Id="rId1" Type="{_OFFICE}/officeDocument" Target="xl/workbook.xml"/>'
        f'<Relationship Id="rId2" Type="{_PKG}/metadata/core-properties" '
        'Target="docProps/core.xml"/>'
        f'<Relationship Id="rId3" Type="{_OFFICE}/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _core(spec: DocumentSpec) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{_CP}" xmlns:dc="{_DC}">'
        f"<dc:title>{xml_escape(spec.title)}</dc:title>"
        f"<dc:creator>{xml_escape(spec.author)}</dc:creator>"
        "<cp:lastModifiedBy>Agentic Runtime</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )


def _app() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<Properties xmlns="{_APP}"><Application>Agentic Runtime</Application></Properties>'
    )
