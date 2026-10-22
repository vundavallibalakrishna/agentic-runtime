"""Eligibility, previews and standing-approval matching."""

import re
from datetime import datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Any

_PREVIEW_LIMIT = 500
_ARGS_LIMIT = 4096


def render_preview(
    template: object, arguments: dict[str, object], *, title: str
) -> dict[str, object]:
    """Render ``approval_preview`` or a generic argument preview."""
    if not isinstance(template, dict) or not template:
        text = _clip(_pretty(arguments), _ARGS_LIMIT)
        return {"title": title, "summary": text, "fields": [], "links": []}
    fields = []
    raw_fields = template.get("fields")
    if isinstance(raw_fields, list):
        for field in raw_fields:
            if not isinstance(field, dict):
                continue
            path = str(field.get("path") or "")
            fields.append(
                {
                    "label": str(field.get("label") or path),
                    "value": _clip(_subst_value(arguments, path), _PREVIEW_LIMIT),
                }
            )
    diff = None
    raw_diff = template.get("diff")
    if isinstance(raw_diff, dict):
        diff = {
            "before": _subst_value(arguments, str(raw_diff.get("before_path") or "")),
            "after": _subst_value(arguments, str(raw_diff.get("after_path") or "")),
        }
    links = template.get("links") if isinstance(template.get("links"), list) else []
    return {
        "title": _template(str(template.get("title") or title), arguments),
        "summary": _template(str(template.get("summary") or ""), arguments),
        "fields": fields,
        "diff": diff,
        "links": links,
    }


def can_decide(store: Any, actor: Any, approval: dict[str, object]) -> bool:
    """True when this person may decide the approval. Spec 09 §5."""
    if approval.get("status") != "pending":
        return False
    if approval.get("four_eyes") and str(actor.user_id) == str(
        approval.get("requested_for_user_id")
    ):
        return False
    return is_approver(store, actor, approval)


def is_approver(store: Any, actor: Any, approval: dict[str, object]) -> bool:
    """True when this person is named on the approval, including after it is decided."""
    rule = approval.get("approver_rule")
    mode = "requester"
    groups: list[object] = []
    users: list[object] = []
    if isinstance(rule, dict):
        mode = str(rule.get("mode") or "requester")
        groups = list(rule.get("groups") or [])
        users = list(rule.get("users") or [])
    if mode == "requester":
        return str(actor.user_id) == str(approval.get("requested_for_user_id"))
    if mode == "agent_owner":
        return _owns(store, actor, approval)
    if "approvals:decide" not in actor.permissions:
        return False
    if mode == "users":
        return str(actor.user_id) in {str(item) for item in users}
    if mode == "group":
        have = set(store.user_groups.get(actor.user_id, []))
        return any(str(item) in have for item in groups)
    return False


def can_view(actor: Any, approval: dict[str, object], *, eligible: bool) -> bool:
    if eligible:
        return True
    if str(actor.user_id) == str(approval.get("requested_for_user_id")):
        return True
    return "approvals:read_all" in actor.permissions


def consume_standing(store: Any, request: dict[str, object], tool: dict[str, object]) -> str | None:
    """Atomically consume one matching standing approval. Never for W3."""
    if str(tool.get("risk_class") or request.get("risk_class")) == "W3":
        return None
    lock = _lock(store)
    with lock:
        for row in list(store.standing_approvals.values()):
            if not _standing_ok(store, row, request, tool):
                continue
            limit = row.get("max_uses")
            uses = int(row.get("uses") or 0)
            cap = limit if isinstance(limit, int) else 2_147_483_647
            if uses >= cap:
                continue
            row["uses"] = uses + 1
            return str(row["id"])
    return None


def _standing_ok(  # noqa: PLR0911
    store: Any, row: dict[str, object], request: dict[str, object], tool: dict[str, object]
) -> bool:
    from ar_common.time import utcnow  # noqa: PLC0415

    if row.get("revoked_at") is not None:
        return False
    expires = row.get("expires_at")
    if isinstance(expires, datetime) and expires <= utcnow():
        return False
    if row.get("tenant_id") != request.get("tenant_id"):
        return False
    if row.get("tool_id") != tool.get("id"):
        return False
    run = store.runs.get(request.get("run_id")) if request.get("run_id") else None
    routine_id = run.get("routine_id") if isinstance(run, dict) else None
    agent_id = request.get("agent_id") or (run.get("agent_id") if isinstance(run, dict) else None)
    if row.get("routine_id") is not None and row.get("routine_id") != routine_id:
        return False
    if row.get("routine_id") is None and row.get("agent_id") != agent_id:
        return False
    constraints = row.get("argument_constraints")
    if not isinstance(constraints, list):
        return True
    from ar_domain.policy.logic import jsonpath_values, predicate_holds  # noqa: PLC0415

    arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else {}
    for item in constraints:
        if not isinstance(item, dict):
            return False
        path = str(item.get("path") or "$")
        values = jsonpath_values(arguments, path)
        if not predicate_holds(
            str(item.get("op") or "eq"), values, item.get("value"), starred="[*]" in path
        ):
            return False
    return True


def _owns(store: Any, actor: Any, approval: dict[str, object]) -> bool:
    agent = store.agents.get(approval.get("agent_id"))
    if not isinstance(agent, dict):
        return False
    if str(agent.get("owner_user_id")) == str(actor.user_id):
        return True
    team = agent.get("owner_team_id")
    raw_leads = getattr(store, "team_leads", None)
    leads = cast("set[tuple[str, str]]", raw_leads) if isinstance(raw_leads, set) else set()
    return (str(team), str(actor.user_id)) in leads


def _lock(store: Any) -> Any:
    import threading  # noqa: PLC0415

    lock = getattr(store, "approval_lock", None)
    if lock is None:
        lock = threading.Lock()
        store.approval_lock = lock
    return lock


def _template(text: str, arguments: dict[str, object]) -> str:
    def replace(match: re.Match[str]) -> str:
        return _escape(_subst_value(arguments, match.group(1).strip()))

    return _clip(re.sub(r"\{\{\s*(\$\.[^}]+)\s*\}\}", replace, text), _PREVIEW_LIMIT)


def _subst_value(arguments: dict[str, object], path: str) -> str:
    from ar_domain.policy.logic import jsonpath_values  # noqa: PLC0415

    if not path:
        return ""
    values = jsonpath_values(arguments, path if path.startswith("$") else f"$.{path}")
    if not values:
        return ""
    return ", ".join(str(item) for item in values)


def _pretty(arguments: dict[str, object]) -> str:
    import orjson  # noqa: PLC0415

    return orjson.dumps(arguments, option=orjson.OPT_INDENT_2).decode()


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
