"""Local password credential on users.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-09

Sign-in moves in-house: a user's password is stored as an argon2id hash on the user row
instead of in an external identity provider. Expand only — both columns are nullable, so
older code and existing rows keep working; a user with no ``password_hash`` cannot sign
in with a password until one is set. Spec: docs/06-security/authn-authz.md.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("password_set_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "password_set_at")
    op.drop_column("users", "password_hash")
