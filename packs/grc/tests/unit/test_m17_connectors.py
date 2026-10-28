"""Connector kit, P1 fixtures, approval on writes and external references."""

import uuid

from ar_common.settings import BaseServiceSettings
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.records.memory import blobs, bucket
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline
from ar_pack_grc.connectors.kit import (
    READ_METHODS,
    WRITE_METHODS,
    ConnectorKit,
    MemoryTransport,
    Tool,
)
from ar_pack_grc.connectors.registry import SERVERS, invoke
from ar_pack_grc.findings import list_issues
from ar_pack_grc.install import install_for

PERMS = PERMISSION_KEYS | frozenset(
    {
        "grc.controls:read",
        "grc.controls:manage",
        "grc.evidence:link",
        "grc.tests:read",
        "grc.tests:run",
        "grc.findings:read",
        "grc.findings:manage",
        "evidence:read",
        "evidence:capture",
    }
)


def _actor() -> Actor:
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=PERMS,
        roles=frozenset({"tenant_admin"}),
    )


def _store() -> tuple[ChatService, Actor]:
    store = ChatService()
    actor = _actor()
    install_for(store, actor)
    return store, actor


def test_page_cap_backoff_and_stable_hash() -> None:
    assert BaseServiceSettings().grc_connector_max_pages == 50
    forward = {"cursor": "9", "region": "eu"}
    reverse = {"region": "eu", "cursor": "9"}
    assert request_same(forward, reverse)
    store, actor = _store()
    pages = []
    for index in range(4):
        body: dict[str, object] = {"items": [{"id": index}]}
        if index < 3:
            body["nextCursor"] = str(index + 1)
        pages.append({"status": 200, "body": body})
    recorded = [{"status": 429, "body": {"message": "slow"}}, *pages]
    kit = ConnectorKit(
        store, actor, "grc_aws", MemoryTransport(recorded), max_pages=2
    )
    tool = Tool("list_config_rules", "List Config rules", "R0", "GET", "/config/rules")
    kept = kit.collect(tool)
    captured = _aws(store)
    assert len(kept) == 2
    assert kit.delays == [0.05]
    assert len(captured) == 2
    assert all(row["collection_method"] == "tool_call" for row in captured)
    kit.transport = MemoryTransport(recorded)
    again = kit.collect(tool)
    assert len(again) == 2
    assert len(_aws(store)) == 2


def _aws(store: ChatService) -> list[dict[str, object]]:
    return [
        row for row in bucket(store, "evidence").values() if row.get("source_system") == "grc_aws"
    ]


def request_same(left: dict[str, str], right: dict[str, str]) -> bool:
    from ar_pack_grc.connectors.kit import request_hash

    return request_hash("GET", "/config/rules", left) == request_hash("GET", "/config/rules", right)


def test_each_read_tool_captures_and_never_writes() -> None:
    store, actor = _store()
    marker = "fixture-token-value"
    store.grc_connections = {"grc_aws": {"secret_ref_id": "aws-key", "value": marker}}
    for spec in SERVERS:
        for tool in spec.tools:
            if tool.method not in READ_METHODS:
                continue
            result = invoke(
                store,
                spec,
                tool.name,
                {"_tenant_id": str(actor.tenant_id), "_user_id": str(actor.user_id)},
            )
            assert result["is_error"] is False
            assert result["structured"]["source_system"] == spec.slug
            assert result["structured"]["captured"] >= 1
    methods = {call.method for call in store.grc_http_log}
    assert methods
    assert methods.isdisjoint(WRITE_METHODS)
    raw = b"".join(blobs(store, "evidence").values())
    assert marker.encode() not in raw
    aws = next(
        row for row in bucket(store, "evidence").values() if row["source_system"] == "grc_aws"
    )
    assert aws["provenance"]["credential"] == "secret_ref"
    assert aws["provenance"]["request_sha256"]


def test_write_waits_for_approval_then_stores_the_external_id() -> None:
    store, actor = _store()
    store.grc_http_log = []
    version = next(
        row
        for row in store.tool_versions.values()
        if row["qualified_name"] == "grc_jira.create_issue"
    )
    arguments = {"title": "Close the config gap", "finding_id": ""}
    held, digest = _execute(store, actor, version["id"], arguments)
    assert held["status"] == "awaiting_approval"
    assert store.grc_http_log == []
    approval_id = uuid.UUID(str(held["approval_id"]))
    store.approvals[approval_id]["status"] = "approved"
    done, _digest = _execute(store, actor, version["id"], arguments, approval_id, digest)
    assert done["status"] == "succeeded"
    assert any(call.method == "POST" for call in store.grc_http_log)
    issues = list_issues(store, actor, {})
    assert issues["items"][0]["external_ref"] == "grc_jira:SEC-14"
    snow = next(
        row
        for row in store.tool_versions.values()
        if row["qualified_name"] == "grc_servicenow.create_record"
    )
    assert snow["risk_class"] == "W2"
    assert version["risk_class"] == "W2"


def _execute(
    store: ChatService,
    actor: Actor,
    version_id: uuid.UUID,
    arguments: dict[str, object],
    approval_id: uuid.UUID | None = None,
    digest: str = "",
) -> tuple[dict[str, object], str]:
    hashed = digest or call_args_hash(str(version_id), arguments)
    request: dict[str, object] = {
        "tenant_id": actor.tenant_id,
        "user_id": actor.user_id,
        "synthetic": True,
        "tool_version_id": version_id,
        "arguments": arguments,
        "args_hash": hashed,
        "model_call_id": "m17",
    }
    if approval_id is not None:
        request["approval_id"] = approval_id
    return ToolPipeline(store).execute(request), hashed
