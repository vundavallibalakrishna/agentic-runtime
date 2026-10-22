"""Message content parts. Spec: docs/05-contracts/stream-events.md §4."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from ar_contracts.api_model import ApiModel


class _Part(ApiModel):
    model_config = ConfigDict(frozen=True)


class TextPart(_Part):
    type: Literal["text"]
    text: str


class FilePart(_Part):
    type: Literal["file"]
    file_id: uuid.UUID
    name: str
    mime_type: str


class ImagePart(_Part):
    type: Literal["image"]
    file_id: uuid.UUID
    alt: str = ""


class ToolUsePart(_Part):
    type: Literal["tool_use"]
    tool_call_id: uuid.UUID
    qualified_name: str
    arguments: dict[str, object] | None = None


class Citation(ApiModel):
    """A citation attached to an assistant message.

    ``source_kind`` is ``knowledge``, ``tool_result`` or ``evidence_item``.
    Document fields are omitted for tool results and evidence items.
    """

    model_config = ConfigDict(frozen=True)

    index: int
    source_kind: Literal["knowledge", "tool_result", "evidence_item"] = "knowledge"
    document_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    collection_id: uuid.UUID | None = None
    evidence_id: uuid.UUID | None = None
    title: str = ""
    uri: str = ""
    snippet: str = ""
    page_from: int | None = None
    page_to: int | None = None
    source_modified_at: datetime | None = None


class GroundingClaim(ApiModel):
    model_config = ConfigDict(frozen=True)

    text: str
    citation_indexes: list[int] = Field(default_factory=list)
    status: Literal["grounded", "removed", "flagged"]


class GroundingReport(ApiModel):
    model_config = ConfigDict(frozen=True)

    mode: Literal["off", "preferred", "strict"]
    claims: list[GroundingClaim] = Field(default_factory=list)
    sources: list[Citation] = Field(default_factory=list)
    tools: list[dict[str, object]] = Field(default_factory=list)
    approvals: list[dict[str, object]] = Field(default_factory=list)


class GroundingPart(_Part):
    type: Literal["grounding"]
    report: GroundingReport


class CitationRefPart(_Part):
    type: Literal["citation_ref"]
    index: int
    citation: Citation


class ToolResultPart(_Part):
    type: Literal["tool_result"]
    tool_call_id: uuid.UUID
    text: str
    is_error: bool = False


ContentPart = Annotated[
    TextPart
    | FilePart
    | ImagePart
    | ToolUsePart
    | CitationRefPart
    | ToolResultPart
    | GroundingPart,
    Field(discriminator="type"),
]
