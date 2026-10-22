"""Collections, sources and documents for the dev API.

Postgres tables are revision 0014. A bound process flushes this cache (OQ-38).
It uses the same ingest and retrieval functions as the worker.
"""

import hashlib
import os
import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_contracts.tenants import PlanLimits
from ar_domain.audit.memory import remember
from ar_domain.knowledge.access import can_manage, can_read_document, can_see
from ar_domain.knowledge.acl import collection_acl
from ar_domain.knowledge.fetchers import check
from ar_domain.knowledge.pipeline import ingest_or_enqueue
from ar_domain.knowledge.searching import search as run_search
from ar_domain.knowledge.store import memory_index
from ar_domain.knowledge.store_types import SUPPORTED_DIMS, PhysicalCollectionSpec
from ar_domain.knowledge.syncing import (
    acl_sync,
    delete_document,
    finish_job,
    open_job,
    reindex,
    sync_source,
)
from ar_domain.knowledge.syncutil import run_sync

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_KINDS = frozenset(
    {
        "upload",
        "web",
        "s3",
        "sharepoint",
        "confluence",
        "google_drive",
        "database",
        "mcp_resource",
    }
)
_VISIBILITY = frozenset({"private", "team", "tenant"})
_CLASS = frozenset({"public", "internal", "confidential", "restricted"})


