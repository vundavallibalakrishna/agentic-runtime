"""Rule matching and the combination algorithm. Spec: docs/03-specs/09-policy-approvals.md §2-3.

The same decisions are implemented in ``policies/rego/ar``. This module is the
in-process evaluator used when ``AR_OPA_URL`` is empty, and the fallback when
OPA does not answer.
"""

import re
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

_R0_BUILTINS = ("knowledge.", "memory.search", "files.list", "files.read", "plan.update")
_EFFECTS = {"allow": "allow", "deny": "deny", "require_approval": "require_approval"}
_WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
_ZONES = ("UTC", "Asia/Kolkata", "America/New_York", "Europe/London")
_OPS = frozenset(
    {
        "eq",
        "neq",
        "in",
        "not_in",
        "matches",
        "not_matches",
        "domain_in",
        "not_domain_in",
        "gt",
        "gte",
        "lt",
        "lte",
        "len_gt",
        "exists",
        "not_exists",
    }
)


def normalize_effect(value: object) -> str:
    """Map a definition effect onto the decision vocabulary."""
    text = str(value or "").replace("Approval", "_approval").replace("approval", "approval")
    compact = re.sub(r"(?<!^)(?=[A-Z])", "_", str(value or "")).lower().replace("-", "_")
    if compact in {"require_approval", "requireapproval"}:
        return "require_approval"
    if compact in _EFFECTS:
        return compact
    if text in _EFFECTS:
        return text
    return "deny"


def enrich_time(now: datetime) -> dict[str, object]:
    """Local weekday and minute-of-day for the zones rules name."""
    zones: dict[str, object] = {}
    for name in _ZONES:
        local = now.astimezone(ZoneInfo(name))
        zones[name] = {
            "weekday": _WEEKDAYS[local.weekday()],
            "minutes": local.hour * 60 + local.minute,
        }
    return {"now": now.isoformat(), "zones": zones}


def evaluate(
    policy_input: Mapping[str, object],
    rules: list[dict[str, object]],
    settings: Mapping[str, object],
) -> dict[str, object]:
    """Combine matching rules. Deny wins, then approval, then allow, then the risk default."""
    matched = [rule for rule in rules if rule_matches(rule, policy_input)]
    denies = [rule for rule in matched if rule.get("effect") == "deny"]
    if denies:
        return _result(
            "deny",
            [str(rule.get("message") or "denied by policy") for rule in denies],
            [str(rule.get("id")) for rule in denies],
            None,
        )
    approvals = [rule for rule in matched if rule.get("effect") == "require_approval"]
    risk = _risk(policy_input)
    if approvals or _w3_allow(matched, risk):
        return _approval_result(policy_input, approvals, matched, settings, risk)
    if any(rule.get("effect") == "allow" for rule in matched):
        return _maybe_override(policy_input, _result("allow", [], _ids(matched), None))
    return _maybe_override(policy_input, _default(policy_input, risk, settings))


def fallback(
    policy_input: Mapping[str, object], rules: list[dict[str, object]]
) -> dict[str, object]:
    """OPA is unreachable. Allow listed R0 built-ins; honour deny rules; otherwise deny."""
    name = _qualified(policy_input)
    if any(name == item or name.startswith(item) for item in _R0_BUILTINS):
        return _result("allow", ["fallback_builtin"], [], None)
    denies = [
        rule for rule in rules if rule.get("effect") == "deny" and rule_matches(rule, policy_input)
    ]
    if denies:
        return _result(
            "deny",
            [str(rule.get("message") or "denied by policy") for rule in denies],
            [str(rule.get("id")) for rule in denies],
            None,
        )
    return _result("deny", ["policy_unavailable"], [], None)


