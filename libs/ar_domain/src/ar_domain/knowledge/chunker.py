"""Heading-aware chunking. Spec: docs/03-specs/10-knowledge.md §4.2."""

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_PAGE = re.compile(r"<!--\s*page:(\d+)\s*-->")
_FENCE = re.compile(r"```.*?```", re.DOTALL)
_TABLE = re.compile(r"(?:^\|.+\|$\n?)+", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    ordinal: int
    text: str
    heading_path: list[str]
    page_from: int | None
    page_to: int | None
    token_count: int


def token_count(text: str) -> int:
    """Approximate ``o200k_base``. Uses tiktoken when that extra is installed."""
    try:
        import tiktoken  # noqa: PLC0415
    except ModuleNotFoundError:
        words = re.findall(r"\S+", text)
        return max(1, len(words)) if text.strip() else 0
    encoding = tiktoken.get_encoding("o200k_base")
    return len(encoding.encode(text))


def chunk_markdown(
    markdown: str, *, target_tokens: int = 512, overlap_pct: int = 12
) -> list[ChunkDraft]:
    """Split on headings. Tables and code fences stay intact below 1.5x target."""
    target = min(2048, max(128, target_tokens))
    overlap = max(0, min(30, overlap_pct))
    blocks = _blocks(markdown)
    chunks: list[ChunkDraft] = []
    buffer: list[str] = []
    headings: list[str] = []
    page_from: int | None = None
    page_to: int | None = None
    for kind, body, page in blocks:
        if kind == "heading":
            _flush(chunks, buffer, headings, page_from, page_to, target, overlap)
            buffer = []
            level = body.count("#", 0, body.find(" ")) if " " in body else 1
            title = body.lstrip("#").strip()
            headings = headings[: max(0, level - 1)]
            headings.append(title)
            page_from = page
            page_to = page
            continue
        if page_from is None:
            page_from = page
        page_to = page or page_to
        piece = body.strip()
        if not piece:
            continue
        if kind in {"code", "table"} and token_count(piece) <= int(target * 1.5):
            _flush(chunks, buffer, headings, page_from, page_to, target, overlap)
            buffer = []
            chunks.append(_draft(len(chunks), piece, headings, page, page, token_count(piece)))
            continue
        buffer.append(piece)
        if token_count("\n\n".join(buffer)) >= target:
            _flush(chunks, buffer, headings, page_from, page_to, target, overlap)
            buffer = _overlap(buffer, target, overlap)
            page_from = page
    _flush(chunks, buffer, headings, page_from, page_to, target, overlap)
    return chunks


def _blocks(markdown: str) -> list[tuple[str, str, int | None]]:
    protected: list[str] = []

    def hold(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"\n@@BLOCK{len(protected) - 1}@@\n"

    masked = _FENCE.sub(hold, markdown)
    masked = _TABLE.sub(hold, masked)
    blocks: list[tuple[str, str, int | None]] = []
    page: int | None = None
    for line in masked.splitlines():
        page_match = _PAGE.search(line)
        if page_match:
            page = int(page_match.group(1))
            continue
        if line.startswith("@@BLOCK"):
            index = int(line.replace("@@BLOCK", "").replace("@@", "") or "0")
            body = protected[index] if index < len(protected) else ""
            kind = "code" if body.startswith("```") else "table"
            blocks.append((kind, body, page))
            continue
        if _HEADING.match(line):
            blocks.append(("heading", line, page))
            continue
        blocks.append(("text", line, page))
    return blocks


def _flush(  # noqa: PLR0917 - chunk buffer fields stay positional at the call site
    chunks: list[ChunkDraft],
    buffer: list[str],
    headings: list[str],
    page_from: int | None,
    page_to: int | None,
    target: int,
    overlap: int,
) -> None:
    del overlap
    text = "\n\n".join(part for part in buffer if part.strip())
    if not text.strip():
        return
    words = text.split()
    step = max(target, 1)
    if token_count(text) <= int(target * 1.5):
        chunks.append(_draft(len(chunks), text, headings, page_from, page_to, token_count(text)))
        return
    start = 0
    while start < len(words):
        piece_words = words[start : start + step]
        piece = " ".join(piece_words)
        chunks.append(_draft(len(chunks), piece, headings, page_from, page_to, token_count(piece)))
        start += step


def _overlap(buffer: list[str], _target: int, overlap_pct: int) -> list[str]:
    if overlap_pct <= 0 or not buffer:
        return []
    text = "\n\n".join(buffer)
    words = text.split()
    keep = max(1, int(len(words) * overlap_pct / 100))
    return [" ".join(words[-keep:])]


def _draft(  # noqa: PLR0917 - chunk fields stay positional at the call site
    ordinal: int,
    text: str,
    headings: list[str],
    page_from: int | None,
    page_to: int | None,
    tokens: int,
) -> ChunkDraft:
    return ChunkDraft(
        ordinal=ordinal,
        text=text,
        heading_path=list(headings),
        page_from=page_from,
        page_to=page_to,
        token_count=tokens,
    )
