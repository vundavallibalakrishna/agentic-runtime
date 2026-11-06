"""Clear the made-up vectors stored for tools.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-06

``tool_versions.embedding`` was filled with numbers computed from a hash of the tool's
description, which carry no meaning. Tool search now embeds the catalogue with the model
the tenant registered and keeps those vectors with the process, so nothing reads or
writes the column. It stays, empty, until a later revision drops it (OQ-106). Downgrade
does not put the made-up numbers back.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The catalogue is a few hundred rows; the change guard on approved versions lets
    # this column change.
    op.execute("UPDATE tool_versions SET embedding = NULL WHERE embedding IS NOT NULL")


def downgrade() -> None:
    """Forward-only. The cleared values were never real vectors."""
