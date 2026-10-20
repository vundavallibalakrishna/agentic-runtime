"""Identifier helpers. Spec: docs/02-architecture/adr/ADR-0020-ids-pagination-errors.md."""

import uuid


def new_id() -> uuid.UUID:
    """Return a new UUIDv7.

    Postgres 18 ``uuidv7()`` is used for rows created in the database. Python
    generates the same variant for ids created before insert.
    """
    return uuid.uuid7()