def rule_matches(rule: Mapping[str, object], policy_input: Mapping[str, object]) -> bool:  # noqa: PLR0911
    """A rule matches when every non-empty match field matches."""
    raw = rule.get("match")
    match = raw if isinstance(raw, dict) else {}
    if not _listed(match.get("tools"), _qualified(policy_input), glob=True):
        return False
    if not _listed(match.get("servers"), _tool(policy_input).get("server_slug")):
        return False
    if not _listed(match.get("risk_classes") or match.get("riskClasses"), _risk(policy_input)):
        return False
    if not _listed(match.get("agents"), _agent(policy_input).get("slug")):
        return False
    run = _mapping(policy_input.get("run"))
    if not _listed(match.get("triggers"), run.get("trigger")):
        return False
    if not _listed(match.get("channels"), run.get("channel")):
        return False
    user = _mapping(policy_input.get("user"))
    if not _overlap(match.get("user_groups") or match.get("userGroups"), user.get("groups")):
        return False
    if not _overlap(match.get("user_teams") or match.get("userTeams"), user.get("teams")):
        return False
    if not _attributes(match.get("user_attributes") or match.get("userAttributes"), user):
        return False
    classification = _tool(policy_input).get("data_classification")
    classes = match.get("data_classifications") or match.get("dataClassifications")
    if not _listed(classes, classification):
        return False
    if not _args(match.get("args"), policy_input.get("args")):
        return False
    return _window(match.get("time_window") or match.get("timeWindow"), policy_input.get("time"))


def jsonpath_values(document: object, path: str) -> list[object]:
    """Evaluate the JSONPath subset ``$.a.b``, ``$.a[0]`` and ``$.a[*]``."""
    if not path.startswith("$"):
        return []
    current: list[object] = [document]
    for kind, token in _segments(path[1:]):
        nxt: list[object] = []
        for item in current:
            nxt.extend(_step(item, kind, token))
        current = nxt
    return current


def predicate_holds(op: str, values: list[object], expected: object, *, starred: bool) -> bool:  # noqa: PLR0911
    """Argument predicate. ``[*]`` is true if any element matches; ``not_*`` if any fails."""
    if op not in _OPS:
        return False
    if op == "exists":
        return bool(values)
    if op == "not_exists":
        return not values
    positive = op[4:] if op.startswith("not_") else ("eq" if op == "neq" else op)
    negative = op.startswith("not_") or op == "neq"
    hits = [_positive(positive, value, expected) for value in values]
    if not hits:
        return negative
    if starred:
        return any(not item for item in hits) if negative else any(hits)
    if negative:
        return all(not item for item in hits)
    return all(hits)


def _approval_result(
    policy_input: Mapping[str, object],
    approvals: list[dict[str, object]],
    matched: list[dict[str, object]],
    settings: Mapping[str, object],
    risk: str,
) -> dict[str, object]:
    """W3 allow becomes an owner approval. An explicit W3 approval keeps its approvers."""
    force_owner = risk == "W3" and not approvals
    force_flags = risk == "W3"
    chosen = _winner(approvals) if approvals else None
    requirement = _requirement(chosen, settings, force_owner=force_owner, force_flags=force_flags)
    if approvals:
        requirement = _merge(approvals, requirement, settings, force_flags=force_flags)
    reasons = [str(rule.get("message") or "") for rule in approvals if rule.get("message")]
    if force_owner and not reasons:
        reasons = ["W3 writes need a second person"]
    return _maybe_override(
        policy_input,
        _result("require_approval", reasons, _ids(matched), requirement),
        keep=True,
    )


def _requirement(
    rule: Mapping[str, object] | None,
    settings: Mapping[str, object],
    *,
    force_owner: bool = False,
    force_flags: bool = False,
) -> dict[str, object]:
    raw = (
        rule.get("approval") if rule is not None and isinstance(rule.get("approval"), dict) else {}
    )
    approval = raw if isinstance(raw, dict) else {}
    approvers = approval.get("approvers")
    mode = "requester"
    groups: list[str] = []
    users: list[str] = []
    if isinstance(approvers, dict) and not force_owner:
        mode = str(approvers.get("mode") or "requester")
        groups = _strings(approvers.get("groups"))
        users = _strings(approvers.get("users") or approvers.get("user_ids"))
    if force_owner:
        mode = "agent_owner"
    security = _mapping(settings.get("security"))
    step = bool(approval.get("step_up") or approval.get("stepUp"))
    if force_flags and bool(security.get("require_step_up_for_w3", True)):
        step = True
    ttl = approval.get("ttl_s") if approval.get("ttl_s") is not None else approval.get("ttlS")
    ttl_s = _ttl(ttl, settings)
    required = approval.get("required_approvals")
    if required is None:
        required = approval.get("requiredApprovals")
    count = 1 if not isinstance(required, int) else max(1, min(5, required))
    four = bool(approval.get("four_eyes") or approval.get("fourEyes")) or force_flags
    return {
        "approvers": {"mode": mode, "groups": groups, "users": users},
        "required_approvals": count,
        "four_eyes": four,
        "step_up": step,
        "ttl_s": ttl_s,
        "message": "" if rule is None else str(rule.get("message") or ""),
    }