class KnowledgeBook:
    """Object-level access. A missing or foreign row is 404."""

    def __init__(self, store: Any) -> None:
        self.store = store
        for name in (
            "knowledge_collections",
            "knowledge_sources",
            "knowledge_documents",
            "document_chunks",
            "ingestion_jobs",
            "knowledge_blobs",
            "user_emails",
            "user_clearance",
            "user_groups",
            "group_keys",
        ):
            if not isinstance(getattr(store, name, None), dict):
                setattr(store, name, {})

    def list_collections(self, actor: Actor) -> list[dict[str, object]]:
        rows = [
            self._collection_view(actor, row)
            for row in self.store.knowledge_collections.values()
            if can_see(actor, row)
        ]
        rows.sort(key=lambda item: str(item["name"]).lower())
        return rows

    def create_collection(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        self._require_manage(actor)
        slug = str(body.get("slug") or "").strip().lower()
        name = str(body.get("name") or "").strip()
        if not slug or not name or any(char.isspace() for char in slug):
            raise ValidationFailedError("slug and name are required")
        if any(
            row.get("tenant_id") == actor.tenant_id and str(row.get("slug")) == slug
            for row in self.store.knowledge_collections.values()
        ):
            raise ConflictError("slug is already in use")
        self._limits(actor, adding=1)
        visibility = str(body.get("visibility") or "tenant")
        if visibility not in _VISIBILITY:
            raise ValidationFailedError("visibility is invalid")
        classification = str(body.get("classification") or "internal")
        if classification not in _CLASS:
            raise ValidationFailedError("classification is invalid")
        dims = int(body.get("dims") or 1024)  # type: ignore[call-overload]
        if dims not in SUPPORTED_DIMS:
            raise ArError(ErrorCode.VALIDATION_FAILED, "unsupported_embedding_dims")
        chunking = _chunking(body.get("chunking"))
        collection_id = new_id()
        backend = os.environ.get("AR_VECTOR_BACKEND", "pgvector").strip() or "pgvector"
        if backend not in {"pgvector", "qdrant"}:
            backend = "pgvector"
        store_collection = run_sync(
            memory_index(self.store).ensure_collection(
                PhysicalCollectionSpec(
                    tenant_id=actor.tenant_id,
                    collection_id=collection_id,
                    model_key=str(body.get("embedding_alias") or "embed"),
                    dims=dims,
                )
            )
        )
        now = utcnow()
        row = {
            "id": collection_id,
            "tenant_id": actor.tenant_id,
            "slug": slug,
            "name": name,
            "description": str(body.get("description") or ""),
            "owner_team_id": body.get("owner_team_id"),
            "visibility": visibility,
            "acl_mode": str(body.get("acl_mode") or "source"),
            "sensitivity": str(body.get("sensitivity") or "normal"),
            "classification": classification,
            "embedding_alias": str(body.get("embedding_alias") or "embed"),
            "embedding_model": "fake-embed",
            "dims": dims,
            "index_version": 1,
            "store_backend": backend,
            "store_collection": store_collection,
            "text_search_config": str(body.get("text_search_config") or "simple"),
            "chunking": chunking,
            "stats": {"documents": 0, "chunks": 0, "bytes": 0, "failed": 0},
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self.store.knowledge_collections[collection_id] = row
        self._upload_source(actor, row)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="collection.created",
            target_type="knowledge_collection",
            target_id=collection_id,
            detail={"slug": slug},
        )
        return self._collection_view(actor, row)

    def get_collection(self, actor: Actor, collection_id: uuid.UUID) -> dict[str, object]:
        return self._collection_view(actor, self._visible(actor, collection_id))

    def patch_collection(
        self, actor: Actor, collection_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._managed(actor, collection_id)
        for key in ("name", "description", "visibility", "sensitivity", "classification"):
            if key in body and body[key] is not None:
                row[key] = body[key]
        if "owner_team_id" in body:
            row["owner_team_id"] = body["owner_team_id"]
        row["updated_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="collection.updated",
            target_type="knowledge_collection",
            target_id=collection_id,
            detail={"fields": sorted(body)},
        )
        return self._collection_view(actor, row)

    def delete_collection(self, actor: Actor, collection_id: uuid.UUID) -> dict[str, object]:
        row = self._managed(actor, collection_id)
        if self._bound(row):
            raise ConflictError("a published agent still uses this collection")
        for document in list(self.store.knowledge_documents.values()):
            same = document.get("collection_id") == collection_id
            if same and document.get("status") != "deleted":
                delete_document(self.store, document, actor_id=actor.user_id)
        run_sync(
            memory_index(self.store).drop_collection(
                str(row.get("store_collection")), actor.tenant_id, collection_id
            )
        )
        self.store.knowledge_collections.pop(collection_id, None)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="collection.deleted",
            target_type="knowledge_collection",
            target_id=collection_id,
            detail={"slug": str(row.get("slug"))},
        )
        return {"id": str(collection_id), "status": "deleted"}

    def reindex_collection(
        self, actor: Actor, collection_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._managed(actor, collection_id)
        if body.get("embedding_alias"):
            row["embedding_alias"] = str(body["embedding_alias"])
        if isinstance(body.get("chunking"), dict):
            row["chunking"] = _chunking(body["chunking"])
        if body.get("text_search_config") in {"simple", "english"}:
            row["text_search_config"] = body["text_search_config"]
        if body.get("target_backend") in {"pgvector", "qdrant"}:
            row["pending_backend"] = body["target_backend"]
        job = reindex(self.store, row, actor_id=actor.user_id)
        return {"job_id": str(job["id"])}

    def list_sources(self, actor: Actor, collection_id: uuid.UUID) -> list[dict[str, object]]:
        self._visible(actor, collection_id)
        return [
            self._source_view(row)
            for row in self.store.knowledge_sources.values()
            if row.get("collection_id") == collection_id
        ]

    def create_source(
        self, actor: Actor, collection_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        collection = self._managed(actor, collection_id)
        kind = str(body.get("kind") or "")
        if kind not in _KINDS:
            raise ValidationFailedError("kind is invalid")
        owned = [
            row
            for row in self.store.knowledge_sources.values()
            if row.get("collection_id") == collection_id
        ]
        if len(owned) >= 20:
            raise ArError(ErrorCode.PLAN_LIMIT_REACHED, "a collection can have 20 sources")
        now = utcnow()
        source_id = new_id()
        row = {
            "id": source_id,
            "tenant_id": actor.tenant_id,
            "collection_id": collection_id,
            "name": str(body.get("name") or kind),
            "kind": kind,
            "config": body.get("config") if isinstance(body.get("config"), dict) else {},
            "secret_ref_id": body.get("secret_id"),
            "data_connection_id": body.get("data_connection_id"),
            "sync_schedule": body.get("sync_schedule"),
            "acl_sync_schedule": body.get("acl_sync_schedule") or "*/10 * * * *",
            "temporal_schedule_id": f"ks-sync-{source_id}",
            "status": "active",
            "last_sync_at": None,
            "last_sync_status": None,
            "cursor": {},
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self.store.knowledge_sources[source_id] = row
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="source.created",
            target_type="knowledge_source",
            target_id=source_id,
            detail={"kind": kind},
        )
        if kind != "upload":
            sync_source(self.store, row, mode="full", actor_id=actor.user_id)
        del collection
        return self._source_view(row)

    def get_source(self, actor: Actor, source_id: uuid.UUID) -> dict[str, object]:
        return self._source_view(self._source(actor, source_id))

    def patch_source(
        self, actor: Actor, source_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._source(actor, source_id, manage=True)
        if isinstance(body.get("config"), dict):
            row["config"] = body["config"]
        if body.get("name"):
            row["name"] = body["name"]
        if "sync_schedule" in body:
            row["sync_schedule"] = body["sync_schedule"]
        row["updated_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="source.updated",
            target_type="knowledge_source",
            target_id=source_id,
            detail={},
        )
        return self._source_view(row)

    def delete_source(self, actor: Actor, source_id: uuid.UUID) -> dict[str, object]:
        row = self._source(actor, source_id, manage=True)
        if row.get("kind") == "upload":
            raise ConflictError("the uploads source stays with the collection")
        for document in list(self.store.knowledge_documents.values()):
            if document.get("source_id") == source_id and document.get("status") != "deleted":
                delete_document(self.store, document, actor_id=actor.user_id)
        self.store.knowledge_sources.pop(source_id, None)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="source.deleted",
            target_type="knowledge_source",
            target_id=source_id,
            detail={},
        )
        return {"id": str(source_id), "status": "deleted"}

    def test_source(self, actor: Actor, source_id: uuid.UUID) -> dict[str, object]:
        return check(self._source(actor, source_id, manage=True))

    def sync(self, actor: Actor, source_id: uuid.UUID, mode: str) -> dict[str, object]:
        row = self._source(actor, source_id, manage=True)
        if mode not in {"incremental", "full"}:
            raise ValidationFailedError("mode must be incremental or full")
        job = sync_source(self.store, row, mode=mode, actor_id=actor.user_id)
        return {"job_id": str(job["id"])}

    def pause(self, actor: Actor, source_id: uuid.UUID) -> dict[str, object]:
        row = self._source(actor, source_id, manage=True)
        row["status"] = "paused"
        return self._source_view(row)

    def resume(self, actor: Actor, source_id: uuid.UUID) -> dict[str, object]:
        row = self._source(actor, source_id, manage=True)
        row["status"] = "active"
        return self._source_view(row)

    def acl(self, actor: Actor, source_id: uuid.UUID) -> dict[str, object]:
        row = self._source(actor, source_id, manage=True)
        job = acl_sync(self.store, row, actor_id=actor.user_id)
        return {"job_id": str(job["id"])}

    def list_documents(
        self,
        actor: Actor,
        collection_id: uuid.UUID,
        *,
        query: str = "",
        status: str = "",
        source_id: uuid.UUID | None = None,
    ) -> list[dict[str, object]]:
        collection = self._visible(actor, collection_id)
        manager = can_manage(actor, collection)
        found: list[dict[str, object]] = []
        for row in self.store.knowledge_documents.values():
            if row.get("collection_id") != collection_id or row.get("status") == "deleted":
                continue
            if status and row.get("status") != status:
                continue
            if source_id is not None and row.get("source_id") != source_id:
                continue
            if query and query.lower() not in str(row.get("title") or "").lower():
                continue
            readable = can_read_document(self.store, actor, row, collection)
            if not readable and not manager:
                continue
            view = self._document_view(row)
            view["can_read"] = readable
            found.append(view)
        return found

    async def add_documents(
        self, actor: Actor, collection_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        collection = self._managed(actor, collection_id)
        file_ids = body.get("file_ids")
        if not isinstance(file_ids, list) or not file_ids or len(file_ids) > 100:
            raise ValidationFailedError("file_ids must contain 1 to 100 files")
        source = self._uploads(collection_id)
        requested = body.get("acl_principals")
        if isinstance(requested, list) and requested:
            principals = [str(item) for item in requested]
        else:
            principals = collection_acl(
                visibility=str(collection.get("visibility") or "tenant"),
                owner_team_id=None
                if collection.get("owner_team_id") is None
                else str(collection.get("owner_team_id")),
                created_by=str(collection.get("created_by") or actor.user_id),
            )
            if collection.get("acl_mode") == "source" and not requested:
                principals = [f"user:{actor.user_id}", "tenant:*"]
        documents = []
        for raw_id in file_ids:
            file_id = uuid.UUID(str(raw_id))
            file_row = self.store.files.get(file_id)
            if (
                not isinstance(file_row, dict)
                or file_row.get("tenant_id") != actor.tenant_id
                or file_row.get("owner_user_id") != actor.user_id
                or file_row.get("status") != "ready"
            ):
                raise ValidationFailedError("files must be ready and owned by you")
            raw = bytes(self.store.blobs.get(file_id, b""))
            self._byte_limit(actor, len(raw))
            document = self._new_document(
                actor, collection, source, file_row, principals, external_id=str(file_id)
            )
            self.store.knowledge_blobs[document["id"]] = raw
            job = open_job(
                self.store,
                tenant_id=actor.tenant_id,
                collection_id=collection_id,
                source_id=source["id"],  # type: ignore[arg-type]
                kind="single_document",
                triggered_by="upload",
            )
            status = await ingest_or_enqueue(self.store, uuid.UUID(str(document["id"])), raw)
            finish_job(job, status="failed" if status == "failed" else "succeeded")
            self.store.domain_events.append(
                {
                    "type": "knowledge.ingestion_completed",
                    "document_id": str(document["id"]),
                    "status": status,
                }
            )
            remember(
                self.store,
                tenant_id=actor.tenant_id,
                actor_id=actor.user_id,
                action="document.added",
                target_type="document",
                target_id=document["id"],
                detail={"title": document["title"]},
            )
            view = self._document_view(document)
            view["can_read"] = True
            documents.append(view)
        return {"documents": documents}

    def get_document(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        document, collection = self._document(actor, document_id)
        view = self._document_view(document)
        view["summary"] = document.get("summary") or ""
        view["language"] = document.get("language")
        view["can_read"] = can_read_document(self.store, actor, document, collection)
        view["jobs"] = [
            self._job_view(row)
            for row in self.store.ingestion_jobs.values()
            if row.get("source_id") == document.get("source_id")
        ][-10:]
        return view

    def chunks(self, actor: Actor, document_id: uuid.UUID) -> list[dict[str, object]]:
        document, collection = self._document(actor, document_id)
        if not can_manage(actor, collection):
            raise NotFoundError()
        rows = [
            {
                "id": str(row["id"]),
                "ordinal": row["ordinal"],
                "text": row["text"],
                "context_prefix": row.get("context_prefix") or "",
                "heading_path": row.get("heading_path") or [],
                "page_from": row.get("page_from"),
                "page_to": row.get("page_to"),
                "token_count": row["token_count"],
            }
            for row in self.store.document_chunks.values()
            if row.get("document_id") == document["id"]
        ]
        rows.sort(key=lambda item: int(item["ordinal"]))
        return rows

    async def reingest(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        document, _collection = self._document(actor, document_id, manage=True)
        raw = bytes(self.store.knowledge_blobs.get(document["id"], b""))
        document["version_hash"] = ""
        await ingest_or_enqueue(self.store, uuid.UUID(str(document["id"])), raw)
        return self._document_view(document)

    def remove_document(self, actor: Actor, document_id: uuid.UUID) -> dict[str, object]:
        document, _collection = self._document(actor, document_id, manage=True)
        source = self.store.knowledge_sources.get(document.get("source_id"))
        if not isinstance(source, dict) or source.get("kind") != "upload":
            raise ConflictError("delete a synced document at its source")
        delete_document(self.store, document, actor_id=actor.user_id)
        return {"id": str(document_id), "status": "deleted"}

    def list_jobs(self, actor: Actor, collection_id: uuid.UUID) -> list[dict[str, object]]:
        self._visible(actor, collection_id)
        return [
            self._job_view(row)
            for row in self.store.ingestion_jobs.values()
            if row.get("collection_id") == collection_id
        ]

    def get_job(self, actor: Actor, job_id: uuid.UUID) -> dict[str, object]:
        row = self.store.ingestion_jobs.get(job_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        self._visible(actor, uuid.UUID(str(row["collection_id"])))
        return self._job_view(row)

    def cancel_job(self, actor: Actor, job_id: uuid.UUID) -> dict[str, object]:
        row = self.store.ingestion_jobs.get(job_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        self._managed(actor, uuid.UUID(str(row["collection_id"])))
        if row.get("status") in {"queued", "running"}:
            finish_job(row, status="cancelled")
        return self._job_view(row)

    def search(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        raw_ids = body.get("collection_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            raise ValidationFailedError("collection_ids is required")
        top_k = int(body.get("top_k") or 8)  # type: ignore[call-overload]
        if top_k < 1 or top_k > 20:
            raise ValidationFailedError("top_k must be between 1 and 20")
        return run_search(
            self.store,
            actor,
            query=str(body.get("query") or ""),
            collection_ids=[uuid.UUID(str(item)) for item in raw_ids],
            top_k=top_k,
            debug=bool(body.get("debug")),
            min_score=float(body.get("min_score") or 0.2),  # type: ignore[arg-type]
        )

    def _upload_source(self, actor: Actor, collection: dict[str, object]) -> dict[str, object]:
        return self.create_source(
            actor,
            uuid.UUID(str(collection["id"])),
            {"name": "uploads", "kind": "upload", "config": {}},
        )

    def _new_document(
        self,
        actor: Actor,
        collection: dict[str, object],
        source: dict[str, object],
        file_row: dict[str, object],
        principals: list[str],
        *,
        external_id: str,
    ) -> dict[str, object]:
        document_id = new_id()
        now = utcnow()
        row = {
            "id": document_id,
            "tenant_id": actor.tenant_id,
            "collection_id": collection["id"],
            "source_id": source["id"],
            "external_id": external_id,
            "uri": f"file:{file_row.get('id')}",
            "title": str(file_row.get("name") or "Untitled"),
            "mime_type": str(file_row.get("mime_type") or "text/markdown"),
            "version_hash": "",
            "size_bytes": int(file_row.get("size_bytes") or 0),  # type: ignore[call-overload]
            "language": None,
            "classification": str(collection.get("classification") or "internal"),
            "acl_principals": principals,
            "acl_hash": hashlib.sha256("|".join(sorted(principals)).encode()).hexdigest(),
            "summary": "",
            "status": "pending",
            "error": None,
            "indexed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self.store.knowledge_documents[document_id] = row
        return row

    def _visible(self, actor: Actor, collection_id: uuid.UUID) -> dict[str, object]:
        row = self.store.knowledge_collections.get(collection_id)
        if not isinstance(row, dict) or not can_see(actor, row):
            raise NotFoundError()
        return row

    def _managed(self, actor: Actor, collection_id: uuid.UUID) -> dict[str, object]:
        row = self._visible(actor, collection_id)
        if not can_manage(actor, row):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot manage this collection")
        return row

    def _source(
        self, actor: Actor, source_id: uuid.UUID, *, manage: bool = False
    ) -> dict[str, object]:
        row = self.store.knowledge_sources.get(source_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        if manage:
            self._managed(actor, uuid.UUID(str(row["collection_id"])))
        else:
            self._visible(actor, uuid.UUID(str(row["collection_id"])))
        return row

    def _uploads(self, collection_id: uuid.UUID) -> dict[str, object]:
        for row in self.store.knowledge_sources.values():
            if row.get("collection_id") == collection_id and row.get("kind") == "upload":
                return row  # type: ignore[no-any-return]
        raise NotFoundError()

    def _document(
        self, actor: Actor, document_id: uuid.UUID, *, manage: bool = False
    ) -> tuple[dict[str, object], dict[str, object]]:
        row = self.store.knowledge_documents.get(document_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        collection = self.store.knowledge_collections.get(row.get("collection_id"))
        if not isinstance(collection, dict) or not can_see(actor, collection):
            raise NotFoundError()
        if manage and not can_manage(actor, collection):
            raise ArError(ErrorCode.FORBIDDEN, "you cannot manage this document")
        if (
            not manage
            and not can_manage(actor, collection)
            and not can_read_document(self.store, actor, row, collection)
        ):
            raise NotFoundError()
        return row, collection

    def _limits(self, actor: Actor, *, adding: int) -> None:
        limits = _plan(self.store, actor.tenant_id)
        owned = [
            row
            for row in self.store.knowledge_collections.values()
            if row.get("tenant_id") == actor.tenant_id
        ]
        if limits.max_collections is not None and len(owned) + adding > limits.max_collections:
            raise ArError(ErrorCode.PLAN_LIMIT_REACHED, "collection limit reached")

    def _byte_limit(self, actor: Actor, extra: int) -> None:
        limits = _plan(self.store, actor.tenant_id)
        documents = [
            row
            for row in self.store.knowledge_documents.values()
            if row.get("tenant_id") == actor.tenant_id and row.get("status") != "deleted"
        ]
        if len(documents) + 1 > limits.max_knowledge_documents:
            raise ArError(ErrorCode.PLAN_LIMIT_REACHED, "document limit reached")
        total = sum(int(row.get("size_bytes") or 0) for row in documents) + extra
        if total > limits.max_knowledge_bytes:
            raise ArError(ErrorCode.PLAN_LIMIT_REACHED, "knowledge byte limit reached")

    def _bound(self, collection: dict[str, object]) -> bool:
        slug = str(collection.get("slug"))
        for version in self.store.versions.values():
            if version.get("state") != "published":
                continue
            definition = version.get("definition")
            if not isinstance(definition, dict):
                continue
            knowledge = definition.get("knowledge")
            if isinstance(knowledge, dict) and slug in set(knowledge.get("collections") or []):
                return True
        return False

    def _collection_view(self, actor: Actor, row: dict[str, object]) -> dict[str, object]:
        sources = [
            item
            for item in self.store.knowledge_sources.values()
            if item.get("collection_id") == row.get("id")
        ]
        synced = (item.get("last_sync_at") for item in sources if item.get("last_sync_at"))
        last = max(synced, default=None)
        stats = row.get("stats") if isinstance(row.get("stats"), dict) else {}
        return {
            "id": str(row["id"]),
            "slug": row["slug"],
            "name": row["name"],
            "description": row.get("description") or "",
            "visibility": row.get("visibility"),
            "acl_mode": row.get("acl_mode"),
            "sensitivity": row.get("sensitivity"),
            "classification": row.get("classification"),
            "embedding_alias": row.get("embedding_alias"),
            "index_version": row.get("index_version"),
            "store_backend": row.get("store_backend"),
            "owner_team": None
            if row.get("owner_team_id") is None
            else str(row.get("owner_team_id")),
            "stats": {
                "documents": int(stats.get("documents") or 0),  # type: ignore[attr-defined]
                "chunks": int(stats.get("chunks") or 0),  # type: ignore[attr-defined]
                "bytes": int(stats.get("bytes") or 0),  # type: ignore[attr-defined]
                "failed": int(stats.get("failed") or 0),  # type: ignore[attr-defined]
            },
            "sources_count": len(sources),
            "last_sync_at": None if last is None else str(last),
            "can_manage": can_manage(actor, row),
        }

    def _source_view(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "collection_id": str(row["collection_id"]),
            "name": row["name"],
            "kind": row["kind"],
            "config": row.get("config") or {},
            "status": row.get("status"),
            "sync_schedule": row.get("sync_schedule"),
            "acl_sync_schedule": row.get("acl_sync_schedule"),
            "last_sync_at": None if row.get("last_sync_at") is None else str(row["last_sync_at"]),
            "last_sync_status": row.get("last_sync_status"),
        }

    def _document_view(self, row: dict[str, object]) -> dict[str, object]:
        source = self.store.knowledge_sources.get(row.get("source_id"), {})
        acl = row.get("acl_principals")
        return {
            "id": str(row["id"]),
            "title": row.get("title"),
            "uri": row.get("uri"),
            "mime_type": row.get("mime_type"),
            "size_bytes": row.get("size_bytes"),
            "status": row.get("status"),
            "error": row.get("error"),
            "source": {
                "id": str(source.get("id") or ""),
                "name": source.get("name"),
                "kind": source.get("kind"),
            },
            "classification": row.get("classification"),
            "acl_principal_count": len(acl) if isinstance(acl, list) else 0,
            "source_modified_at": row.get("source_modified_at"),
            "indexed_at": None if row.get("indexed_at") is None else str(row.get("indexed_at")),
            "summary": row.get("summary") or "",
        }

    def _job_view(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(row["id"]),
            "kind": row.get("kind"),
            "status": row.get("status"),
            "stats": row.get("stats") or {},
            "error": row.get("error"),
            "triggered_by": row.get("triggered_by"),
            "started_at": None if row.get("started_at") is None else str(row.get("started_at")),
            "finished_at": None if row.get("finished_at") is None else str(row.get("finished_at")),
            "failures": row.get("failures") or [],
        }

    def _require_manage(self, actor: Actor) -> None:
        if "knowledge:manage" not in actor.permissions:
            raise ArError(ErrorCode.FORBIDDEN, "knowledge:manage is required")


def _chunking(value: object) -> dict[str, object]:
    raw = value if isinstance(value, dict) else {}
    target = int(raw.get("target_tokens") or 512)
    overlap = int(raw.get("overlap_pct") or 12)
    if target < 128 or target > 2048 or overlap < 0 or overlap > 30:
        raise ValidationFailedError("chunking is outside the allowed range")
    return {
        "target_tokens": target,
        "overlap_pct": overlap,
        "contextual": bool(raw.get("contextual") or False),
    }


def _plan(store: Any, tenant_id: uuid.UUID) -> PlanLimits:
    settings = getattr(store, "tenant_settings", {}).get(tenant_id, {})
    raw = settings.get("plan_limits") if isinstance(settings, dict) else None
    if isinstance(raw, dict):
        return PlanLimits.model_validate(raw)
    return PlanLimits()
