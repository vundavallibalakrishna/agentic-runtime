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
        label = name.strip()
        if not label:
            raise ValidationFailedError("name is required")
        rows = _rows(text)
        catalogue_id = new_id()
        bucket(self.store, "grc_catalogues")[catalogue_id] = {
            "id": catalogue_id,
            "tenant_id": actor.tenant_id,
            "name": label,
            "created_at": utcnow(),
        }
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
            bucket(self.store, "grc_items")[item_id] = stored
            items.append(stored)
        return {"id": str(catalogue_id), "name": label, "items": len(items)}

    def items(self, actor: Actor, catalogue_id: uuid.UUID) -> list[dict[str, object]]:
        self._catalogue(actor, catalogue_id)
        return [
            row
            for row in bucket(self.store, "grc_items").values()
            if row.get("tenant_id") == actor.tenant_id and row.get("catalogue_id") == catalogue_id
        ]

    def link_evidence(
        self, actor: Actor, item_id: uuid.UUID, evidence_id: uuid.UUID, note: str = ""
    ) -> dict[str, object]:
        """Point a catalogue item at a sealed record. The record must exist."""
        item = self._item(actor, item_id)
        from records_pack.vault import EvidenceBook  # noqa: PLC0415

        EvidenceBook(self.store).get(actor, evidence_id)
        link_id = new_id()
        row = {
            "id": link_id,
            "tenant_id": actor.tenant_id,
            "item_id": item["id"],
            "evidence_id": evidence_id,
            "note": note.strip(),
        }
        bucket(self.store, "grc_evidence_links")[link_id] = row
        return {"id": str(link_id), "itemId": str(item_id), "evidenceId": str(evidence_id)}

    def add_risk(
        self, actor: Actor, title: str, score: int, status: str = "open"
    ) -> dict[str, object]:
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
        bucket(self.store, "grc_risks")[risk_id] = row
        return {"id": str(risk_id), "title": label, "score": score, "status": row["status"]}

    def add_finding(
        self, actor: Actor, title: str, item_key: str = "", status: str = "open"
    ) -> dict[str, object]:
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
        bucket(self.store, "grc_findings")[finding_id] = row
        return {"id": str(finding_id), "title": label, "itemKey": row["item_key"]}

    def judge(
        self, actor: Actor, catalogue_id: uuid.UUID, passages: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Judge each imported statement with the core document judge. No model is required."""
        rows = self.items(actor, catalogue_id)
        document = {"id": str(catalogue_id), "passages": passages}
        pairs = [(str(row["item_key"]), str(row["statement"])) for row in rows]
        return judge_items(
            document,
            pairs,
            None,
            model_id="none",
            rule_set_id=str(catalogue_id),
            rule_set_version="1",
        )

    def _catalogue(self, actor: Actor, catalogue_id: uuid.UUID) -> dict[str, object]:
        row = bucket(self.store, "grc_catalogues").get(catalogue_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _item(self, actor: Actor, item_id: uuid.UUID) -> dict[str, object]:
        row = bucket(self.store, "grc_items").get(item_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row


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
