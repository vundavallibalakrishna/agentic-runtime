"""Markdown, HTML and CSV writers for documents.create."""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ar_domain.documents.create.spec import DocumentSpec


def render_markdown(spec: DocumentSpec) -> bytes:
    lines = [f"# {spec.title}", ""]
    if spec.subtitle:
        lines.extend([spec.subtitle, ""])
    for section in spec.sections:
        marks = "#" * max(1, min(section.level, 6))
        lines.append(f"{marks} {section.heading}")
        lines.extend(section.paragraphs)
        lines.extend(f"- {item}" for item in section.bullets)
        if section.table is not None:
            lines.append(_markdown_table(section.table.columns, section.table.rows))
        lines.append("")
    if not spec.sections and spec.sheets:
        for sheet in spec.sheets:
            lines.append(f"## {sheet.name}")
            lines.append(_markdown_table(sheet.columns, sheet.rows))
            lines.append("")
    return "\n".join(lines).strip().encode()


def render_html(spec: DocumentSpec) -> bytes:
    from html import escape  # noqa: PLC0415

    parts = ["<!DOCTYPE html><html><body>", f"<h1>{escape(spec.title)}</h1>"]
    if spec.subtitle:
        parts.append(f"<p>{escape(spec.subtitle)}</p>")
    for section in spec.sections:
        level = max(1, min(section.level, 6))
        parts.append(f"<h{level}>{escape(section.heading)}</h{level}>")
        parts.extend(f"<p>{escape(paragraph)}</p>" for paragraph in section.paragraphs)
        if section.bullets:
            parts.append("<ul>")
            parts.extend(f"<li>{escape(item)}</li>" for item in section.bullets)
            parts.append("</ul>")
    parts.append("</body></html>")
    return "".join(parts).encode()


def render_csv(spec: DocumentSpec) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    sheets = spec.sheets
    if not sheets and spec.sections:
        for section in spec.sections:
            if section.table is None:
                continue
            writer.writerow(section.table.columns)
            for row in section.table.rows:
                writer.writerow([cell.text for cell in row])
    for sheet in sheets:
        writer.writerow(sheet.columns)
        for row in sheet.rows:
            writer.writerow([cell.text for cell in row])
    return buffer.getvalue().encode()


def _markdown_table(columns: tuple[str, ...], rows: tuple[tuple[object, ...], ...]) -> str:
    header = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(getattr(cell, "text", str(cell)) for cell in row) + " |" for row in rows
    ]
    return "\n".join([header, rule, *body])
