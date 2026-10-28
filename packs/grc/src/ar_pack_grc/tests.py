"""Control tests and the results a CCM run records."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import one, owned, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_OUTCOMES = frozenset({"pass", "fail", "error"})


def list_tests(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.tests:read")
    body = snake_body(query)
    control_id = str(body.get("control_id") or "")
    items = []
    for row in owned(store, "grc_control_tests", actor):
        if control_id and str(row.get("control_id")) != control_id:
            continue
        items.append(_test_view(row))
    return {"items": items, "next_cursor": None, "has_more": False}


def create_test(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.controls:manage")
    body = snake_body(payload)
    control = one(store, "grc_controls", actor, _uuid(body.get("control_id")))
    key = str(body.get("key") or "").strip()
    procedure = str(body.get("procedure") or "").strip()
    schedule = str(body.get("schedule") or "").strip()
    if not key or not procedure or not schedule:
        raise ValidationFailedError("key, procedure and schedule are required")
    for row in bucket_rows(store, "grc_control_tests").values():
        if row.get("control_id") == control["id"] and row.get("key") == key:
            return _test_view(row)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "control_id": control["id"],
        "key": key,
        "procedure": procedure,
        "schedule": schedule,
        "freshness_days": _days(body.get("freshness_days")),
    }
    bucket_rows(store, "grc_control_tests")[item_id] = row
    record(store, actor, "grc.control.updated", item_id, {"key": key})
    return _test_view(row)


def patch_test(
    store: Any, actor: Actor, test_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.controls:manage")
    row = one(store, "grc_control_tests", actor, test_id)
    body = snake_body(payload)
    if "procedure" in body:
        procedure = str(body.get("procedure") or "").strip()
        if not procedure:
            raise ValidationFailedError("procedure is required")
        row["procedure"] = procedure
    if "schedule" in body:
        schedule = str(body.get("schedule") or "").strip()
        if not schedule:
            raise ValidationFailedError("schedule is required")
        row["schedule"] = schedule
    if "freshness_days" in body:
        row["freshness_days"] = _days(body.get("freshness_days"))
    record(store, actor, "grc.control.updated", test_id, {"patched": True})
    return _test_view(row)


def list_results(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.tests:read")
    body = snake_body(query)
    test_id = str(body.get("test_id") or "")
    outcome = str(body.get("outcome") or "")
    items = []
    for row in bucket_rows(store, "grc_test_results").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if test_id and str(row.get("test_id")) != test_id:
            continue
        if outcome and str(row.get("outcome")) != outcome:
            continue
        items.append(_result_view(row))
    items.sort(key=lambda item: str(item.get("created_at") or ""))
    return {"items": items, "next_cursor": None, "has_more": False}


def record_result(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    """Insert one result. The same run id does not insert a second row."""
    require(actor, "grc.tests:run")
    body = snake_body(payload)
    test = one(store, "grc_control_tests", actor, _uuid(body.get("test_id")))
    outcome = str(body.get("outcome") or "")
    if outcome not in _OUTCOMES:
        raise ValidationFailedError("outcome must be pass, fail or error")
    run_id = _optional_uuid(body.get("run_id"))
    if run_id is not None:
        for row in bucket_rows(store, "grc_test_results").values():
            if row.get("run_id") == run_id and row.get("test_id") == test["id"]:
                return _result_view(row)
    evidence_ids = _evidence_ids(body.get("evidence_item_ids"))
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "test_id": test["id"],
        "run_id": run_id,
        "run_record_id": None,
        "outcome": outcome,
        "evidence_item_id": evidence_ids[0] if evidence_ids else None,
        "detail": {
            "summary": str(body.get("summary") or ""),
            "evidence_item_ids": [str(item) for item in evidence_ids],
        },
        "created_at": utcnow(),
        "exception_id": _covering(store, actor, test.get("control_id")),
    }
    bucket_rows(store, "grc_test_results")[item_id] = row
    record(
        store,
        actor,
        "grc.test_result.recorded",
        item_id,
        {"outcome": outcome, "test_id": str(test["id"])},
    )
    return _result_view(row)


def _covering(store: Any, actor: Actor, control_id: object) -> uuid.UUID | None:
    from ar_pack_grc.exceptions import covering_exception  # noqa: PLC0415

    row = covering_exception(store, actor, control_id)
    if row is None:
        return None
    found = row.get("id")
    return found if isinstance(found, uuid.UUID) else None


def _test_view(row: dict[str, Any]) -> dict[str, Any]:
    return present(row)


def _result_view(row: dict[str, Any]) -> dict[str, Any]:
    item = present(row)
    detail = row.get("detail")
    if isinstance(detail, dict):
        item["summary"] = str(detail.get("summary") or "")
    return item


def _evidence_ids(value: object) -> list[uuid.UUID]:
    if value is None:
        return []
    if isinstance(value, str):
        parsed = _optional_uuid(value)
        return [parsed] if parsed is not None else []
    if not isinstance(value, list):
        raise ValidationFailedError("evidence_item_ids must be a list")
    found = []
    for item in value:
        parsed = _optional_uuid(item)
        if parsed is not None:
            found.append(parsed)
    return found


def _days(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValidationFailedError("freshness_days must be at least 1")
    try:
        days = int(value)
    except ValueError as exc:
        raise ValidationFailedError("freshness_days must be at least 1") from exc
    if days < 1:
        raise ValidationFailedError("freshness_days must be at least 1")
    return days


def _uuid(value: object) -> uuid.UUID:
    parsed = _optional_uuid(value)
    if parsed is None:
        raise ValidationFailedError("id is not a uuid")
    return parsed


def _optional_uuid(value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
