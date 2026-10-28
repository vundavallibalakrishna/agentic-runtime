"""GRC policy documents. Publish waits for a signed review."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.campaigns import create_campaign
from ar_pack_grc.reviews import audited, open_review, signed_for, supersede
from ar_pack_grc.values import required_text

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor


def list_policies(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.policies:read")
    body = snake_body(query)
    text = str(body.get("q") or "").lower()
    items = []
    for row in bucket_rows(store, "grc_policies").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if text and text not in str(row.get("title") or "").lower():
            continue
        items.append(present(row))
    return page(items)


def create_policy(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.policies:manage")
    body = snake_body(payload)
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "key": required_text(body.get("key"), "key"),
        "title": required_text(body.get("title"), "title"),
        "owner_user_id": body.get("owner_user_id") or actor.user_id,
        "created_at": utcnow(),
    }
    bucket_rows(store, "grc_policies")[item_id] = row
    return present(row)


def get_policy(store: Any, actor: Actor, policy_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.policies:read")
    row = one(store, "grc_policies", actor, policy_id)
    body = present(row)
    body["versions"] = [
        present(item)
        for item in bucket_rows(store, "grc_policy_versions").values()
        if same_tenant(item, actor.tenant_id) and item.get("policy_id") == policy_id
    ]
    return body


def add_version(
    store: Any, actor: Actor, policy_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.policies:manage")
    one(store, "grc_policies", actor, policy_id)
    body = snake_body(payload)
    text = required_text(body.get("body_md"), "body_md")
    version = 1 + sum(
        1
        for item in bucket_rows(store, "grc_policy_versions").values()
        if item.get("policy_id") == policy_id
    )
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "policy_id": policy_id,
        "version": version,
        "body_md": text,
        "change_note": str(body.get("change_note") or ""),
        "content_hash": hashlib.sha256(text.encode()).hexdigest(),
        "state": "draft",
        "review_item_id": None,
        "published_at": None,
    }
    bucket_rows(store, "grc_policy_versions")[item_id] = row
    return present(row)


def revise_draft(store: Any, actor: Actor, version_id: uuid.UUID, body_md: str) -> dict[str, Any]:
    """A new body hash supersedes the open review for this version."""
    require(actor, "grc.policies:manage")
    row = one(store, "grc_policy_versions", actor, version_id)
    if row.get("state") != "draft":
        raise ConflictError("review_required")
    text = required_text(body_md, "body_md")
    row["body_md"] = text
    row["content_hash"] = supersede(store, version_id, text)
    return present(row)


def submit_review(store: Any, actor: Actor, policy_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.policies:manage")
    version = _latest_draft(store, actor, policy_id)
    text = str(version.get("body_md") or "")
    item = open_review(
        store,
        actor,
        slug="grc-policies",
        subject_id=version["id"],
        content=text,
        statement=f"I reviewed policy version {version.get('version')}.",
    )
    version["review_item_id"] = item.get("id")
    version["content_hash"] = item.get("content_hash")
    return {"version": present(version), "review_item": item}


def publish(store: Any, actor: Actor, version_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.policies:manage")
    row = one(store, "grc_policy_versions", actor, version_id)
    if row.get("state") == "published":
        return present(row)
    digest = str(row.get("content_hash") or "")
    if signed_for(store, version_id, digest) is None:
        raise ConflictError("review_required")
    row["state"] = "published"
    row["published_at"] = utcnow()
    if not audited(store, "grc.policy.published", version_id):
        record(store, actor, "grc.policy.published", version_id, {"content_hash": digest})
        policy = one(store, "grc_policies", actor, row["policy_id"])
        create_campaign(
            store,
            actor,
            {
                "kind": "acknowledgement",
                "title": f"Acknowledge {policy.get('title')}",
                "audience": {"policy_id": str(policy["id"]), "version_id": str(version_id)},
            },
            trusted=True,
        )
    return present(row)


def search_published(store: Any, actor: Actor, query: str) -> list[dict[str, Any]]:
    require(actor, "grc.policies:read")
    published = {
        row["policy_id"]
        for row in bucket_rows(store, "grc_policy_versions").values()
        if same_tenant(row, actor.tenant_id) and row.get("state") == "published"
    }
    found = []
    for row in bucket_rows(store, "grc_policies").values():
        if not same_tenant(row, actor.tenant_id) or row["id"] not in published:
            continue
        if query and query.lower() not in str(row.get("title") or "").lower():
            continue
        found.append(present(row))
    return found


def _latest_draft(store: Any, actor: Actor, policy_id: uuid.UUID) -> dict[str, Any]:
    one(store, "grc_policies", actor, policy_id)
    drafts = [
        row
        for row in bucket_rows(store, "grc_policy_versions").values()
        if same_tenant(row, actor.tenant_id)
        and row.get("policy_id") == policy_id
        and row.get("state") == "draft"
    ]
    if not drafts:
        raise ConflictError("review_required")
    drafts.sort(key=lambda row: int(row.get("version") or 0))
    return drafts[-1]
