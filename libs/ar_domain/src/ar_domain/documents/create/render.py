"""Writers registered for documents.create. A format is a registration."""

from __future__ import annotations

from collections.abc import Callable

from ar_domain.documents.create.docx import render_docx
from ar_domain.documents.create.pdf import render_pdf
from ar_domain.documents.create.pptx import render_pptx
from ar_domain.documents.create.spec import CreateError, DocumentSpec
from ar_domain.documents.create.textfmt import render_csv, render_html, render_markdown
from ar_domain.documents.create.xlsx import render_xlsx

Renderer = Callable[[DocumentSpec], bytes]
_RENDERERS: dict[str, Renderer] = {}


def register_renderer(name: str, renderer: Renderer) -> None:
    """Add or replace the writer for one format."""
    _RENDERERS[name.strip().lower()] = renderer


def registered_formats() -> frozenset[str]:
    return frozenset(_RENDERERS)


def render(spec: DocumentSpec) -> bytes:
    renderer = _RENDERERS.get(spec.format)
    if renderer is None:
        known = ", ".join(sorted(_RENDERERS)) or "none"
        raise CreateError(f"No renderer is registered for {spec.format}. Registered: {known}.")
    return renderer(spec)


def _install() -> None:
    register_renderer("docx", render_docx)
    register_renderer("pdf", render_pdf)
    register_renderer("pptx", render_pptx)
    register_renderer("xlsx", render_xlsx)
    register_renderer("md", render_markdown)
    register_renderer("html", render_html)
    register_renderer("csv", render_csv)


_install()
