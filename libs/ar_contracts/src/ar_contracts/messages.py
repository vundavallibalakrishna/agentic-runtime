"""Message content parts. Spec: docs/05-contracts/stream-events.md §4."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Part(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


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


class Citation(BaseModel):
    """A knowledge citation attached to an assistant message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    collection_id: uuid.UUID
    title: str
    uri: str
    snippet: str
    page_from: int | None = None
    page_to: int | None = None
    source_modified_at: datetime | None = None


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
    TextPart | FilePart | ImagePart | ToolUsePart | CitationRefPart | ToolResultPart,
    Field(discriminator="type"),
]
