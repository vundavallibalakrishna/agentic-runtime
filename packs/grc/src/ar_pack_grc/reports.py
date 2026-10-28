"""Report templates render through the core binder. The SoA lists control ids only."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from ar_common.errors import ArError, ErrorCode
from ar_domain.records.access import require
from ar_domain.records.binders import BinderBook
from ar_domain.records.memory import bucket
from ar_pack_grc.access import record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.values import choice

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

TEMPLATES = ("soa", "soc2_binder", "cscrf", "dpdp_breach", "board_pack")
_LICENSED = ("the organization shall", "the entity shall")


def list_templates(store: Any, actor: Actor) -> dict[str, Any]:
    del store
    require(actor, "grc.reports:export")
    return {"items": [{"key": key} for key in TEMPLATES]}


def render(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.reports:export")
    body = snake_body(payload)
    template = choice(body.get("template"), frozenset(TEMPLATES), "template")
    raw_params = body.get("params")
    params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
    selection = _selection(store, actor, template, params)
    title = template.replace("_", " ")
    book = BinderBook(store)
    if template == "board_pack":
        return _board(store, actor, book, title, selection)
    created = book.create(actor, {"title": title, "selection": selection})
    binder_id = _uuid(created.get("id"))
    built = book.build(actor, binder_id)
    record(store, actor, "grc.report.exported", binder_id, {"template": template})
    return {"binder_id": built.get("id"), "status": built.get("status"), "template": template}


def sample_size(population: int) -> int:
    """CSCRF sampling: the whole population up to 25, otherwise at least 25 percent."""
    if population <= 25:
        return population
    return max(1, math.ceil(population * 0.25))


def _board(
    store: Any,
    actor: Actor,
    book: BinderBook,
    title: str,
    selection: dict[str, object],
) -> dict[str, Any]:
    created = book.create(actor, {"title": title, "selection": selection, "require_review": True})
    binder_id = _uuid(created.get("id"))
    try:
        book.build(actor, binder_id)
    except ArError as exc:
        if exc.code is not ErrorCode.REVIEW_REQUIRED:
            raise
    saved = bucket(store, "binders").get(binder_id)
    status = saved.get("status") if isinstance(saved, dict) else "pending_review"
    record(store, actor, "grc.report.exported", binder_id, {"template": "board_pack"})
    return {"binder_id": binder_id, "status": status, "template": "board_pack"}


def _selection(
    store: Any, actor: Actor, template: str, params: dict[str, Any]
) -> dict[str, object]:
    keys = _control_ids(store, actor)
    if template == "soa":
        return {"control_ids": keys}
    population = len(keys)
    raw = params.get("population")
    if isinstance(raw, int) and not isinstance(raw, bool):
        population = raw
    size = sample_size(population)
    lines = [
        f"population={population}",
        f"sample={size}",
        "method=cscrf" if template == "cscrf" else f"method={template}",
    ]
    return {"control_ids": keys, "notes": _plain(lines)}


def _control_ids(store: Any, actor: Actor) -> list[str]:
    keys = [
        str(row.get("key") or row.get("id") or "")
        for row in bucket_rows(store, "grc_controls").values()
        if same_tenant(row, actor.tenant_id)
    ]
    return _plain([key for key in keys if key])


def _plain(values: list[str]) -> list[str]:
    """Drop licensed statement text. Control ids and counts stay."""
    kept = []
    for value in values:
        lowered = value.lower()
        if any(phrase in lowered for phrase in _LICENSED):
            continue
        kept.append(value)
    return kept


def _uuid(value: object) -> uuid.UUID:
    import uuid as uuid_mod  # noqa: PLC0415

    if isinstance(value, uuid_mod.UUID):
        return value
    return uuid_mod.UUID(str(value))
