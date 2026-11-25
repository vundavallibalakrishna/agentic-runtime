"""Allow a service connection to exchange a stored secret for a short-lived token.

Revision ID: 0067
Revises: 0066
Create Date: 2026-11-24

The kind check listed the auth kinds a connection can store. ``token_exchange``
is one more: the secret is posted to the connection's token URL and the returned
token is sent on later calls. Expand only. Downgrade restores the previous check
and refuses if a row already uses the new kind.
"""

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0067"
down_revision: str | None = "0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = (
    "kind IN ('api_key','bearer','basic','oauth_authorization_code',"
    "'oauth_client_credentials','token_exchange')"
)
_OLD = "kind IN ('api_key','bearer','basic','oauth_authorization_code','oauth_client_credentials')"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_service_connections_kind"), "service_connections", type_="check")
    op.create_check_constraint(op.f("ck_service_connections_kind"), "service_connections", _NEW)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM service_connections WHERE kind = 'token_exchange'"))
    op.drop_constraint(op.f("ck_service_connections_kind"), "service_connections", type_="check")
    op.create_check_constraint(op.f("ck_service_connections_kind"), "service_connections", _OLD)
