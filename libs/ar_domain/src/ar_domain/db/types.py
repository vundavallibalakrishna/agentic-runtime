"""Column helpers. Spec: docs/04-data/schema.md §0."""

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ar_common.ids import new_id

JsonObject = dict[str, Any]


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUIDv7 primary key, generated in the app and by Postgres."""
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_id,
        server_default=text("uuidv7()"),
    )


def tenant_fk(*, nullable: bool = False) -> Mapped[uuid.UUID]:
    """Tenant foreign key. Nullable only for platform-or-own tables."""
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=nullable,
    )


def created_at_col() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


def updated_at_col() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


def jsonb_col(*, default: str = "'{}'::jsonb") -> Mapped[JsonObject]:
    return mapped_column(JSONB, nullable=False, server_default=text(default))


def text_array(*, default: str = "'{}'::text[]") -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text()), nullable=False, server_default=text(default))


CITEXT_COL = CITEXT()
