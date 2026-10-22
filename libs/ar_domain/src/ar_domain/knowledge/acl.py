"""Principals, classification and external principal mapping.

Spec: docs/03-specs/10-knowledge.md §2 and §5.3.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid

CLASS_RANK = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}


def allowed_classifications(clearance: str) -> list[str]:
    """Classifications the person may read, from ``public`` up to their clearance."""
    limit = CLASS_RANK.get(clearance, CLASS_RANK["internal"])
    return [name for name, rank in CLASS_RANK.items() if rank <= limit]


def principals_for(
    user_id: uuid.UUID,
    *,
    group_ids: list[str] | None = None,
    team_ids: list[str] | None = None,
) -> list[str]:
    """``user:{id}``, ``tenant:*``, and the person's groups and teams."""
    found = [f"user:{user_id}", "tenant:*"]
    found.extend(f"group:{group_id}" for group_id in group_ids or [] if group_id)
    found.extend(f"team:{team_id}" for team_id in team_ids or [] if team_id)
    return found


def collection_acl(
    *,
    visibility: str,
    owner_team_id: str | None,
    created_by: str | None,
) -> list[str]:
    """Principals implied by collection visibility when ``acl_mode`` is ``collection``."""
    if visibility == "tenant":
        return ["tenant:*"]
    if visibility == "team" and owner_team_id:
        return [f"team:{owner_team_id}"]
    if created_by:
        return [f"user:{created_by}"]
    return []


def map_external(
    external: list[dict[str, object]],
    *,
    email_to_user: dict[str, str],
    group_keys: dict[str, str],
    company_domains: set[str],
) -> tuple[list[str], int]:
    """Map source principals. Unmapped entries are dropped and counted.

    A document left with no principals is readable by nobody.
    """
    mapped: list[str] = []
    unmapped = 0
    for item in external:
        kind = str(item.get("type") or "")
        email = str(item.get("email") or "").strip().lower()
        external_id = str(item.get("id") or item.get("name") or "")
        if kind in {"domain", "anyone"}:
            domain = email.split("@")[-1] if "@" in email else str(item.get("id") or "")
            if kind == "anyone" or (domain and domain.lower() in company_domains):
                mapped.append("tenant:*")
            else:
                unmapped += 1
            continue
        if kind == "user" and email in email_to_user:
            mapped.append(f"user:{email_to_user[email]}")
            continue
        if kind == "group":
            group_id = group_keys.get(external_id) or group_keys.get(external_id.lower())
            if group_id:
                mapped.append(f"group:{group_id}")
                continue
        unmapped += 1
    deduped = list(dict.fromkeys(mapped))
    return deduped, unmapped


def acl_overlap(acl: list[str], principals: list[str]) -> bool:
    return bool(set(acl) & set(principals))
