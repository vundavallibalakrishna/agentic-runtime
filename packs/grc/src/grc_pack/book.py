"""Customer-imported catalogues, evidence links, risks and findings.

Statements are the customer's own words. This pack does not ship framework text.
Rows live in the process store, the same way the records pack does. The SQL
under migrations/ is the reversible Postgres shape.
"""

from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING, Any

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.documents.judgement import judge_items
from ar_domain.records.access import audit, require
from ar_domain.records.memory import bucket

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_HEADERS = ("key", "title", "statement")


class CatalogueBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def import_csv(self, actor: Actor, name: str, text: str) -> dict[str, object]:
        """Import a catalogue from CSV. Columns are key, title, statement."""
        require(actor, "grc.catalogues:manage")
        label = name.strip()
        if not label:
            raise ValidationFailedError("name is required")
        rows = _rows(text)
        catalogue_id = new_id()
        catalogue = {
            "id": catalogue_id,
            "tenant_id": actor.tenant_id,
            "name": label,
            "created_at": utcnow(),
        }
        _put(self.store, "catalogues", catalogue)
        items: list[dict[str, object]] = []
        for row in rows:
            item_id = new_id()
            stored = {
                "id": item_id,
                "tenant_id": actor.tenant_id,
                "catalogue_id": catalogue_id,
                "item_key": row["key"],
                "title": row["title"],
                "statement": row["statement"],
            }
            _put(self.store, "items", stored)
            items.append(stored)
        audit(
            self.store,
            actor,
            "grc.catalogue.imported",
            "grc_catalogue",
            catalogue_id,
            {"name": label, "items": len(items)},
        )
        return {"id": str(catalogue_id), "name": label, "items": len(items)}

    def list_catalogues(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "grc.catalogues:manage")
        return _scan(self.store, "catalogues", actor.tenant_id)

    def items(self, actor: Actor, catalogue_id: uuid.UUID) -> list[dict[str, object]]:
        require(actor, "grc.catalogues:manage")
        self._catalogue(actor, catalogue_id)
        return [
            row
            for row in _scan(self.store, "items", actor.tenant_id)
            if row.get("catalogue_id") == catalogue_id
        ]

    def link_evidence(
        self, actor: Actor, item_id: uuid.UUID, evidence_id: uuid.UUID, note: str = ""
    ) -> dict[str, object]:
        """Point a catalogue item at a sealed record. The record must exist."""
        require(actor, "grc.evidence:link")
        item = self._item(actor, item_id)
        evidence = bucket(self.store, "evidence").get(evidence_id)
        if not isinstance(evidence, dict) or evidence.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        link_id = new_id()
        row = {
            "id": link_id,
            "tenant_id": actor.tenant_id,
            "item_id": item["id"],
            "evidence_id": evidence_id,
            "note": note.strip(),
        }
        _put(self.store, "evidence_links", row)
        audit(
            self.store,
            actor,
            "grc.evidence.linked",
            "grc_evidence_link",
            link_id,
            {"itemId": str(item_id), "evidenceId": str(evidence_id)},
        )
        return {"id": str(link_id), "itemId": str(item_id), "evidenceId": str(evidence_id)}

    def add_risk(
        self, actor: Actor, title: str, score: int, status: str = "open"
    ) -> dict[str, object]:
        require(actor, "grc.risks:manage")
        label = title.strip()
        if not label:
            raise ValidationFailedError("title is required")
        if score < 0 or score > 100:
            raise ValidationFailedError("score must be from 0 to 100")
        risk_id = new_id()
        row = {
            "id": risk_id,
            "tenant_id": actor.tenant_id,
            "title": label,
            "score": score,
            "status": status.strip() or "open",
        }
        _put(self.store, "risks", row)
        audit(self.store, actor, "grc.risk.added", "grc_risk", risk_id, {"title": label})
        return {"id": str(risk_id), "title": label, "score": score, "status": row["status"]}

    def add_finding(
        self, actor: Actor, title: str, item_key: str = "", status: str = "open"
    ) -> dict[str, object]:
        require(actor, "grc.findings:manage")
        label = title.strip()
        if not label:
            raise ValidationFailedError("title is required")
        finding_id = new_id()
        row = {
            "id": finding_id,
            "tenant_id": actor.tenant_id,
            "title": label,
            "item_key": item_key.strip(),
            "status": status.strip() or "open",
        }
        _put(self.store, "findings", row)
        audit(self.store, actor, "grc.finding.added", "grc_finding", finding_id, {"title": label})
        return {"id": str(finding_id), "title": label, "itemKey": row["item_key"]}

    def judge(
        self, actor: Actor, catalogue_id: uuid.UUID, passages: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Judge each imported statement with the core document judge. No model is required."""
        rows = self.items(actor, catalogue_id)
        document: dict[str, object] = {"id": str(catalogue_id), "passages": passages}
        pairs = [(str(row["item_key"]), str(row["statement"])) for row in rows]
        return judge_items(
            document,
            pairs,
            None,
            model_id="none",
            rule_set_id=str(catalogue_id),
            rule_set_version="1",
        )

    def list_risks(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "grc.risks:manage")
        return _scan(self.store, "risks", actor.tenant_id)

    def update_risk(
        self,
        actor: Actor,
        risk_id: uuid.UUID,
        *,
        title: str | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        require(actor, "grc.risks:manage")
        row = _one(self.store, "risks", actor.tenant_id, risk_id)
        if title is not None and title.strip():
            row["title"] = title.strip()
        if status is not None and status.strip():
            row["status"] = status.strip()
        _put(self.store, "risks", row)
        audit(self.store, actor, "grc.risk.updated", "grc_risk", risk_id, {})
        return {"id": str(risk_id), "title": row["title"], "status": row["status"]}

    def list_findings(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "grc.findings:manage")
        return _scan(self.store, "findings", actor.tenant_id)

    def update_finding(
        self,
        actor: Actor,
        finding_id: uuid.UUID,
        *,
        title: str | None = None,
        status: str | None = None,
    ) -> dict[str, object]:
        require(actor, "grc.findings:manage")
        row = _one(self.store, "findings", actor.tenant_id, finding_id)
        if title is not None and title.strip():
            row["title"] = title.strip()
        if status is not None and status.strip():
            row["status"] = status.strip()
        _put(self.store, "findings", row)
        audit(self.store, actor, "grc.finding.updated", "grc_finding", finding_id, {})
        return {"id": str(finding_id), "title": row["title"], "status": row["status"]}

    def _catalogue(self, actor: Actor, catalogue_id: uuid.UUID) -> dict[str, object]:
        return _one(self.store, "catalogues", actor.tenant_id, catalogue_id)

    def _item(self, actor: Actor, item_id: uuid.UUID) -> dict[str, object]:
        return _one(self.store, "items", actor.tenant_id, item_id)


def _table(store: Any) -> dict[object, dict[str, object]]:
    rows = getattr(store, "extension_rows", None)
    if not isinstance(rows, dict):
        rows = {}
        store.extension_rows = rows
    return rows


def _put(store: Any, name: str, row: dict[str, object]) -> None:
    _table(store)[row["id"]] = {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "pack_id": "grc",
        "bucket": name,
        "payload": row,
    }


def _scan(store: Any, name: str, tenant_id: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for item in _table(store).values():
        if item.get("pack_id") != "grc" or item.get("bucket") != name:
            continue
        if item.get("tenant_id") != tenant_id:
            continue
        payload = item.get("payload")
        if isinstance(payload, dict):
            found.append(payload)
    return found


def _one(store: Any, name: str, tenant_id: object, row_id: uuid.UUID) -> dict[str, object]:
    item = _table(store).get(row_id)
    payload = item.get("payload") if isinstance(item, dict) else None
    if (
        not isinstance(item, dict)
        or item.get("pack_id") != "grc"
        or item.get("bucket") != name
        or item.get("tenant_id") != tenant_id
        or not isinstance(payload, dict)
    ):
        raise NotFoundError()
    return payload


def _rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or tuple(name.strip() for name in reader.fieldnames) != _HEADERS:
        raise ValidationFailedError("csv columns must be key, title, statement")
    found: list[dict[str, str]] = []
    for raw in reader:
        row = {key: str(raw.get(key) or "").strip() for key in _HEADERS}
        if not row["key"] or not row["statement"]:
            raise ValidationFailedError("each row needs a key and a statement")
        found.append(row)
    if not found:
        raise ValidationFailedError("the catalogue has no rows")
    return found
