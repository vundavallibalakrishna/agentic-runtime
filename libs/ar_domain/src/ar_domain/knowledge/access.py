"""Who can see a collection and read a document. Spec: docs/03-specs/10-knowledge.md §2."""

import uuid
from typing import TYPE_CHECKING

from ar_domain.knowledge.acl import acl_overlap, allowed_classifications, principals_for

if TYPE_CHECKING:
    from typing import Any


def can_see(actor: Any, row: dict[str, object]) -> bool:
    """Visibility controls who can see and bind a collection."""
    if row.get("tenant_id") != actor.tenant_id:
        return False
    if "knowledge:manage" in actor.permissions:
        return True
    visibility = str(row.get("visibility") or "tenant")
    if visibility == "tenant":
        return True
    if visibility == "private":
        return row.get("created_by") == actor.user_id  # type: ignore[no-any-return]
    team = row.get("owner_team_id")
    teams = {str(item) for item in getattr(actor, "team_ids", ())}
    return team is not None and str(team) in teams


def can_manage(actor: Any, row: dict[str, object]) -> bool:
    """Creator, an owner-team lead, or ``knowledge:manage``."""
    if not can_see(actor, row):
        return False
    if "knowledge:manage" in actor.permissions:
        return True
    if row.get("created_by") == actor.user_id:
        return True
    team = row.get("owner_team_id")
    leads = getattr(actor, "lead_team_ids", frozenset())  # type: ignore[var-annotated]
    return team is not None and str(team) in {str(item) for item in leads}


def principals(store: Any, actor: Any) -> list[str]:
    groups = list(getattr(store, "user_groups", {}).get(actor.user_id, []))
    teams = [str(item) for item in getattr(actor, "team_ids", ())]
    return principals_for(actor.user_id, group_ids=groups, team_ids=teams)


def clearance(store: Any, actor: Any) -> str:
    found = getattr(store, "user_clearance", {}).get(actor.user_id)
    return str(found or "internal")


def readable_classes(store: Any, actor: Any) -> list[str]:
    return allowed_classifications(clearance(store, actor))


def can_read_document(
    store: Any, actor: Any, document: dict[str, object], collection: dict[str, object]
) -> bool:
    if document.get("status") == "deleted":
        return False
    if str(document.get("classification") or "internal") not in readable_classes(store, actor):
        return False
    del collection
    acl = document.get("acl_principals")
    if not isinstance(acl, list) or not acl:
        return False
    return acl_overlap([str(item) for item in acl], principals(store, actor))


def emails(store: Any) -> dict[str, str]:
    raw = getattr(store, "user_emails", {})
    return {str(email).lower(): str(user_id) for user_id, email in raw.items()}


def as_uuid(value: object) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))
