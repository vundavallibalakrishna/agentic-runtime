"""Author, version and simulate policies. Spec: docs/03-specs/09-policy-approvals.md §4."""

import hashlib
import uuid
from typing import TYPE_CHECKING, Any, cast

import orjson

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.policy.logic import enrich_time, evaluate, normalize_effect
from ar_domain.rows import as_dict, as_int, as_list

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_MAX_POLICIES = 100
_MAX_RULES = 200


class PolicyBook:
    """In-process policy catalogue. Postgres tables are revision 0012."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_policies(self, actor: Actor) -> list[dict[str, object]]:
        rows = [
            self._summary(row)
            for row in self.store.policies.values()
            if row.get("tenant_id") == actor.tenant_id
        ]
        rows.sort(key=lambda item: (as_int(item["priority"]), str(item["name"])))
        return rows

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        self._limit(actor)
        name = str(body.get("name") or "").strip()
        if not name or self._named(actor.tenant_id, name) is not None:
            raise ConflictError("a policy with that name already exists")
        kind = str(body.get("kind") or "rules")
        if kind not in {"rules", "rego"}:
            raise ValidationFailedError("kind must be rules or rego")
        rego = body.get("rego")
        if kind == "rego":
            self._rego_allowed(actor, rego)
        policy_id = new_id()
        now = utcnow()
        priority = body.get("priority")
        row = {
            "id": policy_id,
            "tenant_id": actor.tenant_id,
            "name": name,
            "description": str(body.get("description") or ""),
            "kind": kind,
            "status": "draft",
            "priority": priority if isinstance(priority, int) else 100,
            "active_version_id": None,
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self.store.policies[policy_id] = row
        version = self._add_version(actor, row, body, number=1)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="policy.created",
            target_type="policy",
            target_id=policy_id,
            detail={"name": name},
        )
        return self._detail(row, version)

    def get(self, actor: Actor, policy_id: uuid.UUID) -> dict[str, object]:
        row = self._require(actor, policy_id)
        return self._detail(row, self._latest(row))

    def patch(
        self, actor: Actor, policy_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._require(actor, policy_id)
        if body.get("name"):
            other = self._named(actor.tenant_id, str(body["name"]))
            if other is not None and other["id"] != policy_id:
                raise ConflictError("a policy with that name already exists")
            row["name"] = str(body["name"])
        if "description" in body:
            row["description"] = str(body["description"] or "")
        if isinstance(body.get("priority"), int):
            row["priority"] = body["priority"]
        row["updated_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="policy.updated",
            target_type="policy",
            target_id=policy_id,
            detail={"name": row["name"]},
        )
        return self._detail(row, self._latest(row))

    def delete(self, actor: Actor, policy_id: uuid.UUID) -> None:
        row = self._require(actor, policy_id)
        if row["status"] not in {"draft", "disabled"}:
            raise ConflictError("only a draft or disabled policy can be deleted")
        for version_id, version in list(self.store.policy_versions.items()):
            if version.get("policy_id") == policy_id:
                del self.store.policy_versions[version_id]
        del self.store.policies[policy_id]
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="policy.deleted",
            target_type="policy",
            target_id=policy_id,
            detail={"name": row["name"]},
        )

    def versions(self, actor: Actor, policy_id: uuid.UUID) -> list[dict[str, object]]:
        self._require(actor, policy_id)
        rows = [
            self._version_view(row)
            for row in self.store.policy_versions.values()
            if row.get("policy_id") == policy_id
        ]
        rows.sort(key=lambda item: as_int(item["version"]))
        return rows

    def add_version(
        self, actor: Actor, policy_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._require(actor, policy_id)
        if row["kind"] == "rego":
            self._rego_allowed(actor, body.get("rego"))
        latest = self._latest(row)
        number = 1 if latest is None else as_int(latest["version"]) + 1
        version = self._add_version(actor, row, body, number=number)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="policy.version_created",
            target_type="policy_version",
            target_id=version["id"],
            detail={"version": number, "passed": _passed(version)},
        )
        return self._version_view(version)

    def activate(
        self, actor: Actor, policy_id: uuid.UUID, version: int, *, stepped_up: bool
    ) -> dict[str, object]:
        if actor.auth_method == "session" and not stepped_up:
            from ar_domain.approvals.errors import StepUpRequiredError  # noqa: PLC0415

            raise StepUpRequiredError()
        row = self._require(actor, policy_id)
        found = self._by_number(policy_id, version)
        if found is None:
            raise NotFoundError("policy version not found")
        if not _passed(found):
            raise ValidationFailedError("policy tests must pass before activation")
        self._one_active(actor.tenant_id, policy_id)
        row["active_version_id"] = found["id"]
        row["status"] = "active"
        row["updated_at"] = utcnow()
        self._event("policy.activated", row, found)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="policy.activated",
            target_type="policy",
            target_id=policy_id,
            detail={"version": version, "hash": found["hash"]},
        )
        self._rebuild()
        return self._detail(row, found)

    def disable(self, actor: Actor, policy_id: uuid.UUID) -> dict[str, object]:
        row = self._require(actor, policy_id)
        row["status"] = "disabled"
        row["active_version_id"] = None
        row["updated_at"] = utcnow()
        self._event("policy.disabled", row, None)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="policy.disabled",
            target_type="policy",
            target_id=policy_id,
            detail={},
        )
        self._rebuild()
        return self._detail(row, self._latest(row))

    def simulate(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        built = build_input(self.store, actor, body)
        drafts = body.get("include_drafts") or []
        rules = active_rules(self.store, actor.tenant_id)
        if isinstance(drafts, list):
            for item in drafts:
                rules.extend(self._draft_rules(actor, item))
        decision = evaluate(built, rules, _settings(self.store, actor.tenant_id))
        trace = _trace(rules, built)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="policy.simulated",
            target_type="policy",
            target_id=actor.tenant_id,
            detail={"decision": decision["decision"]},
        )
        from ar_domain.approvals.sod import SodBook  # noqa: PLC0415

        sod = SodBook(self.store).simulate(actor, body, decision)
        return {**decision, "trace": trace, "sod": sod}

    def _add_version(
        self, actor: Actor, policy: dict[str, object], body: dict[str, object], *, number: int
    ) -> dict[str, object]:
        document = body.get("document")
        rego = body.get("rego")
        if policy["kind"] == "rules":
            if not isinstance(document, dict):
                raise ValidationFailedError("a rules policy needs a document")
            rules = document.get("rules")
            if isinstance(rules, list) and len(rules) > _MAX_RULES:
                raise ValidationFailedError("a policy can hold at most 200 rules")
            rego = None
        else:
            if not isinstance(rego, str) or not rego.strip():
                raise ValidationFailedError("a rego policy needs a module")
            document = None
        report = {"passed": True, "failed": []}
        if isinstance(document, dict):
            report = _run_tests(self.store, actor, policy, document)
        version_id = new_id()
        payload = document if document is not None else {"rego": rego}
        row = {
            "id": version_id,
            "tenant_id": actor.tenant_id,
            "policy_id": policy["id"],
            "version": number,
            "document": document,
            "rego": rego,
            "hash": hashlib.sha256(orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)).hexdigest(),
            "test_report": report,
            "created_by": actor.user_id,
            "created_at": utcnow(),
        }
        self.store.policy_versions[version_id] = row
        policy["updated_at"] = row["created_at"]
        return row

    def _draft_rules(self, actor: Actor, policy_id: object) -> list[dict[str, object]]:
        try:
            found = uuid.UUID(str(policy_id))
        except ValueError:
            return []
        row = self.store.policies.get(found)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            return []
        latest = self._latest(row)
        if latest is None:
            return []
        return compile_rules(row, latest)

    def _rebuild(self) -> None:
        from ar_domain.policy.bundle import store_bundle  # noqa: PLC0415

        store_bundle(self.store)

    def _event(
        self, topic: str, policy: dict[str, object], version: dict[str, object] | None
    ) -> None:
        self.store.domain_events.append(
            {
                "topic": topic,
                "payload": {
                    "policy_id": str(policy["id"]),
                    "policy_version_id": None if version is None else str(version["id"]),
                },
                "at": utcnow().isoformat(),
            }
        )

    def _limit(self, actor: Actor) -> None:
        count = sum(
            1 for row in self.store.policies.values() if row.get("tenant_id") == actor.tenant_id
        )
        if count >= _MAX_POLICIES:
            raise ValidationFailedError("a tenant can have at most 100 policies")

    def _named(self, tenant_id: uuid.UUID, name: str) -> dict[str, object] | None:
        for row in self.store.policies.values():
            if row.get("tenant_id") == tenant_id and row.get("name") == name:
                return cast("dict[str, object]", row)
        return None

    def _require(self, actor: Actor, policy_id: uuid.UUID) -> dict[str, object]:
        row = self.store.policies.get(policy_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("policy not found")
        return row

    def _latest(self, policy: dict[str, object]) -> dict[str, object] | None:
        rows = [
            row
            for row in self.store.policy_versions.values()
            if row.get("policy_id") == policy["id"]
        ]
        if not rows:
            return None
        return cast("dict[str, object]", max(rows, key=lambda item: as_int(item["version"])))

    def _by_number(self, policy_id: object, number: int) -> dict[str, object] | None:
        for row in self.store.policy_versions.values():
            if row.get("policy_id") == policy_id and as_int(row["version"]) == number:
                return cast("dict[str, object]", row)
        return None

    def _summary(self, row: dict[str, object]) -> dict[str, object]:
        latest = self._latest(row)
        active = row.get("active_version_id")
        active_row = self.store.policy_versions.get(active) if active is not None else None
        return {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "kind": row["kind"],
            "status": row["status"],
            "priority": row["priority"],
            "active_version": None if not isinstance(active_row, dict) else active_row["version"],
            "latest_version": 0 if latest is None else latest["version"],
            "updated_at": row["updated_at"],
        }

    def _detail(
        self, row: dict[str, object], version: dict[str, object] | None
    ) -> dict[str, object]:
        body = self._summary(row)
        body["active"] = (
            None
            if row.get("active_version_id") is None
            else self._version_view(self.store.policy_versions.get(row["active_version_id"]) or {})
        )
        body["latest"] = None if version is None else self._version_view(version)
        return body

    def _version_view(self, row: dict[str, object]) -> dict[str, object]:
        if not row:
            return {}
        return {
            "id": row.get("id"),
            "version": row.get("version"),
            "document": row.get("document"),
            "rego": row.get("rego"),
            "hash": row.get("hash"),
            "test_report": row.get("test_report"),
            "created_at": row.get("created_at"),
        }

    def _rego_allowed(self, actor: Actor, rego: object) -> None:
        features = _mapping(_settings(self.store, actor.tenant_id).get("features"))
        if features.get("custom_rego") is not True:
            raise ValidationFailedError("custom rego is not enabled")
        if not isinstance(rego, str) or "package " not in rego:
            raise ValidationFailedError("rego must declare a package")
        from ar_domain.policy.bundle import opa_check  # noqa: PLC0415

        opa_check(rego)

    def _one_active(self, tenant_id: uuid.UUID, keep: uuid.UUID) -> None:
        del tenant_id, keep


def active_rules(store: Any, tenant_id: uuid.UUID) -> list[dict[str, object]]:
    """Rules from every active policy version in the tenant."""
    found: list[dict[str, object]] = []
    for policy in store.policies.values():
        if policy.get("tenant_id") != tenant_id or policy.get("status") != "active":
            continue
        version = store.policy_versions.get(policy.get("active_version_id"))
        if isinstance(version, dict):
            found.extend(compile_rules(policy, version))
    return found


def compile_rules(policy: dict[str, object], version: dict[str, object]) -> list[dict[str, object]]:
    """Turn a stored document into evaluator rules."""
    document = version.get("document")
    if not isinstance(document, dict):
        return []
    rules = document.get("rules")
    if not isinstance(rules, list):
        return []
    compiled: list[dict[str, object]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        compiled.append(
            {
                "id": str(rule.get("id") or ""),
                "policy_id": str(policy["id"]),
                "policy_name": str(policy.get("name") or ""),
                "priority": policy.get("priority")
                if isinstance(policy.get("priority"), int)
                else 100,
                "effect": normalize_effect(rule.get("effect")),
                "match": rule.get("match") if isinstance(rule.get("match"), dict) else {},
                "approval": rule.get("approval") if isinstance(rule.get("approval"), dict) else {},
                "message": str(rule.get("message") or ""),
            }
        )
    return compiled


def build_input(store: Any, actor: Actor, body: dict[str, object]) -> dict[str, object]:
    """PolicyInput for a hypothetical call or a past tool call."""
    past = body.get("tool_call_id")
    if past:
        return _from_call(store, actor, past)
    name = str(body.get("tool_qualified_name") or "")
    version = _version_named(store, actor.tenant_id, name)
    tool = {
        "qualified_name": name,
        "name": name.split(".", 1)[-1],
        "server_slug": name.split(".", 1)[0] if "." in name else "",
        "risk_class": "R1" if version is None else version.get("risk_class"),
        "data_classification": "internal"
        if version is None
        else version.get("data_classification"),
        "annotations": {},
    }
    agent = _agent_input(store, body.get("agent_id"))
    user_id = body.get("user_id") or actor.user_id
    return {
        "tenant_id": str(actor.tenant_id),
        "tool": tool,
        "agent": agent,
        "run": {
            "id": "",
            "trigger": str(body.get("trigger") or "chat"),
            "channel": str(body.get("channel") or "web"),
            "depth": 0,
            "routine_id": None,
        },
        "user": _user_input(store, user_id, actor),
        "args": body.get("args") if isinstance(body.get("args"), dict) else {},
        "time": enrich_time(utcnow()),
        "settings": _settings(store, actor.tenant_id),
    }


def _run_tests(
    store: Any, actor: Actor, policy: dict[str, object], document: dict[str, object]
) -> dict[str, object]:
    tests = document.get("tests")
    if not isinstance(tests, list) or not tests:
        return {"passed": True, "failed": []}
    rules = compile_rules(policy, {"document": document})
    failed: list[dict[str, object]] = []
    for case in tests:
        if not isinstance(case, dict):
            continue
        sample = as_dict(case.get("input"))
        expect = as_dict(case.get("expect"))
        built = _test_input(store, actor, sample)
        got = evaluate(built, rules, _settings(store, actor.tenant_id))
        wanted = normalize_effect(expect.get("decision"))
        rule_ids = expect.get("rule_ids") or expect.get("ruleIds")
        if got["decision"] != wanted or (
            isinstance(rule_ids, list) and list(rule_ids) != got["matched_rule_ids"]
        ):
            failed.append({"name": str(case.get("name") or "test"), "got": got["decision"]})
    return {"passed": not failed, "failed": failed}


def _test_input(store: Any, actor: Actor, sample: dict[str, object]) -> dict[str, object]:
    tool = as_dict(sample.get("tool"))
    user = as_dict(sample.get("user"))
    name = str(tool.get("qualified_name") or tool.get("qualifiedName") or "tool.example")
    return {
        "tenant_id": str(actor.tenant_id),
        "tool": {
            "qualified_name": name,
            "name": name.split(".", 1)[-1],
            "server_slug": name.split(".", 1)[0] if "." in name else "",
            "risk_class": str(tool.get("risk_class") or tool.get("riskClass") or "W2"),
            "data_classification": "internal",
            "annotations": {},
        },
        "agent": {"id": "", "slug": "", "risk_tier": "medium", "overrides": {}},
        "run": {
            "id": "",
            "trigger": str(sample.get("trigger") or "chat"),
            "channel": str(sample.get("channel") or "web"),
            "depth": 0,
            "routine_id": None,
        },
        "user": {
            "id": str(actor.user_id),
            "groups": as_list(user.get("groups")),
            "teams": [],
            "roles": [],
            "attributes": as_dict(user.get("attributes")),
        },
        "args": sample.get("args") if isinstance(sample.get("args"), dict) else {},
        "time": enrich_time(utcnow()),
        "settings": _settings(store, actor.tenant_id),
    }


def _from_call(store: Any, actor: Actor, tool_call_id: object) -> dict[str, object]:
    try:
        found = uuid.UUID(str(tool_call_id))
    except ValueError as exc:
        raise NotFoundError("tool call not found") from exc
    row = store.tool_calls.get(found)
    if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
        raise NotFoundError("tool call not found")
    return build_input(
        store,
        actor,
        {
            "tool_qualified_name": row.get("qualified_name"),
            "args": row.get("arguments_redacted"),
        },
    )


def _version_named(store: Any, tenant_id: uuid.UUID, qualified: str) -> dict[str, object] | None:
    for row in store.tool_versions.values():
        if row.get("qualified_name") != qualified:
            continue
        server_version = store.tool_server_versions.get(row.get("tool_server_version_id"))
        server = (
            store.tool_servers.get(server_version.get("tool_server_id"))
            if isinstance(server_version, dict)
            else None
        )
        if isinstance(server, dict) and server.get("tenant_id") not in {None, tenant_id}:
            continue
        return cast("dict[str, object]", row)
    return None


def _agent_input(store: Any, agent_id: object) -> dict[str, object]:
    if not agent_id:
        return {"id": "", "slug": "", "risk_tier": "medium", "overrides": {}}
    try:
        found = uuid.UUID(str(agent_id))
    except ValueError:
        return {"id": "", "slug": "", "risk_tier": "medium", "overrides": {}}
    agent = store.agents.get(found)
    if not isinstance(agent, dict):
        return {"id": str(found), "slug": "", "risk_tier": "medium", "overrides": {}}
    version = store.versions.get(agent.get("published_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else {}
    return {
        "id": str(found),
        "slug": str(agent.get("slug") or ""),
        "risk_tier": "medium",
        "overrides": _overrides(definition if isinstance(definition, dict) else {}),
        "owner_user_id": str(agent.get("owner_user_id") or ""),
    }


def _overrides(definition: dict[str, object]) -> dict[str, object]:
    found: dict[str, object] = {}
    tools = definition.get("tools")
    if not isinstance(tools, list):
        return found
    for binding in tools:
        if not isinstance(binding, dict):
            continue
        raw = binding.get("overrides")
        if isinstance(raw, dict):
            found.update(raw)
    return found


def _user_input(store: Any, user_id: object, actor: Actor) -> dict[str, object]:
    try:
        found = uuid.UUID(str(user_id))
    except ValueError:
        found = actor.user_id
    groups = store.user_groups.get(found, []) if hasattr(store, "user_groups") else []
    roles = store.user_roles.get(found, set()) if hasattr(store, "user_roles") else set()
    return {
        "id": str(found),
        "groups": list(groups),
        "teams": list(actor.team_ids) if found == actor.user_id else [],
        "roles": list(roles),
        "attributes": {},
    }


def _settings(store: Any, tenant_id: uuid.UUID) -> dict[str, object]:
    raw = store.tenant_settings.get(tenant_id) if hasattr(store, "tenant_settings") else None
    base = raw if isinstance(raw, dict) else {}
    security = _mapping(base.get("security"))
    security.setdefault("require_step_up_for_w3", True)
    security.setdefault("require_step_up_for_signoff", True)
    approvals = _mapping(base.get("approvals"))
    approvals.setdefault("default_ttl_s", 86400)
    features = _mapping(base.get("features"))
    return {**base, "security": security, "approvals": approvals, "features": features}


def _trace(
    rules: list[dict[str, object]], policy_input: dict[str, object]
) -> list[dict[str, object]]:
    from ar_domain.policy.logic import rule_matches  # noqa: PLC0415

    return [
        {
            "policy": rule.get("policy_name"),
            "rule_id": rule.get("id"),
            "matched": rule_matches(rule, policy_input),
        }
        for rule in rules
    ]


def _passed(version: dict[str, object]) -> bool:
    report = version.get("test_report")
    if not isinstance(report, dict):
        return True
    return report.get("passed") is not False


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return {str(key): item for key, item in value.items()}
    return {}
