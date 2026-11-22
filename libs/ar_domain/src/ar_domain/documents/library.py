"""Tenant document library.

Original bytes live in the object store under the row's key. The row keeps the
sha256 and the derived passages. Retrieval and citations point at those passages.
"""

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
from ar_common.settings import get_settings
from ar_common.time import utcnow
from ar_domain.documents.chunk import passage_dicts, retrieve, score
from ar_domain.documents.extract import Extracted, ExtractError
from ar_domain.documents.layout import parse_layout
from ar_domain.documents.model import ModelAsk
from ar_domain.documents.originals import read_original, store_original
from ar_domain.files.logic import scan_bytes

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor


def max_document_bytes() -> int:
    """The configured upload cap. A larger file is refused with its size."""
    return int(get_settings().document_max_bytes)


def _holds_hash(files: object, document: dict[str, object], digest: str | set[str]) -> bool:
    """Whether this knowledge document is the named bytes.

    ``files`` is keyed by id. The document names one file, or carries the hash
    itself. Neither path walks the file table.
    """
    wanted = {digest} if isinstance(digest, str) else digest
    version = str(document.get("version_hash") or "")
    if version and version in wanted:
        return True
    file_id = document.get("raw_file_id")
    meta = files.get(file_id) if isinstance(files, dict) else None
    if not isinstance(meta, dict) or meta.get("deleted_at"):
        return False
    return str(meta.get("sha256") or "") in wanted


def _quality(extracted: Extracted) -> dict[str, object]:
    """The extract's own metadata plus the read-quality record."""
    from ar_domain.documents.quality import quality_record  # noqa: PLC0415

    pages = extracted.metadata.get("pagesOcr")
    record = quality_record(
        page_count=extracted.page_count,
        passages=list(extracted.passages),
        tables=list(extracted.tables),
        pages_ocr=pages if isinstance(pages, int) and not isinstance(pages, bool) else 0,
        engine=str(extracted.metadata.get("ocrEngine") or "none"),
    )
    return {**extracted.metadata, **record}


async def ingest_bytes(
    store: Any,
    actor: Actor,
    *,
    data: bytes,
    filename: str,
    media_type: str = "",
    source: str = "upload",
) -> dict[str, object]:
    """Store ``data`` once per tenant. A second upload of the same bytes returns the first."""
    library = DocumentLibrary(store)
    digest = hashlib.sha256(data).hexdigest()
    existing = library._by_hash(actor.tenant_id, digest)
    if existing is None:
        loaded = await _load_library_hash(store, actor.tenant_id, digest)
        if loaded is not None:
            _install_library_row(store, loaded)
            existing = library._by_hash(actor.tenant_id, digest)
    if existing is not None:
        if not existing.get("object_key"):
            existing["object_key"] = store_original(
                store,
                tenant_id=actor.tenant_id,
                document_id=_as_uuid(existing.get("id")) or new_id(),
                data=data,
                media_type=str(existing.get("media_type") or media_type),
            )
        view = library._view(existing)
        view["deduped"] = True
        return view
    client = getattr(store, "temporal_client", None)
    # A connected worker parses. A process with no database still parses here,
    # with the fallback reader when Docling is not installed.
    if (
        client is not None
        and getattr(store, "durable_engine", None) is not None
        and hasattr(client, "start_workflow")
        and not getattr(store, "_ingest_worker", False)
    ):
        return await _parse_on_worker(
            store,
            actor,
            client,
            data=data,
            filename=filename,
            media_type=media_type,
            source=source,
        )
    return library.ingest(actor, data=data, filename=filename, media_type=media_type, source=source)


