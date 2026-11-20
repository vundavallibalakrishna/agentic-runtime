"""Measure a document against the registered context window.

The model decides how to read. This module only reports the measured facts:
tokens, whether the text fits, and the budget the window leaves.
"""

from __future__ import annotations

from dataclasses import dataclass

from ar_common.settings import get_settings
from ar_domain.knowledge.chunker import token_count


@dataclass(frozen=True, slots=True)
class NamedText:
    """One named document, measured the way a prompt spends the window."""

    file_id: str
    document_id: str
    tokens: int
    characters: int
    headings: int
    title: str = ""
    page_count: int = 0
    outline: tuple[str, ...] = ()
    tables: int = 0
    fits: bool = False


def estimate_tokens(text: str) -> int:
    """Tokens the ingest counter would charge, times the install's margin."""
    if not text.strip():
        return 0
    factor = float(get_settings().document_token_factor)
    return max(1, int(token_count(text) * factor))


def usable_tokens(context_window: int | None) -> int | None:
    """Tokens left for document text. ``None`` when the model has no registered window."""
    if (
        not isinstance(context_window, int)
        or isinstance(context_window, bool)
        or context_window <= 0
    ):
        return None
    settings = get_settings()
    margin = int(context_window * float(settings.document_margin_ratio))
    left = (
        context_window
        - int(settings.document_output_reserve)
        - int(settings.document_instruction_reserve)
        - int(settings.document_tool_reserve)
        - int(settings.document_history_reserve)
        - margin
    )
    return max(0, left)


def documents_fit(
    documents: list[NamedText], context_window: int | None
) -> tuple[bool, int | None]:
    """Whether the measured text fits the usable budget."""
    usable = usable_tokens(context_window)
    total_tokens = sum(item.tokens for item in documents)
    total_chars = sum(item.characters for item in documents)
    if usable is None:
        return total_chars <= int(get_settings().document_retrieval_budget), None
    return total_tokens <= usable, usable
