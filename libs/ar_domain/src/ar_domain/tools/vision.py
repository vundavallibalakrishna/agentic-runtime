"""image.ask. One question about a screenshot, chart, UI or diagram."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import ArError

if TYPE_CHECKING:
    from typing import Any
from ar_domain.documents.vision import VisionError, ask_image
from ar_domain.tools.documents import _actor, _error, _ok, _source_bytes


def dispatch_image(  # noqa: PLR0911
    store: Any, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    """Run one image tool. Unknown names are errors."""
    if name != "ask":
        return _error("unknown_tool", f"unknown tool {name}")
    actor = _actor(arguments)
    if actor is None:
        return _error("validation_failed", "The image tool needs a tenant.")
    question = str(arguments.get("question") or "").strip()
    if not question:
        return _error("validation_failed", "question is required.")
    document_id = str(arguments.get("documentId") or arguments.get("document_id") or "")
    page = arguments.get("page")
    if document_id and page not in {None, ""}:
        try:
            data, filename, media = _page_image(store, actor, document_id, page)
        except ArError as exc:
            return _error(exc.code.value, exc.detail)
    else:
        try:
            data, filename, media, _source, _ref = _source_bytes(store, arguments)
        except ArError as exc:
            return _error(exc.code.value, exc.detail)
    alias = _vision_alias(store, arguments)
    try:
        answer = ask_image(
            store,
            actor.tenant_id,
            alias=alias,
            question=question,
            data=data,
            media_type=media or filename,
        )
    except VisionError as exc:
        return _error(exc.code, _what_next(exc))
    return _ok(answer, {"kind": "image_ask", "alias": alias or "vision"})


_READ_TEXT = (
    " This turn can still read the text printed in the image: call documents.ocr with the "
    "same file. Describing what the image shows needs the vision model."
)


def _what_next(exc: VisionError) -> str:
    """The refusal, and what the agent can do now when no model here can read images.

    The setup message is for an administrator. The model reading it needs to know that
    text recognition does not need a vision model.
    """
    return exc.message + _READ_TEXT if exc.code == "vision_unavailable" else exc.message


def _page_image(
    store: Any, actor: object, document_id: str, page: object
) -> tuple[bytes, str, str]:
    """Render one page of a stored document for the vision model."""
    import uuid  # noqa: PLC0415

    from ar_common.errors import NotFoundError, ValidationFailedError  # noqa: PLC0415
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415

    try:
        number = int(str(page))
    except (TypeError, ValueError) as exc:
        raise ValidationFailedError("page must be a number.") from exc
    library = DocumentLibrary(store)
    try:
        original = library.original(actor, uuid.UUID(document_id))  # type: ignore[arg-type]
    except ValueError as exc:
        raise NotFoundError("document not found") from exc
    rendered = _render_page(original, number)
    return rendered, f"page-{number}.png", "image/png"


def _render_page(data: bytes, page: int) -> bytes:
    import shutil  # noqa: PLC0415
    import subprocess  # noqa: PLC0415
    import tempfile  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    from ar_common.errors import ValidationFailedError  # noqa: PLC0415
    from ar_common.offload import blocking  # noqa: PLC0415

    binary = shutil.which("pdftoppm")
    if data.startswith(b"%PDF") and binary:
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "page.pdf"
            source.write_bytes(data)
            target = Path(folder) / "page"
            result = blocking(
                lambda: subprocess.run(  # noqa: S603 — pdftoppm is the page renderer on PATH
                    [binary, "-png", "-f", str(page), "-l", str(page), str(source), str(target)],
                    check=False,
                    capture_output=True,
                    timeout=60,
                )
            )
            produced = Path(f"{target}-{page}.png")
            if result.returncode == 0 and produced.is_file():
                return produced.read_bytes()
    raise ValidationFailedError(
        "This page could not be rendered. A PDF page needs pdftoppm in the image."
    )


def _vision_alias(store: Any, arguments: dict[str, object]) -> str:
    named = arguments.get("visionAlias") or arguments.get("vision_alias")
    if isinstance(named, str) and named.strip():
        return named.strip()
    version_id = arguments.get("_agent_version_id")
    versions = getattr(store, "versions", None)
    version = (
        versions.get(version_id)
        if isinstance(versions, dict) and isinstance(version_id, uuid.UUID)
        else None
    )
    definition = version.get("definition") if isinstance(version, dict) else None
    model = definition.get("model") if isinstance(definition, dict) else None
    if isinstance(model, dict):
        alias = model.get("vision_alias") or model.get("visionAlias")
        if isinstance(alias, str) and alias.strip():
            return alias.strip()
    return "vision"