def _merge(
    rules: list[dict[str, object]],
    base: dict[str, object],
    settings: Mapping[str, object],
    *,
    force_flags: bool = False,
) -> dict[str, object]:
    """Keep the winner's approvers. Counts, flags and TTL combine across matches."""
    counts = [_number(base["required_approvals"])]
    ttls = [_number(base["ttl_s"])]
    four = bool(base["four_eyes"])
    step = bool(base["step_up"])
    for rule in rules:
        requirement = _requirement(rule, settings, force_flags=force_flags)
        counts.append(_number(requirement["required_approvals"]))
        ttls.append(_number(requirement["ttl_s"]))
        four = four or bool(requirement["four_eyes"])
        step = step or bool(requirement["step_up"])
    merged = dict(base)
    merged["required_approvals"] = max(counts)
    merged["ttl_s"] = min(ttls)
    merged["four_eyes"] = four
    merged["step_up"] = step
    return merged


def _default(
    _policy_input: Mapping[str, object],
    risk: str,
    settings: Mapping[str, object],
) -> dict[str, object]:
    if risk == "W3":
        return _result("deny", ["W3 is denied unless a policy asks for approval"], [], None)
    if risk == "W2":
        return _result(
            "require_approval",
            ["writes that affect others wait for approval"],
            [],
            _requirement(None, settings, force_owner=False, force_flags=False),
        )
    return _result("allow", [], [], None)


def _maybe_override(
    policy_input: Mapping[str, object], result: dict[str, object], *, keep: bool = False
) -> dict[str, object]:
    if keep or result["decision"] != "allow":
        return result
    overrides = _mapping(_agent(policy_input).get("overrides"))
    name = str(_tool(policy_input).get("name") or "")
    raw = overrides.get(name)
    flag = raw.get("require_approval") if isinstance(raw, dict) else raw
    text = str(flag or "").lower()
    if text not in {"always", "require_approval"}:
        return result
    settings = _mapping(policy_input.get("settings"))
    return _result(
        "require_approval",
        ["the agent asks for approval on this tool"],
        [str(item) for item in _rule_id_list(result.get("matched_rule_ids"))],
        _requirement(None, settings, force_owner=False, force_flags=False),
    )