async def _parse_on_worker(
    store: Any,
    actor: Actor,
    client: Any,
    *,
    data: bytes,
    filename: str,
    media_type: str,
    source: str,
) -> dict[str, object]:
    """Store the bytes and let the ingest worker parse them. The API does not."""
    from ar_domain.durable.flush import flush_store  # noqa: PLC0415
    from ar_domain.durable.waiting import WORKER_WAIT_S, worker_result  # noqa: PLC0415

    library = DocumentLibrary(store)
    staged = library.ingest(
        actor,
        data=data,
        filename=filename,
        media_type=media_type,
        source=source,
        defer_parse=True,
    )
    await flush_store(store)
    document_id = str(staged.get("id") or "")
    handle = await client.start_workflow(
        "LibraryParseWorkflow",
        {"document_id": document_id, "tenant_id": str(actor.tenant_id)},
        id=f"library-parse-{document_id}",
        task_queue="ar-ingest",
    )
    finished, answer = await worker_result(handle, WORKER_WAIT_S)
    if not finished:
        # The worker is still reading. The row says so, and the worker finishes it.
        return staged
    if isinstance(answer, dict) and answer.get("status") == "failed":
        raise ArError(ErrorCode(str(answer.get("code"))), str(answer.get("message") or ""))
    loaded = await _load_library_id(store, actor.tenant_id, document_id)
    if loaded is None:
        return staged
    _install_library_row(store, loaded)
    return library._view(loaded)


async def _load_library_id(
    store: Any, tenant_id: uuid.UUID, document_id: str
) -> dict[str, object] | None:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession  # noqa: PLC0415

    engine = getattr(store, "durable_engine", None)
    if not isinstance(engine, AsyncEngine):
        row = store.library_documents.get(_as_uuid(document_id))
        return row if isinstance(row, dict) else None
    from sqlalchemy import text  # noqa: PLC0415

    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        found = await session.execute(
            text("SELECT * FROM documents WHERE tenant_id = :tenant_id AND id = :id"),
            {"tenant_id": tenant_id, "id": document_id},
        )
        row = found.mappings().first()
    if row is None:
        return None
    from ar_domain.durable.m24 import library_view  # noqa: PLC0415

    return library_view({str(key): row[key] for key in row})


async def _load_library_hash(
    store: Any, tenant_id: uuid.UUID, digest: str
) -> dict[str, object] | None:
    """The durable row for this hash, when this process has a database and no copy yet."""
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession  # noqa: PLC0415

    engine = getattr(store, "durable_engine", None)
    if not isinstance(engine, AsyncEngine) or not digest:
        return None
    from sqlalchemy import text  # noqa: PLC0415

    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": str(tenant_id)},
        )
        found = await session.execute(
            text(
                "SELECT * FROM documents "
                "WHERE tenant_id = :tenant_id AND content_hash = :content_hash "
                "AND content_hash <> ''"
            ),
            {"tenant_id": tenant_id, "content_hash": digest},
        )
        row = found.mappings().first()
    if row is None:
        return None
    from ar_domain.durable.m24 import library_view  # noqa: PLC0415

    return library_view({str(key): row[key] for key in row})


