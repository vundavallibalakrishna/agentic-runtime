"""Formats the layout parser does not read directly.

LibreOffice converts the office formats it owns. Email and zip are read here
and then handed to the same extractor. A missing converter is an error that
names the tool, not a guessed document.
"""

from __future__ import annotations

import email
import email.policy
import io
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from ar_common.offload import blocking
from ar_common.settings import get_settings
from ar_domain.documents.extract import Extracted, ExtractError, extract_bytes


def convert_and_extract(data: bytes, filename: str, media_type: str) -> Extracted:
    """Read one of the formats that need a conversion step."""
    name = filename.lower()
    if name.endswith(".eml") or media_type == "message/rfc822":
        return _email(data, filename)
    if name.endswith(".zip") or media_type in {"application/zip", "application/x-zip-compressed"}:
        return _zip(data, filename)
    target = _office_target(name)
    if target is None:
        raise ExtractError("unsupported", f"Upload a supported file. {filename} is not one.")
    converted = _libreoffice(data, filename, target)
    return extract_bytes(converted, filename=f"{Path(filename).stem}.{target}")


def _office_target(name: str) -> str | None:
    if name.endswith((".doc", ".odt", ".rtf")):
        return "docx"
    if name.endswith((".xls", ".ods")):
        return "xlsx"
    if name.endswith(".msg"):
        return "txt"
    return None


def _libreoffice(data: bytes, filename: str, target: str) -> bytes:
    binary = shutil.which("soffice") or shutil.which("libreoffice")
    if not binary:
        raise ExtractError(
            "unsupported",
            "This format needs LibreOffice in the ingest image, and it is not installed.",
        )
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / Path(filename).name
        source.write_bytes(data)
        try:
            result = blocking(
                lambda: subprocess.run(  # noqa: S603 — the binary is soffice on PATH
                    [binary, "--headless", "--convert-to", target, "--outdir", folder, str(source)],
                    check=False,
                    capture_output=True,
                    timeout=120,
                )
            )
        except subprocess.TimeoutExpired as exc:
            raise ExtractError("ocr_unavailable", "Conversion took too long.") from exc
        produced = source.with_suffix(f".{target}")
        if result.returncode != 0 or not produced.is_file():
            raise ExtractError("corrupt", "LibreOffice could not read this file.")
        return produced.read_bytes()


def _email(data: bytes, filename: str) -> Extracted:
    message = email.message_from_bytes(data, policy=email.policy.default)
    parts = [f"Subject: {message.get('subject', '')}", f"From: {message.get('from', '')}"]
    body = message.get_body(preferencelist=("plain", "html"))
    if body is not None:
        parts.append(str(body.get_content()))
    text = "\n\n".join(part for part in parts if part.strip())
    if not text.strip():
        raise ExtractError("no_text", "This message has no readable text.")
    return extract_bytes(text.encode(), filename=f"{Path(filename).stem}.txt")


def _zip(data: bytes, filename: str) -> Extracted:
    cap = int(get_settings().document_zip_members)
    try:
        book = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ExtractError("corrupt", "This archive could not be read.") from exc
    names = [
        name
        for name in book.namelist()
        if not name.endswith("/") and not name.lower().endswith(".zip")
    ][:cap]
    if not names:
        raise ExtractError("no_text", "This archive has no files.")
    pieces: list[str] = []
    for name in names:
        member = book.read(name)
        if len(member) > int(get_settings().document_max_bytes):
            continue
        try:
            extracted = extract_bytes(member, filename=name)
        except ExtractError:
            continue
        text = "\n".join(passage.text for passage in extracted.passages)
        if text.strip():
            pieces.append(f"# {name}\n{text}")
    if not pieces:
        raise ExtractError("no_text", "No file in this archive could be read.")
    if len(book.namelist()) > cap:
        pieces.append(f"Further members were not read. The page size is {cap}.")
    return extract_bytes("\n\n".join(pieces).encode(), filename=f"{Path(filename).stem}.md")
