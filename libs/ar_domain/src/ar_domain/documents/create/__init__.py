"""Build a DOCX, PDF or XLSX from a structured payload.

Writers use the standard library (OQ-71). The tool stores the bytes as a
workspace artifact so chat can download them.
"""

from ar_domain.documents.create.publish import publish
from ar_domain.documents.create.render import render
from ar_domain.documents.create.spec import MEDIA, CreateError, DocumentSpec, parse

__all__ = ["MEDIA", "CreateError", "DocumentSpec", "parse", "publish", "render"]