def _install_library_row(store: Any, row: dict[str, object]) -> None:
    documents = getattr(store, "library_documents", None)
    if not isinstance(documents, dict):
        return
    was = getattr(store, "reloading", False)
    store.reloading = True
    try:
        documents[row["id"]] = row
    finally:
        store.reloading = was
    dirty = getattr(documents, "dirty", None)
    if isinstance(dirty, set):
        dirty.discard(row["id"])


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
        defer_parse: bool = False,
    ) -> dict[str, object]:
        if source not in {"upload", "workspace", "connection"}:
            raise ValidationFailedError("source must be upload, workspace or connection")
        cap = max_document_bytes()
        if len(data) > cap:
            raise PayloadTooLargeError(f"The file is over the {cap // (1024 * 1024)} MB limit.")
        scanned = scan_bytes(
            data,
            scanner=str(getattr(self.store, "scanner", "none")),
            address=getattr(self.store, "clamav_address", None),
        )
        if scanned == "infected":
            self._audit(actor, "library_document.rejected", None, {"reason": "infected"}, "failure")
            raise ValidationFailedError("The file was rejected by the upload scanner.")
        if scanned == "error":
            self._audit(
                actor, "library_document.rejected", None, {"reason": "scan_error"}, "failure"
            )
            raise ArError(
                ErrorCode.UNAVAILABLE,
                "The malware scanner did not answer. The upload was rejected.",
            )
        digest = hashlib.sha256(data).hexdigest()
        existing = self._by_hash(actor.tenant_id, digest)
        if existing is not None:
            if not existing.get("object_key"):
                existing["object_key"] = store_original(
                    self.store,
                    tenant_id=actor.tenant_id,
                    document_id=_as_uuid(existing.get("id")) or new_id(),
                    data=data,
                    media_type=str(existing.get("media_type") or media_type),
                )
            view = self._view(existing)
            view["deduped"] = True
            return view
        if defer_parse:
            extracted = Extracted(
                title=(filename or "upload")[: int(get_settings().document_create_max_title)],
                media_type=media_type or "application/octet-stream",
                page_count=0,
            )
        elif extracted is None:
            try:
                extracted = parse_layout(
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
        title_cap = int(get_settings().document_create_max_title)
        ref_cap = int(get_settings().document_source_ref_chars)
        object_key = store_original(
            self.store,
            tenant_id=actor.tenant_id,
            document_id=document_id,
            data=data,
            media_type=extracted.media_type or media_type,
        )
        row = {
            "id": document_id,
            "tenant_id": actor.tenant_id,
            "owner_user_id": actor.user_id,
            "title": extracted.title[:title_cap],
            "filename": (filename or "upload")[:title_cap],
            "media_type": extracted.media_type,
            "source": source,
            "source_ref": source_ref[:ref_cap],
            "content_hash": digest,
            "object_key": object_key,
            "size_bytes": len(data),
            "status": "parsing" if defer_parse else "ready",
            "error_code": None,
            "error_message": None,
            "page_count": extracted.page_count,
            "metadata": _quality(extracted),
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

    def finish_parse(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        """Fill a staged row from the layout parser. The original bytes are already stored."""
        row = self._own(actor, document_id)
        data = read_original(self.store, str(row.get("object_key") or ""))
        if data is None:
            raise NotFoundError()
        try:
            extracted = parse_layout(
                data,
                filename=str(row.get("filename") or "upload"),
                media_type=str(row.get("media_type") or ""),
            )
        except ExtractError as exc:
            row["status"] = "failed"
            row["error_code"] = exc.code
            row["error_message"] = exc.message
            raise _extract_error(exc) from exc
        cap = int(get_settings().document_create_max_title)
        row["title"] = extracted.title[:cap]
        row["media_type"] = extracted.media_type or row.get("media_type")
        row["page_count"] = extracted.page_count
        row["metadata"] = _quality(extracted)
        row["passages"] = passage_dicts(extracted.passages)
        row["tables"] = [
            {
                "anchor": table.anchor,
                "page": table.page,
                "caption": table.caption,
                "csv": table.csv_text,
            }
            for table in extracted.tables
        ]
        row["status"] = "ready"
        row["error_code"] = None
        row["error_message"] = None
        row["updated_at"] = utcnow()
        return self._view(row)

    def list_items(
        self,
        actor: Actor,
        *,
        scope: str = "library",
        run: dict[str, object] | None = None,
        cursor: str = "",
    ) -> dict[str, object]:
        """Documents in one scope. A later page is ``nextCursor``, never a silent cut."""
        rows = [row for row in self._scoped(actor, scope, run) if self._visible(actor, row)]
        rows.sort(key=lambda item: str(item.get("title") or ""))
        start = _cursor_index(cursor)
        cap = int(get_settings().document_search_hits)
        page = rows[start : start + cap]
        nxt = f"o:{start + cap}" if start + cap < len(rows) else ""
        return {
            "documents": [self._view(row) for row in page],
            "nextCursor": nxt,
            "total": len(rows),
        }

    def get(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        return self._view(self._own(actor, document_id), detail=True)

    def passages(
        self, actor: Actor, document_id: uuid.UUID, *, page_from: int = 1, page_to: int = 0
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        pages = _rows(row.get("passages"))
        if page_to <= 0:
            page_count = row.get("page_count")
            count = (
                int(page_count)
                if isinstance(page_count, int) and not isinstance(page_count, bool)
                else 1
            )
            span = int(get_settings().document_heading_cap)
            page_to = page_from + span - 1 if count > span else count
        chosen = [item for item in pages if page_from <= int(str(item.get("page") or 1)) <= page_to]
        nxt = page_to + 1 if page_to < int(str(row.get("page_count") or page_to)) else 0
        return {
            "document_id": str(document_id),
            "passages": chosen,
            "nextPage": nxt or None,
        }

    def outline(
        self, actor: Actor, document_id: uuid.UUID, *, cursor: str = ""
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        items = _outline(row)
        start = _cursor_index(cursor)
        cap = int(get_settings().document_heading_cap)
        page = items[start : start + cap]
        nxt = f"o:{start + cap}" if start + cap < len(items) else ""
        return {
            "document_id": str(document_id),
            "outline": page,
            "nextCursor": nxt,
            "total": len(items),
        }

    def tables(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        *,
        table: str = "",
        offset: int = 0,
        limit: int = 0,
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        tables = _rows(row.get("tables"))
        if table:
            tables = [
                item
                for item in tables
                if str(item.get("anchor") or "") == table or str(item.get("caption") or "") == table
            ]
        cap = limit if limit > 0 else int(get_settings().document_table_preview_rows)
        paged = [_page_table(item, offset, cap) for item in tables]
        return {"document_id": str(document_id), "tables": paged}

    def search(
        self,
        actor: Actor,
        query: str,
        *,
        document_ids: list[str] | None = None,
        file_ids: list[str] | None = None,
        collection_ids: list[str] | None = None,
        top_k: int = 0,
        run: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """One retrieval path: stored passages, scored by ``retrieve``, scoped by the caller."""
        settings = get_settings()
        limit = top_k if top_k > 0 else int(settings.document_search_top_k)
        snippet = int(settings.document_search_snippet_chars)
        wanted_docs = set(document_ids or [])
        wanted_files = set(file_ids or [])
        wanted_collections = list(collection_ids or [])
        if run is not None and not wanted_collections:
            from ar_domain.runs.request import asked  # noqa: PLC0415

            stored = asked(run, "collection_ids")
            if isinstance(stored, list):
                wanted_collections = [str(item) for item in stored]
        hits: list[dict[str, object]] = []
        indexed = self._indexed_hits(
            actor,
            query,
            document_ids=list(wanted_docs),
            collection_ids=wanted_collections,
            top_k=limit,
        )
        if indexed is not None:
            hits = indexed
        else:
            for row in self.store.library_documents.values():
                if not self._visible(actor, row) or not self._in_scope(
                    row, wanted_docs, wanted_files
                ):
                    continue
                passages = _rows(row.get("passages"))
                for passage in retrieve(passages, query):
                    text = str(passage.get("text") or "")
                    weight = score(query, text)
                    if weight <= 0 and query.lower() not in text.lower():
                        continue
                    if weight <= 0:
                        weight = 0.1
                    anchor = str(passage.get("anchor") or "")
                    hits.append(
                        {
                            "document_id": str(row.get("id")),
                            "title": row.get("title"),
                            "passage_id": anchor,
                            "anchor": anchor,
                            "page": passage.get("page"),
                            "heading": passage.get("heading"),
                            "snippet": text[:snippet],
                            "content_hash": row.get("content_hash"),
                            "score": round(weight, 2),
                        }
                    )
        hits.sort(key=lambda item: float(str(item.get("score") or 0)), reverse=True)
        page = hits[:limit]
        nxt = f"o:{limit}" if len(hits) > limit else ""
        return {"hits": page, "nextCursor": nxt, "total": len(hits)}

    def read(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        *,
        page_from: int = 1,
        page_to: int = 0,
        anchor: str = "",
        heading: str = "",
        anchor_from: str = "",
        anchor_to: str = "",
        cursor: str = "",
        limit: int = 0,
    ) -> dict[str, object]:
        row = self._own(actor, document_id)
        pages = _rows(row.get("passages"))
        if anchor:
            known = [str(item.get("anchor") or "") for item in pages]
            pages = [item for item in pages if str(item.get("anchor") or "") == anchor]
            if not pages:
                raise ValidationFailedError(
                    f"This document has no anchor {anchor!r}. Its anchors run from "
                    f"{known[0]} to {known[-1]}. Read it without an anchor to see the whole text."
                    if known
                    else "This document has no stored text to read."
                )
        else:
            if heading:
                pages = [item for item in pages if str(item.get("heading") or "") == heading]
            if anchor_from:
                pages = [item for item in pages if str(item.get("anchor") or "") >= anchor_from]
            if anchor_to:
                pages = [item for item in pages if str(item.get("anchor") or "") <= anchor_to]
            if page_to > 0:
                pages = [
                    item
                    for item in pages
                    if page_from <= int(str(item.get("page") or 1)) <= page_to
                ]
        start = _cursor_index(cursor)
        pages = pages[start:]
        cap = limit if limit > 0 else int(get_settings().document_read_chars)
        body: list[str] = []
        used = 0
        shown: list[dict[str, object]] = []
        for item in pages:
            text = str(item.get("text") or "")
            if used and used + len(text) > cap:
                break
            shown.append(item)
            body.append(
                f"[{item.get('anchor')} p.{item.get('page')} {item.get('heading')}]\n{text}"
            )
            used += len(text)
            if used >= cap:
                break
        nxt = ""
        if shown and len(shown) < len(pages):
            nxt = f"o:{start + len(shown)}"
        return {
            "document_id": str(document_id),
            "title": row.get("title"),
            "passages": shown,
            "text": "\n\n".join(body),
            "nextCursor": nxt,
        }

    def original(self, actor: Actor, document_id: uuid.UUID) -> bytes:
        """The stored original. A hash mismatch is a failure, not the derived text."""
        row = self._own(actor, document_id)
        data = read_original(self.store, str(row.get("object_key") or ""))
        if data is None:
            raise NotFoundError()
        if hashlib.sha256(data).hexdigest() != row.get("content_hash"):
            raise ValidationFailedError("The stored file does not match its content hash.")
        return data

    def extract(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        schema: dict[str, object],
        *,
        alias: str = "",
    ) -> dict[str, object]:
        """Fill ``schema`` from the document. A missing model is an error."""
        if not schema:
            raise ValidationFailedError("extract needs a JSON Schema.")
        import orjson  # noqa: PLC0415

        from ar_common.wrapping import wrap_untrusted  # noqa: PLC0415
        from ar_domain.documents.sections import _json_object  # noqa: PLC0415

        row = self._own(actor, document_id)
        passages = _rows(row.get("passages"))
        evidence = "\n\n".join(
            f"[{item.get('anchor')} p.{item.get('page')}] {item.get('text')}" for item in passages
        )
        ask = self._ask(actor, alias)
        raw = ask(
            "Fill this JSON Schema from the passages only. "
            "Return one JSON object and no other text. "
            "Where a value comes from a passage, include that passage's anchor "
            "when the schema allows it.\n" + orjson.dumps(schema).decode(),
            wrap_untrusted(source="document", content=evidence),
        )
        if not isinstance(raw, str) or not raw.strip():
            raise ArError(
                ErrorCode.INVALID_STATE, "No model is configured, so nothing was extracted."
            )
        parsed = _json_object(raw)
        from jsonschema import Draft202012Validator  # noqa: PLC0415

        errors = list(Draft202012Validator(schema).iter_errors(parsed))
        if errors:
            raise ArError(ErrorCode.INVALID_STATE, "The extraction did not match the schema.")
        return {"document_id": str(document_id), "result": parsed, "kind": "extract"}

    def edit(
        self,
        actor: Actor,
        document_id: uuid.UUID,
        changes: list[dict[str, object]],
        *,
        redline: bool = False,
    ) -> dict[str, object]:
        """Write a new file version. The stored passages of the original are not changed."""
        row = self._own(actor, document_id)
        if not changes:
            raise ValidationFailedError("edit needs at least one change.")
        from ar_domain.documents.create.redline import render_version  # noqa: PLC0415

        data = render_version(_rows(row.get("passages")), changes, redline=redline)
        stem = str(row.get("filename") or "document")
        name = f"{stem.rsplit('.', 1)[0]}-v{stem.count('-v') + 2}.docx"
        created = self.ingest(actor, data=data, filename=name)
        stored = self.store.library_documents.get(_as_uuid(created.get("id")))
        if isinstance(stored, dict):
            meta = stored.get("metadata")
            body = dict(meta) if isinstance(meta, dict) else {}
            body["versionOf"] = str(document_id)
            stored["metadata"] = body
            created = self._view(stored, detail=True)
        self._audit(actor, "library_document.versioned", document_id, {"redline": redline})
        return created

    def rows_for_map(
        self,
        actor: Actor,
        run: dict[str, object],
        *,
        document_ids: list[str],
        file_ids: list[str],
        collection_ids: list[str],
    ) -> list[dict[str, object]]:
        """The documents a map reads: the call, else the turn, else the agent's files."""
        if document_ids or file_ids:
            return self._scoped_ids(actor, document_ids, file_ids)
        if collection_ids:
            return [
                row
                for row in self.store.library_documents.values()
                if self._visible(actor, row) and self._in_collections(row, collection_ids)
            ]
        turn = self._scoped(actor, "turn", run)
        return turn or self._scoped(actor, "conversation", run)

    def _scoped(
        self, actor: Actor, scope: str, run: dict[str, object] | None
    ) -> list[dict[str, object]]:
        rows = [
            row
            for row in self.store.library_documents.values()
            if isinstance(row, dict) and row.get("tenant_id") == actor.tenant_id
        ]
        if scope == "library":
            return rows
        file_ids = (
            _turn_file_ids(self.store, run)
            if scope == "turn"
            else _conversation_file_ids(self.store, run)
        )
        if scope == "turn":
            file_ids = file_ids | _agent_file_ids(self.store, run)
        return [row for row in rows if self._file_id_for(row) in {str(item) for item in file_ids}]

    def _scoped_ids(
        self, actor: Actor, document_ids: list[str], file_ids: list[str]
    ) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        for row in self.store.library_documents.values():
            if not self._visible(actor, row):
                continue
            if str(row.get("id")) in document_ids or self._file_id_for(row) in file_ids:
                found.append(row)
        return found

    def _in_scope(self, row: dict[str, object], document_ids: set[str], file_ids: set[str]) -> bool:
        if not document_ids and not file_ids:
            return True
        return str(row.get("id")) in document_ids or self._file_id_for(row) in file_ids

    def _in_collections(self, row: dict[str, object], collection_ids: list[str]) -> bool:
        documents = getattr(self.store, "knowledge_documents", {})
        if not isinstance(documents, dict):
            return False
        digest = str(row.get("content_hash") or "")
        files = getattr(self.store, "files", {})
        for document in documents.values():
            if not isinstance(document, dict):
                continue
            if str(document.get("collection_id") or "") not in collection_ids:
                continue
            if _holds_hash(files, document, digest):
                return True
        return False

    def _ask(self, actor: Actor, alias: str) -> ModelAsk:
        return ModelAsk(self.store, actor.tenant_id, alias or "reasoning")

    def _own(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        row = self.store.library_documents.get(document_id)
        if isinstance(row, dict) and self._visible(actor, row):
            return row
        # A chat attachment's id is a file id. The library row is the same bytes.
        matched = self._by_attached_file(actor, document_id)
        if matched is not None and self._visible(actor, matched):
            return matched
        raise NotFoundError()

    def _visible(self, actor: Actor, row: object) -> bool:
        """The owner, or a user of a published agent whose default files name this file."""
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            return False
        if row.get("owner_user_id") == actor.user_id:
            return True
        return self._agent_granted(actor, row)

    def _agent_granted(self, actor: Actor, row: dict[str, object]) -> bool:
        """A file named on an agent in this tenant is readable by that agent's users.

        A row with no owner is not granted. The binding is the grant, not a missing owner.
        """
        if row.get("owner_user_id") is None:
            return False
        file_id = self._file_id_for(row)
        if not file_id:
            return False
        versions = getattr(self.store, "versions", {})
        if not isinstance(versions, dict):
            return False
        for version in versions.values():
            if not isinstance(version, dict) or version.get("tenant_id") != actor.tenant_id:
                continue
            definition = version.get("definition")
            if not isinstance(definition, dict):
                continue
            knowledge = definition.get("knowledge")
            if not isinstance(knowledge, dict):
                continue
            raw = knowledge.get("file_ids", knowledge.get("fileIds"))
            if isinstance(raw, list) and file_id in {str(item) for item in raw}:
                return True
        return False

    def _indexed_hits(
        self,
        actor: Actor,
        query: str,
        *,
        document_ids: list[str] | None = None,
        collection_ids: list[str] | None = None,
        top_k: int = 8,
    ) -> list[dict[str, object]] | None:
        """Index hits for the caller's documents, or None when nothing is indexed."""
        documents = getattr(self.store, "knowledge_documents", {})
        chunks = getattr(self.store, "document_chunks", {})
        if not isinstance(documents, dict) or not isinstance(chunks, dict) or not query.strip():
            return None
        visible = [
            row for row in self.store.library_documents.values() if self._visible(actor, row)
        ]
        hashes = {str(row.get("content_hash") or "") for row in visible if row.get("content_hash")}
        files = getattr(self.store, "files", {})
        file_ids = {
            document.get("raw_file_id")
            for document in documents.values()
            if isinstance(document, dict) and _holds_hash(files, document, hashes)
        }
        linked = [
            document
            for document in documents.values()
            if isinstance(document, dict)
            and document.get("tenant_id") == actor.tenant_id
            and document.get("status") != "deleted"
            and document.get("raw_file_id") in file_ids
        ]
        named_collections = {str(item) for item in collection_ids or []}
        named_documents = {str(item) for item in document_ids or []}
        if named_collections:
            linked = [
                document
                for document in linked
                if str(document.get("collection_id") or "") in named_collections
            ]
        if named_documents:
            linked = [
                document
                for document in linked
                if str(document.get("id") or "") in named_documents
                or str(document.get("library_document_id") or "") in named_documents
            ]
        named = [document.get("id") for document in linked]
        if not linked or not any(chunk.get("document_id") in named for chunk in chunks.values()):
            return None
        from ar_domain.knowledge.searching import search as search_index  # noqa: PLC0415
        from ar_domain.knowledge.threshold import retrieval_bar  # noqa: PLC0415

        collection_ids_found = list({document.get("collection_id") for document in linked})
        try:
            found = search_index(
                self.store,
                actor,
                query=query,
                collection_ids=[
                    item for item in collection_ids_found if isinstance(item, uuid.UUID)
                ],
                top_k=top_k,
                debug=False,
                min_score=retrieval_bar(self.store, actor.tenant_id, {}),
                document_ids=[item for item in named if isinstance(item, uuid.UUID)],
            )
        except ArError, ValueError, TypeError:
            return None
        hits = found.get("hits") if isinstance(found, dict) else None
        if not isinstance(hits, list):
            return []
        return [
            {
                "document_id": str(hit.get("library_document_id") or hit.get("document_id") or ""),
                "title": hit.get("title"),
                "passage_id": str(hit.get("anchor") or ""),
                "anchor": str(hit.get("anchor") or ""),
                "page": hit.get("page"),
                "heading": hit.get("heading"),
                "snippet": str(hit.get("snippet") or "")[
                    : int(get_settings().document_search_snippet_chars)
                ],
                "score": hit.get("score"),
            }
            for hit in hits
            if isinstance(hit, dict)
        ]

    def _by_attached_file(self, actor: Actor, file_id: uuid.UUID) -> dict[str, object] | None:
        files = getattr(self.store, "files", None)
        meta = files.get(file_id) if isinstance(files, dict) else None
        if not isinstance(meta, dict) or meta.get("tenant_id") != actor.tenant_id:
            return None
        digest = str(meta.get("sha256") or "")
        if not digest:
            return None
        return self._by_hash(actor.tenant_id, digest)

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
            "rule_sets",
            "judgements",
        ):
            if not isinstance(getattr(self.store, name, None), dict):
                setattr(self.store, name, {})

    def _file_id_for(self, row: dict[str, object]) -> str:
        digest = str(row.get("content_hash") or "")
        files = getattr(self.store, "files", {})
        if not digest or not isinstance(files, dict):
            return ""
        for file_id, meta in files.items():
            if (
                isinstance(meta, dict)
                and meta.get("tenant_id") == row.get("tenant_id")
                and meta.get("sha256") == digest
                and not meta.get("deleted_at")
            ):
                return str(file_id)
        return ""

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
            "object_key": row.get("object_key") or "",
            "size_bytes": row.get("size_bytes"),
            "status": row.get("status"),
            "page_count": row.get("page_count"),
            "created_at": _iso(row.get("created_at")),
            "deduped": False,
            "file_id": self._file_id_for(row),
            "metadata": row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
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


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _outline(row: dict[str, object]) -> list[dict[str, object]]:
    """Headings with their level, page span and tokens. One entry per heading."""
    from ar_domain.documents.strategy import estimate_tokens  # noqa: PLC0415

    grouped: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for passage in _rows(row.get("passages")):
        heading = str(passage.get("heading") or "")
        if heading not in grouped:
            order.append(heading)
            grouped[heading] = {
                "anchor": str(passage.get("anchor") or ""),
                "heading": heading,
                "level": passage.get("level") or 1,
                "pageFrom": passage.get("page"),
                "pageTo": passage.get("page"),
                "tokens": 0,
            }
        item = grouped[heading]
        page = passage.get("page")
        if isinstance(page, int) and not isinstance(page, bool):
            start = item.get("pageFrom")
            end = item.get("pageTo")
            if not isinstance(start, int) or page < start:
                item["pageFrom"] = page
            if not isinstance(end, int) or page > end:
                item["pageTo"] = page
        current = item.get("tokens")
        counted = current if isinstance(current, int) and not isinstance(current, bool) else 0
        item["tokens"] = counted + estimate_tokens(str(passage.get("text") or ""))
    return [grouped[name] for name in order]


def _page_table(table: dict[str, object], offset: int, limit: int) -> dict[str, object]:
    text = str(table.get("csv") or table.get("csv_text") or "")
    rows = [line for line in text.splitlines() if line.strip()]
    start = max(0, offset)
    window = rows[start : start + limit]
    nxt = start + limit if start + limit < len(rows) else None
    body = dict(table)
    body["rows"] = window
    body["rowCount"] = len(rows)
    body["nextOffset"] = nxt
    return body


def _cursor_index(cursor: str) -> int:
    if cursor.startswith("o:"):
        try:
            return max(0, int(cursor[2:]))
        except ValueError:
            return 0
    return 0


def _turn_file_ids(store: Any, run: dict[str, object] | None) -> set[str]:
    if not isinstance(run, dict):
        return set()
    from ar_domain.runs.request import asked  # noqa: PLC0415

    found: set[str] = set()
    stored = asked(run, "file_ids")
    if isinstance(stored, list):
        found.update(str(item) for item in stored)
    messages = getattr(store, "messages", {})
    message = messages.get(run.get("input_message_id")) if isinstance(messages, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "file" and part.get("file_id"):
                found.add(str(part.get("file_id")))
    return found


def _conversation_file_ids(store: Any, run: dict[str, object] | None) -> set[str]:
    if not isinstance(run, dict):
        return set()
    from ar_domain.files.attachments import conversation_attachments  # noqa: PLC0415

    return {
        str(item.file_id) for item in conversation_attachments(store, run.get("conversation_id"))
    }


def _agent_file_ids(store: Any, run: dict[str, object] | None) -> set[str]:
    if not isinstance(run, dict):
        return set()
    versions = getattr(store, "versions", {})
    version = versions.get(run.get("agent_version_id")) if isinstance(versions, dict) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    knowledge = definition.get("knowledge") if isinstance(definition, dict) else None
    raw = (
        knowledge.get("file_ids", knowledge.get("fileIds")) if isinstance(knowledge, dict) else None
    )
    if not isinstance(raw, list):
        return set()
    return {str(item) for item in raw}


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
