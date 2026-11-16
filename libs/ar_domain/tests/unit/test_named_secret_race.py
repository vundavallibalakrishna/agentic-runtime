"""A unique secret name is a 409, not an unhandled database error."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from ar_common.errors import ConflictError
from ar_domain.durable.m26 import upsert_named_secret


class _Session:
    async def execute(self, *_args: object, **_kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("ux_named_secrets_name"))


@pytest.mark.asyncio
async def test_a_unique_name_race_is_a_conflict() -> None:
    row = {
        "id": uuid.uuid4(),
        "tenant_id": uuid.uuid4(),
        "name": "__run_callback_secret__",
        "ciphertext": b"sealed",
        "created_at": None,
        "updated_at": None,
    }
    with pytest.raises(ConflictError, match="retry"):
        await upsert_named_secret(_Session(), row)  # type: ignore[arg-type]
