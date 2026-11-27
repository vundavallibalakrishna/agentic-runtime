"""Poll ``ar-ingest`` for document, sync, reindex and audit workflows."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

from temporalio.client import Client
from temporalio.worker import Worker

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger
from ar_common.settings import get_settings, loopback_allowed
from ar_common.temporal_worker import temporal_unavailable_fields, temporal_worker_kwargs
from ar_ingest.activities import (
    acl_sync_activity,
    audit_activity,
    bind_store,
    delete_document_activity,
    ingest_document_activity,
    migrate_activity,
    parse_library_activity,
    reindex_abandon_activity,
    reindex_documents_activity,
    reindex_prepare_activity,
    reindex_switch_activity,
    sync_source_activity,
)
from ar_ingest.main import TASK_QUEUE
from ar_ingest.workflows.acl_sync import AclSyncWorkflow
from ar_ingest.workflows.delete_document import DeleteDocumentWorkflow
from ar_ingest.workflows.ingest_document import IngestDocumentWorkflow
from ar_ingest.workflows.library_parse import LibraryParseWorkflow
from ar_ingest.workflows.migrate_retrieval_store import MigrateRetrievalStoreWorkflow
from ar_ingest.workflows.reindex_collection import ReindexCollectionWorkflow
from ar_ingest.workflows.retrieval_store_audit import RetrievalStoreAuditWorkflow
from ar_ingest.workflows.source_sync import SourceSyncWorkflow

_log = get_logger(__name__)


def ingest_workflows() -> list[type]:
    """Workflows the ingest worker polls. Tests register this same list."""
    return [
        IngestDocumentWorkflow,
        LibraryParseWorkflow,
        DeleteDocumentWorkflow,
        SourceSyncWorkflow,
        AclSyncWorkflow,
        ReindexCollectionWorkflow,
        MigrateRetrievalStoreWorkflow,
        RetrievalStoreAuditWorkflow,
    ]


def ingest_activities() -> list[Callable[..., Any]]:
    """Activities the ingest worker polls. Tests register this same list."""
    return [
        ingest_document_activity,
        parse_library_activity,
        sync_source_activity,
        acl_sync_activity,
        delete_document_activity,
        reindex_prepare_activity,
        reindex_documents_activity,
        reindex_switch_activity,
        reindex_abandon_activity,
        migrate_activity,
        audit_activity,
    ]


def _address() -> str:
    settings = get_settings()
    configured = str(getattr(settings, "temporal_address", "") or "").strip()
    if configured:
        return configured
    return local_endpoint("AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT")


async def _prepare_store() -> None:
    from ar_domain.chat.service import ChatService  # noqa: PLC0415
    from ar_domain.durable.bind import attach_store  # noqa: PLC0415
    from ar_domain.readmodel.boot import build_product_store  # noqa: PLC0415

    settings = get_settings()
    store = build_product_store(
        settings,
        allow_loopback=loopback_allowed(settings),
    )
    store._ingest_worker = True
    if isinstance(store, ChatService):
        await attach_store(store, settings.database_url)
    bind_store(store)


async def run_worker() -> None:
    """Connect and poll. A down frontend is logged and retried."""
    while True:
        try:
            client = await asyncio.wait_for(
                Client.connect(
                    _address(),
                    namespace=getattr(get_settings(), "temporal_namespace", "") or "default",
                ),
                timeout=5,
            )
            await _prepare_store()
            worker = Worker(
                client,
                task_queue=TASK_QUEUE,
                workflows=ingest_workflows(),
                activities=ingest_activities(),
                **temporal_worker_kwargs(),
            )
            _log.info("temporal_connected", queue=TASK_QUEUE)
            await worker.run()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - keep the health server up
            _log.warning("temporal_unavailable", **temporal_unavailable_fields(_address(), exc))
            await asyncio.sleep(5)
