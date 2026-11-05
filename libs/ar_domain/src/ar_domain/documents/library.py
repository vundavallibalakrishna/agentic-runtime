"""Tenant document library. Extracted rows survive a restart. The bytes do not."""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING

from ar_common.errors import (
    ArError,
    ErrorCode,
    NotFoundError,
    PayloadTooLargeError,
    ValidationFailedError,
)
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.documents.chunk import passage_dicts
from ar_domain.documents.extract import Extracted, ExtractError, extract_bytes
from ar_domain.documents.grounding import (
    apply_hunks,
    check,
    compare,
    extract_fields,
    gaps,
    line_hunks,
    redaction_preview,
    requirements_from,
    rewrite_text,
    summarise,
)
from ar_domain.documents.model import ask_model
from ar_domain.files.logic import scan_bytes
from ar_domain.security.guardrails import analysis_redaction_enabled

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor

MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
_READ_CHARS = 12_000


class DocumentLibrary:
    """Ingest and read documents for one process. Postgres is updated on flush."""

    def __init__(self, store: Any) -> None:
        self.store = store
        self._ensure()

    def ingest(
        self,
        actor: Actor,
        *,
        data: bytes,
        filename: str,
        media_type: str = "",
        source: str = "upload",
        source_ref: str = "",
        ocr: Any = None,
        extracted: Extracted | None = None,
    ) -> dict[str, object]:
        if source not in {"upload", "workspace", "connection"}:
            raise ValidationFailedError("source must be upload, workspace or connection")
        if len(data) > MAX_DOCUMENT_BYTES:
            raise PayloadTooLargeError(
                f"The file is over the {MAX_DOCUMENT_BYTES // (1024 * 1024)} MB limit."
            )
        scanned = scan_bytes(data, scanner=str(getattr(self.store, "scanner", "none")))
        if scanned == "infected":
            self._audit(actor, "library_document.rejected", None, {"reason": "infected"}, "failure")
            raise ValidationFailedError("The file was rejected by the upload scanner.")
        digest = hashlib.sha256(data).hexdigest()
        existing = self._by_hash(actor.tenant_id, digest)
        if existing is not None:
            view = self._view(existing)
            view["deduped"] = True
            return view
        if extracted is None:
            try:
                extracted = extract_bytes(
                    data,
                    filename=filename or "upload",
                    media_type=media_type,
                    ocr=ocr,
                )
            except ExtractError as exc:
                self._audit(
                    actor,
                    "library_document.rejected",
                    None,
                    {"reason": exc.code, "filename": filename},
                    "failure",
                )
                raise _extract_error(exc) from exc
        elif not isinstance(extracted, Extracted):
            raise ValidationFailedError("The extraction could not be stored.")
        now = utcnow()
        document_id = new_id()
        row = {
            "id": document_id,
            "tenant_id": actor.tenant_id,
            "owner_user_id": actor.user_id,
            "title": extracted.title[:200],
            "filename": (filename or "upload")[:200],
            "media_type": extracted.media_type,
            "source": source,
            "source_ref": source_ref[:500],
            "content_hash": digest,
            "size_bytes": len(data),
            "status": "ready",
            "error_code": None,
            "error_message": None,
            "page_count": extracted.page_count,
            "metadata": extracted.metadata,
            "passages": passage_dicts(extracted.passages),
            "tables": [
                {
                    "anchor": table.anchor,
                    "page": table.page,
                    "caption": table.caption,
                    "csv": table.csv_text,
                }
                for table in extracted.tables
            ],
            "created_at": now,
            "updated_at": now,
        }
        self.store.library_documents[document_id] = row
        self._audit(actor, "library_document.ingested", document_id, {"filename": row["filename"]})
        return self._view(row)

    def list_items(self, actor: Actor) -> list[dict[str, object]]:
        rows = [
            self._view(row)
            for row in self.store.library_documents.values()
            if isinstance(row, dict) and row.get("tenant_id") == actor.tenant_id
        ]
        rows.sort(key=lambda item: str(item.get("title") or ""))
        return rows

    def get(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        return self._view(self._own(actor, document_id), detail=True)

    def passages(
        self, actor: Actor, document_id: uuid.UUID, *, page_from: int = 1, page_to: int = 0
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        pages = _rows(row.get("passages"))
        if page_to <= 0:
            page_count = row.get("page_count")
            count = int(page_count) if isinstance(page_count, int) else 1
            page_to = page_from + 4 if count > 30 else 10_000
        chosen = [item for item in pages if page_from <= int(str(item.get("page") or 1)) <= page_to]
        return {"document_id": str(document_id), "passages": chosen}

    def outline(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        row = self._own(actor, document_id)
        return {"document_id": str(document_id), "outline": _outline(row)}

    def tables(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        row = self._own(actor, document_id)
        return {"document_id": str(document_id), "tables": _rows(row.get("tables"))}

    def search(self, actor: Actor, query: str) -> list[dict[str, object]]:
        from ar_domain.documents.chunk import score  # noqa: PLC0415

        hits: list[dict[str, object]] = []
        for row in self.store.library_documents.values():
            if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
                continue
            for passage in _rows(row.get("passages")):
                weight = score(query, str(passage.get("text") or ""))
                if weight <= 0 and query.lower() not in str(passage.get("text") or "").lower():
                    continue
                if weight <= 0:
                    weight = 0.1
                text = str(passage.get("text") or "")
                hits.append(
                    {
                        "document_id": str(row.get("id")),
                        "title": row.get("title"),
                        "anchor": passage.get("anchor"),
                        "page": passage.get("page"),
                        "heading": passage.get("heading"),
                        "snippet": text[:240],
                        "score": round(weight, 2),
                    }
                )
        hits.sort(key=lambda item: float(str(item["score"])), reverse=True)
        return hits[:30]

    def read(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        *,
        page_from: int = 1,
        page_to: int = 0,
        anchor: str = "",
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        pages = _rows(row.get("passages"))
        if anchor:
            pages = [item for item in pages if str(item.get("anchor") or "") == anchor]
        elif page_to > 0:
            pages = [
                item for item in pages if page_from <= int(str(item.get("page") or 1)) <= page_to
            ]
        body: list[str] = []
        used = 0
        shown: list[dict[str, object]] = []
        for item in pages:
            text = str(item.get("text") or "")
            if used >= _READ_CHARS:
                break
            shown.append(item)
            body.append(
                f"[{item.get('anchor')} p.{item.get('page')} {item.get('heading')}]\n{text}"
            )
            used += len(text)
        return {
            "document_id": str(document_id),
            "title": row.get("title"),
            "passages": shown,
            "text": "\n\n".join(body)[:_READ_CHARS],
            "truncated": used >= _READ_CHARS,
        }

    def summarise(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        *,
        alias: str = "",
        agent_version_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        return summarise(
            row, self._ask(actor, alias), aggressive=self._aggressive(actor, agent_version_id)
        )

    def compare(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        other_id: uuid.UUID,
        *,
        alias: str = "",
        agent_version_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        left = self._own(actor, document_id)
        right = self._own(actor, other_id)
        result = compare(
            left,
            right,
            self._ask(actor, alias),
            aggressive=self._aggressive(actor, agent_version_id),
        )
        comparison_id = new_id()
        now = utcnow()
        self.store.document_comparisons[comparison_id] = {
            "id": comparison_id,
            "tenant_id": actor.tenant_id,
            "left_id": document_id,
            "right_id": other_id,
            "changes": result,
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        result["id"] = str(comparison_id)
        return result

    def check(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        *,
        requirements: list[str],
        standard_id: uuid.UUID | None = None,
        label: str = "",
        alias: str = "",
        agent_version_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        items = [item.strip() for item in requirements if item.strip()]
        if standard_id is not None:
            items.extend(requirements_from(self._own(actor, standard_id)))
        if not items:
            raise ValidationFailedError("Provide a standard document or a list of requirements.")
        result = check(
            row,
            items[:40],
            self._ask(actor, alias),
            label=label,
            aggressive=self._aggressive(actor, agent_version_id),
        )
        check_id = new_id()
        now = utcnow()
        self.store.document_checks[check_id] = {
            "id": check_id,
            "tenant_id": actor.tenant_id,
            "document_id": document_id,
            "standard_document_id": standard_id,
            "label": label or "Check",
            "rows": result,
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        result["id"] = str(check_id)
        return result

    def gaps(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        *,
        requirements: list[str],
        standard_id: uuid.UUID | None = None,
        alias: str = "",
        agent_version_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        items = [item.strip() for item in requirements if item.strip()]
        if standard_id is not None:
            items.extend(requirements_from(self._own(actor, standard_id)))
        return gaps(
            row,
            items[:40],
            self._ask(actor, alias),
            aggressive=self._aggressive(actor, agent_version_id),
        )

    def redact(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        row = self._own(actor, document_id)
        text = "\n".join(str(item.get("text") or "") for item in _rows(row.get("passages")))
        preview = redaction_preview(text[:20_000])
        preview["document_id"] = str(document_id)
        return preview

    def extract(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        fields: list[str],
        *,
        alias: str = "",
        agent_version_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        if not fields:
            raise ValidationFailedError("Name at least one field.")
        row = self._own(actor, document_id)
        return extract_fields(
            row,
            fields[:20],
            self._ask(actor, alias),
            aggressive=self._aggressive(actor, agent_version_id),
        )

    def propose_rewrite(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        *,
        anchor: str,
        instruction: str,
        alias: str = "",
        agent_version_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        if not instruction.strip():
            raise ValidationFailedError("Say how the passage should change.")
        row = self._own(actor, document_id)
        passages = _rows(row.get("passages"))
        if anchor:
            chosen = [item for item in passages if str(item.get("anchor") or "") == anchor]
            if not chosen:
                raise NotFoundError()
        else:
            chosen = passages[:8]
            anchor = ""
        original = "\n\n".join(str(item.get("text") or "") for item in chosen)[:12_000]
        proposed = rewrite_text(
            original,
            instruction,
            self._ask(actor, alias),
            aggressive=self._aggressive(actor, agent_version_id),
        )
        hunks = line_hunks(original, proposed)
        rewrite_id = new_id()
        now = utcnow()
        saved = {
            "id": rewrite_id,
            "tenant_id": actor.tenant_id,
            "document_id": document_id,
            "anchor": anchor,
            "passage_anchors": [str(item.get("anchor") or "") for item in chosen],
            "instruction": instruction[:500],
            "original": original,
            "proposed": proposed,
            "hunks": hunks,
            "status": "proposed",
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self.store.document_rewrites[rewrite_id] = saved
        self._audit(
            actor, "document_rewrite.proposed", rewrite_id, {"document_id": str(document_id)}
        )
        return _rewrite_view(saved)

    def decide_rewrite(
        self,
        actor: Actor,
        rewrite_id: uuid.UUID,
        *,
        decision: str,
        hunk_id: str = "",
    ) -> dict[str, object]:
        row = self._rewrite(actor, rewrite_id)
        if row.get("status") != "proposed":
            raise ValidationFailedError("This rewrite has already been reviewed.")
        if decision not in {"accept", "reject"}:
            raise ValidationFailedError("decision must be accept or reject")
        hunks = [dict(item) for item in _rows(row.get("hunks"))]
        targets = hunks if not hunk_id else [item for item in hunks if item.get("id") == hunk_id]
        if hunk_id and not targets:
            raise NotFoundError()
        for item in targets:
            item["decision"] = decision
        row["hunks"] = hunks
        pending = [item for item in hunks if not item.get("decision")]
        if pending:
            row["updated_at"] = utcnow()
            return _rewrite_view(row)
        accepted = any(item.get("decision") == "accept" for item in hunks)
        if accepted:
            updated = apply_hunks(str(row.get("original") or ""), hunks)
            self._apply_text(actor, row, updated)
            row["status"] = "accepted"
            action = "document_rewrite.accepted"
        else:
            row["status"] = "rejected"
            action = "document_rewrite.rejected"
        row["updated_at"] = utcnow()
        self._audit(actor, action, rewrite_id, {"document_id": str(row.get("document_id"))})
        return _rewrite_view(row)

    def get_check(self, actor: Actor, check_id: uuid.UUID) -> dict[str, object]:
        row = self.store.document_checks.get(check_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        body = row.get("rows")
        result = dict(body) if isinstance(body, dict) else {}
        result["id"] = str(check_id)
        result["label"] = row.get("label")
        return result

    def get_comparison(self, actor: Actor, comparison_id: uuid.UUID) -> dict[str, object]:
        row = self.store.document_comparisons.get(comparison_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        body = row.get("changes")
        result = dict(body) if isinstance(body, dict) else {}
        result["id"] = str(comparison_id)
        return result

    def get_rewrite(self, actor: Actor, rewrite_id: uuid.UUID) -> dict[str, object]:
        return _rewrite_view(self._rewrite(actor, rewrite_id))

    def _apply_text(self, actor: Actor, rewrite: dict[str, object], updated: str) -> None:
        document_id = rewrite.get("document_id")
        if not isinstance(document_id, uuid.UUID):
            return
        document = self._own(actor, document_id)
        anchors = rewrite.get("passage_anchors")
        wanted = set(anchors) if isinstance(anchors, list) else set()
        passages = _rows(document.get("passages"))
        placed = False
        rewritten: list[dict[str, object]] = []
        for item in passages:
            anchor = str(item.get("anchor") or "")
            if anchor not in wanted:
                rewritten.append(item)
                continue
            if not placed:
                copied = dict(item)
                copied["text"] = updated
                rewritten.append(copied)
                placed = True
        if not placed:
            passages.append(
                {
                    "anchor": "p1-s0",
                    "page": 1,
                    "heading": str(document.get("title") or "Document"),
                    "level": 1,
                    "text": updated,
                }
            )
            document["passages"] = passages
        else:
            document["passages"] = rewritten
        document["updated_at"] = utcnow()

    def _aggressive(self, actor: Actor, agent_version_id: uuid.UUID | None) -> bool:
        return analysis_redaction_enabled(self.store, actor.tenant_id, agent_version_id)

    def _ask(self, actor: Actor, alias: str) -> Any:
        chosen = alias or "reasoning"

        def ask(task: str, evidence: str) -> str | None:
            return ask_model(self.store, actor.tenant_id, chosen, task, evidence)

        return ask

    def _own(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        row = self.store.library_documents.get(document_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _rewrite(self, actor: Actor, rewrite_id: uuid.UUID) -> dict[str, object]:
        row = self.store.document_rewrites.get(rewrite_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _by_hash(self, tenant_id: uuid.UUID, digest: str) -> dict[str, object] | None:
        for row in self.store.library_documents.values():
            if (
                isinstance(row, dict)
                and row.get("tenant_id") == tenant_id
                and row.get("content_hash") == digest
                and row.get("status") == "ready"
            ):
                return row
        return None

    def _ensure(self) -> None:
        for name in (
            "library_documents",
            "document_checks",
            "document_comparisons",
            "document_rewrites",
        ):
            if not isinstance(getattr(self.store, name, None), dict):
                setattr(self.store, name, {})

    def _view(self, row: dict[str, object], *, detail: bool = False) -> dict[str, object]:
        passages = _rows(row.get("passages"))
        preview = "\n".join(str(item.get("text") or "") for item in passages[:2])[:800]
        body = {
            "id": str(row.get("id")),
            "title": row.get("title"),
            "filename": row.get("filename"),
            "media_type": row.get("media_type"),
            "source": row.get("source"),
            "source_ref": row.get("source_ref"),
            "content_hash": row.get("content_hash"),
            "size_bytes": row.get("size_bytes"),
            "status": row.get("status"),
            "page_count": row.get("page_count"),
            "created_at": _iso(row.get("created_at")),
            "deduped": False,
        }
        if detail:
            body["outline"] = _outline(row)
            body["preview"] = preview
            body["table_count"] = len(_rows(row.get("tables")))
        return body

    def _audit(
        self,
        actor: Actor,
        action: str,
        target_id: uuid.UUID | None,
        detail: dict[str, object],
        outcome: str = "success",
    ) -> None:
        log = getattr(self.store, "audit_log", None)
        if not isinstance(log, list):
            return
        log.append(
            {
                "tenant_id": str(actor.tenant_id),
                "actor_id": str(actor.user_id),
                "action": action,
                "target_type": "library_document",
                "target_id": "" if target_id is None else str(target_id),
                "detail": detail,
                "outcome": outcome,
                "at": utcnow().isoformat(),
            }
        )


def _extract_error(exc: ExtractError) -> ArError:
    if exc.code == "unsupported":
        return ArError(ErrorCode.UNSUPPORTED_MEDIA_TYPE, exc.message)
    if exc.code == "too_many_pages":
        return PayloadTooLargeError(exc.message)
    return ValidationFailedError(exc.message)


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _outline(row: dict[str, object]) -> list[dict[str, object]]:
    seen: set[str] = set()
    items: list[dict[str, object]] = []
    for passage in _rows(row.get("passages")):
        anchor = str(passage.get("anchor") or "")
        heading = str(passage.get("heading") or "")
        key = f"{heading}:{anchor.split('-', maxsplit=1)[0]}"
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "anchor": anchor,
                "page": passage.get("page"),
                "heading": heading,
                "level": passage.get("level"),
            }
        )
    return items


def _rewrite_view(row: dict[str, object]) -> dict[str, object]:
    return {
        "kind": "rewrite",
        "id": str(row.get("id")),
        "document_id": str(row.get("document_id")),
        "anchor": row.get("anchor"),
        "instruction": row.get("instruction"),
        "status": row.get("status"),
        "hunks": _rows(row.get("hunks")),
        "original": row.get("original"),
        "proposed": row.get("proposed"),
    }


def _iso(value: object) -> str:
    if value is None:
        return ""
    return str(value)
