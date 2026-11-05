"""Choose a writer for one parsed document."""

from __future__ import annotations

from ar_domain.documents.create.docx import render_docx
from ar_domain.documents.create.pdf import render_pdf
from ar_domain.documents.create.spec import CreateError, DocumentSpec
from ar_domain.documents.create.xlsx import render_xlsx


def render(spec: DocumentSpec) -> bytes:
    if spec.format == "docx":
        return render_docx(spec)
    if spec.format == "pdf":
        return render_pdf(spec)
    if spec.format == "xlsx":
        return render_xlsx(spec)
    raise CreateError("format must be docx, pdf or xlsx.")
