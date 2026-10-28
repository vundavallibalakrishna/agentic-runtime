"""BCP and DR tests. A failed outcome needs an evidence item."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.errors import ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_domain.records.memory import bucket
from ar_pack_grc.access import page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import as_uuid, choice, when

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_KINDS = frozenset({"bcp", "dr"})
_OUTCOMES = frozenset({"pass", "fail", "partial"})


def list_tests(store: Any, actor: Actor) -> dict[str, Any]:
    require(actor, "grc.controls:read")
    items = [
        present(row)
        for row in bucket_rows(store, "grc_resilience_tests").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return page(items)


def record_test(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.controls:manage")
    body = snake_body(payload)
    kind = choice(body.get("kind"), _KINDS, "kind")
    outcome = choice(body.get("outcome"), _OUTCOMES, "outcome")
    tested = when(body.get("tested_on"), required=True)
    evidence_id = as_uuid(body.get("evidence_item_id"), required=False)
    if outcome == "fail" and evidence_id is None:
        raise ValidationFailedError("evidence is required")
    if evidence_id is not None and not _evidence(store, actor, evidence_id):
        raise ValidationFailedError("evidence is required")
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "kind": kind,
        "tested_on": tested.date() if tested is not None else None,
        "outcome": outcome,
        "evidence_item_id": evidence_id,
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_resilience_tests")[item_id] = row
    record(store, actor, "grc.resilience.recorded", item_id, {"kind": kind, "outcome": outcome})
    return present(row)


def _evidence(store: Any, actor: Actor, evidence_id: object) -> bool:
    row = bucket(store, "evidence").get(evidence_id)
    return isinstance(row, dict) and same_tenant(row, actor.tenant_id)
