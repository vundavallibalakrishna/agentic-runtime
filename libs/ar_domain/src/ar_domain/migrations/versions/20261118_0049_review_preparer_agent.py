"""Allow an agent as the preparer of a review item.

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-18

Expand. ``review_items.preparer_principal_type`` gains ``agent``: an assistant reply is
prepared by the agent that wrote it, and the person who accepts it is the reviewer. The
two lists are written out here, so this revision keeps meaning the same thing whatever
the model later allows. Downgrade restores the earlier list for new rows and leaves existing rows in
place (``NOT VALID``), so no recorded acceptance is deleted.
"""

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAME = "ck_review_items_preparer_principal_type"
_BEFORE = "preparer_principal_type IN ('user','service_account','guest')"
_AFTER = "preparer_principal_type IN ('user','service_account','guest','agent')"


def upgrade() -> None:
    op.drop_constraint(op.f(_NAME), "review_items", type_="check")
    op.create_check_constraint(op.f(_NAME), "review_items", _AFTER)


def downgrade() -> None:
    op.drop_constraint(op.f(_NAME), "review_items", type_="check")
    op.create_check_constraint(
        op.f(_NAME),
        "review_items",
        _BEFORE,
        postgresql_not_valid=True,
    )
