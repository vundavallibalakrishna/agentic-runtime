"""Per-tenant audit hash chain. Spec: docs/03-specs/17-audit-usage-metering.md §1."""

import hashlib
from datetime import datetime  # noqa: TC003
from typing import cast

import orjson
from pydantic import JsonValue

from ar_common.jcs import canonical_json

GENESIS = "0" * 64


def json_safe(value: object) -> JsonValue:
    """Round-trip a value through JSON so the hash input is canonical."""
    loaded = orjson.loads(orjson.dumps(value, default=str))
    return cast("JsonValue", loaded)


def audit_document(
    *,
    tenant_id: str | None,
    tenant_seq: int,
    occurred_at: datetime,
    actor_type: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str | None,
    outcome: str,
    detail: object,
    prev_hash: str,
) -> dict[str, JsonValue]:
    """Fields that enter the hash. ``id`` and ``hash`` are excluded."""
    safe_detail = json_safe(detail)
    return {
        "action": action,
        "actor_id": actor_id,
        "actor_type": actor_type,
        "detail": safe_detail,
        "occurred_at": occurred_at.isoformat(),
        "outcome": outcome,
        "prev_hash": prev_hash,
        "target_id": target_id,
        "target_type": target_type,
        "tenant_id": tenant_id,
        "tenant_seq": tenant_seq,
    }


def chain_hash(prev_hash: str, document: dict[str, JsonValue]) -> str:
    """``sha256(prev_hash || JCS(document))``."""
    digest = hashlib.sha256()
    digest.update(prev_hash.encode("ascii"))
    digest.update(canonical_json(document))
    return digest.hexdigest()