def _number(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _rule_id_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _w3_allow(matched: list[dict[str, object]], risk: str) -> bool:
    return risk == "W3" and any(rule.get("effect") == "allow" for rule in matched)


def _winner(rules: list[dict[str, object]]) -> dict[str, object]:
    def key(rule: Mapping[str, object]) -> tuple[int, str]:
        priority = rule.get("priority")
        number = priority if isinstance(priority, int) else 100
        return (number, str(rule.get("policy_name") or ""))

    return sorted(rules, key=key)[0]


def _ttl(value: object, settings: Mapping[str, object]) -> int:
    approvals = _mapping(settings.get("approvals"))
    default = approvals.get("default_ttl_s")
    chosen = value if isinstance(value, int) else default if isinstance(default, int) else 86400
    return max(60, min(7 * 24 * 3600, int(chosen)))


def _listed(expected: object, actual: object, *, glob: bool = False) -> bool:
    items = _strings(expected)
    if not items:
        return True
    text = str(actual or "")
    if glob:
        return any(_glob(item, text) for item in items)
    return text in items


def _glob(pattern: str, text: str) -> bool:
    if pattern in (text, "*"):
        return True
    if pattern.endswith(".*"):
        return text.startswith(pattern[:-1])
    if "*" in pattern:
        return re.fullmatch(pattern.replace(".", r"\.").replace("*", ".*"), text) is not None
    return False


def _overlap(expected: object, actual: object) -> bool:
    items = _strings(expected)
    if not items:
        return True
    have = set(_strings(actual))
    return any(item in have for item in items)


def _attributes(expected: object, user: Mapping[str, object]) -> bool:
    if not isinstance(expected, dict) or not expected:
        return True
    attributes = _mapping(user.get("attributes"))
    for key, allowed in expected.items():
        wanted = _strings(allowed)
        if wanted and str(attributes.get(str(key)) or "") not in wanted:
            return False
    return True


def _args(expected: object, arguments: object) -> bool:
    if not isinstance(expected, list) or not expected:
        return True
    for item in expected:
        if not isinstance(item, dict):
            return False
        path = str(item.get("path") or "$")
        values = jsonpath_values(arguments, path)
        starred = "[*]" in path
        if not predicate_holds(
            str(item.get("op") or ""), values, item.get("value"), starred=starred
        ):
            return False
    return True


def _window(window: object, clock: object) -> bool:
    if not isinstance(window, dict) or not window:
        return True
    zones = _mapping(_mapping(clock).get("zones"))
    zone = str(window.get("timezone") or "UTC")
    local = _mapping(zones.get(zone))
    if not local:
        return False
    days = [item.upper() for item in _strings(window.get("days"))]
    if days and str(local.get("weekday") or "") not in days:
        return False
    start = _minutes(window.get("from"))
    end = _minutes(window.get("to"))
    now = local.get("minutes")
    if not isinstance(now, int) or start is None or end is None:
        return False
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end


def _minutes(value: object) -> int | None:
    text = str(value or "")
    parts = text.split(":")
    if len(parts) != 2:
        return None
    try:
        return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        return None


def _positive(op: str, value: object, expected: object) -> bool:  # noqa: PLR0911
    if op == "eq":
        return value == expected
    if op == "in":
        return value in expected if isinstance(expected, list) else value == expected
    if op == "matches":
        return isinstance(value, str) and _search(str(expected or ""), value)
    if op == "domain_in":
        return _domain(value) in {item.lower() for item in _strings(expected)}
    if op in {"gt", "gte", "lt", "lte"}:
        return _compare(op, value, expected)
    if op == "len_gt":
        length = len(value) if isinstance(value, (str, list)) else -1
        return isinstance(expected, int) and length > expected
    return False


def _compare(op: str, value: object, expected: object) -> bool:
    if isinstance(value, bool) or isinstance(expected, bool):
        return False
    if not isinstance(value, (int, float)) or not isinstance(expected, (int, float)):
        return False
    if op == "gt":
        return value > expected
    if op == "gte":
        return value >= expected
    if op == "lt":
        return value < expected
    return value <= expected


def _search(pattern: str, value: str) -> bool:
    if len(pattern) > 200:
        return False
    try:
        return re.search(pattern, value) is not None
    except re.error:
        return False


def _domain(value: object) -> str:
    text = str(value or "").strip().lower()
    if "://" in text:
        text = text.split("://", 1)[1].split("/", 1)[0]
    if "@" in text:
        text = text.split("@", 1)[1]
    return text.split(":")[0]


def _segments(rest: str) -> list[tuple[str, str]]:
    body = rest[1:] if rest.startswith(".") else rest
    found: list[tuple[str, str]] = []
    for part in body.split("."):
        if not part:
            continue
        if part.endswith("[*]"):
            found.append(("key", part[:-3]))
            found.append(("star", ""))
        elif "[" in part and part.endswith("]"):
            name, index = part[:-1].split("[", 1)
            if name:
                found.append(("key", name))
            found.append(("index", index))
        else:
            found.append(("key", part))
    return found


def _step(item: object, kind: str, token: str) -> list[object]:
    if kind == "star":
        if isinstance(item, list):
            return list(item)
        return []
    if kind == "index":
        if isinstance(item, list) and token.isdigit():
            number = int(token)
            return [item[number]] if 0 <= number < len(item) else []
        return []
    if isinstance(item, dict) and token in item:
        return [item[token]]
    return []


def _result(
    decision: str, reasons: list[str], rule_ids: list[str], approval: dict[str, object] | None
) -> dict[str, object]:
    return {
        "decision": decision,
        "reasons": [item for item in reasons if item],
        "matched_rule_ids": rule_ids,
        "approval": approval,
        "standing_approval_id": None,
    }


def _ids(rules: list[dict[str, object]]) -> list[str]:
    return [str(rule.get("id")) for rule in rules]


def _qualified(policy_input: Mapping[str, object]) -> str:
    return str(_tool(policy_input).get("qualified_name") or "")


def _risk(policy_input: Mapping[str, object]) -> str:
    return str(_tool(policy_input).get("risk_class") or "R1")


def _tool(policy_input: Mapping[str, object]) -> dict[str, object]:
    return _mapping(policy_input.get("tool"))


def _agent(policy_input: Mapping[str, object]) -> dict[str, object]:
    return _mapping(policy_input.get("agent"))


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []
