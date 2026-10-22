"""Tool server lifecycle on the process store. Spec: docs/03-specs/08-tool-registry-mcp.md."""

import uuid
from typing import TYPE_CHECKING, Any, cast

from ar_common.errors import ArError, ConflictError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.tools.logic import (
    as_mapping,
    description_hash,
    hash_embedding,
    manifest_hash,
    name_ok,
    semver_greater,
    slug_ok,
)
from ar_domain.tools.openapi_import import OpenApiError, load_document, operations_from
from ar_domain.tools.remote_mcp import RemoteError, list_remote
from ar_domain.tools.views import server_view, tool_summary, tool_version_view, version_view

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_ECHO = [
    {
        "name": "ping",
        "title": "Ping",
        "description": "Return the message so a reviewer can see the tool.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        "risk_class": "R0",
        "annotations": {"readOnlyHint": True},
    }
]


class ToolRegistry:
    """Registry operations over the chat store dictionaries."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def ensure_seed(self) -> None:
        from ar_domain.tools.seed_tools import seed  # noqa: PLC0415

        seed(self.store)

    def list_servers(
        self,
        actor: Actor,
        *,
        q: str | None = None,
        kind: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        include_builtin: bool = True,
    ) -> list[dict[str, object]]:
        rows = []
        for row in self.store.tool_servers.values():
            if not self._visible(actor, row):
                continue
            if not include_builtin and row.get("tenant_id") is None:
                continue
            if kind and row.get("kind") != kind:
                continue
            if status and row.get("status") != status:
                continue
            if owner == "me" and row.get("owner_user_id") != actor.user_id:
                continue
            if q and q.lower() not in f"{row.get('name')} {row.get('slug')}".lower():
                continue
            rows.append(server_view(self.store, row))
        return sorted(rows, key=lambda item: str(item["name"]).lower())

    def get_server(self, actor: Actor, server_id: uuid.UUID) -> dict[str, object]:
        return server_view(self.store, self._server(actor, server_id))

    def create_server(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        self._need(actor, "tools:create")
        slug = str(body.get("slug") or "")
        if not slug_ok(slug):
            raise ValidationFailedError("slug must be a short lowercase name")
        if self._slug_taken(actor.tenant_id, slug):
            raise ConflictError("a tool server with that slug already exists")
        from ar_domain.identity.plan_limits import guard  # noqa: PLC0415

        servers = sum(
            1 for row in self.store.tool_servers.values() if row.get("tenant_id") == actor.tenant_id
        )
        guard(self.store, actor.tenant_id, "max_tool_servers", 1, current=servers)
        version = body.get("version")
        if not isinstance(version, dict):
            raise ValidationFailedError("version is required")
        server_id = new_id()
        now = utcnow()
        self.store.tool_servers[server_id] = {
            "id": server_id,
            "tenant_id": actor.tenant_id,
            "slug": slug,
            "name": str(body.get("name") or slug),
            "description": str(body.get("description") or ""),
            "kind": str(body.get("kind") or "remote_mcp"),
            "owner_team_id": body.get("owner_team_id"),
            "owner_user_id": actor.user_id,
            "status": "draft",
            "disabled_at": None,
            "disabled_reason": None,
            "current_version_id": None,
            "created_at": now,
            "updated_at": now,
        }
        created = self._add_version(actor, server_id, version)
        self._audit(actor, "tool_server.created", server_id, {"slug": slug})
        view = server_view(self.store, self.store.tool_servers[server_id])
        view["versions"] = [created]
        return view

    def patch_server(
        self, actor: Actor, server_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._server(actor, server_id)
        self._owner_or_review(actor, row)
        for key in ("name", "description", "owner_team_id", "owner_user_id"):
            if key in body and body[key] is not None:
                row[key] = body[key]
        row["updated_at"] = utcnow()
        self._audit(actor, "tool_server.updated", server_id, {})
        return server_view(self.store, row)

    def delete_server(self, actor: Actor, server_id: uuid.UUID) -> None:
        row = self._server(actor, server_id)
        self._owner_or_review(actor, row)
        if row.get("tenant_id") is None:
            raise ArError(ErrorCode.FORBIDDEN, "platform servers stay installed")
        used = self._where_used(str(row["slug"]))
        if used:
            raise ConflictError("a published agent still binds this server")
        self.store.tool_servers.pop(server_id, None)
        self._audit(actor, "tool_server.deleted", server_id, {})

    def list_versions(self, actor: Actor, server_id: uuid.UUID) -> list[dict[str, object]]:
        self._server(actor, server_id)
        rows = [
            version_view(self.store, row)
            for row in self.store.tool_server_versions.values()
            if row.get("tool_server_id") == server_id
        ]
        return sorted(rows, key=lambda item: str(item["version"]))

    def create_version(
        self, actor: Actor, server_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._server(actor, server_id)
        self._owner_or_review(actor, row)
        return self._add_version(actor, server_id, body)

    def get_version(
        self, actor: Actor, server_id: uuid.UUID, version_id: uuid.UUID
    ) -> dict[str, object]:
        self._server(actor, server_id)
        return version_view(self.store, self._version(version_id, server_id), tools=True)

    def discover(
        self, actor: Actor, server_id: uuid.UUID, version_id: uuid.UUID
    ) -> dict[str, object]:
        server = self._server(actor, server_id)
        self._owner_or_review(actor, server)
        version = self._version(version_id, server_id)
        if version.get("review_status") == "approved":
            raise ArError(ErrorCode.INVALID_STATE, "approved versions are immutable")
        tools = self._catalogue(server, version)
        self._replace_tools(server, version, tools, actor)
        return {
            "tool_count": len(tools),
            "manifest_hash": version.get("manifest_hash"),
            "errors": [],
        }

    def patch_tool(
        self,
        actor: Actor,
        server_id: uuid.UUID,
        version_id: uuid.UUID,
        tool_version_id: uuid.UUID,
        body: dict[str, object],
    ) -> dict[str, object]:
        server = self._server(actor, server_id)
        version = self._version(version_id, server_id)
        if version.get("review_status") == "approved":
            raise ArError(
                ErrorCode.INVALID_STATE, "create a new version to change an approved tool"
            )
        pending = (
            version.get("review_status") == "pending" and server.get("status") == "pending_review"
        )
        if pending:
            self._need(actor, "tools:review")
        else:
            self._owner_or_review(actor, server)
        row = self._tool_version(tool_version_id, version_id)
        self._apply_tool_patch(row, body)
        self._audit(
            actor, "tool.updated", row.get("tool_id"), {"risk_class": row.get("risk_class")}
        )
        return tool_version_view(row)

    def submit(
        self, actor: Actor, server_id: uuid.UUID, version_id: uuid.UUID
    ) -> dict[str, object]:
        server = self._server(actor, server_id)
        self._owner_or_review(actor, server)
        version = self._version(version_id, server_id)
        tools = [
            row
            for row in self.store.tool_versions.values()
            if row.get("tool_server_version_id") == version_id
        ]
        if not tools or any(row.get("risk_confirmed") is not True for row in tools):
            raise ValidationFailedError("confirm a risk class on every tool before review")
        version["review_status"] = "pending"
        server["status"] = "pending_review"
        server["updated_at"] = utcnow()
        self._audit(actor, "tool_server.review_requested", server_id, {"reason": "new_version"})
        self._event(
            "tool_server.review_requested",
            {"tool_server_id": str(server_id), "reason": "new_version"},
        )
        return version_view(self.store, version)

    def approve(
        self, actor: Actor, server_id: uuid.UUID, version_id: uuid.UUID, notes: str = ""
    ) -> dict[str, object]:
        self._need(actor, "tools:review")
        server = self._server(actor, server_id)
        version = self._version(version_id, server_id)
        self._four_eyes(actor, version)
        now = utcnow()
        version["review_status"] = "approved"
        version["review_notes"] = notes
        version["reviewed_by"] = actor.user_id
        version["reviewed_at"] = now
        server["status"] = "approved"
        server["current_version_id"] = version_id
        server["updated_at"] = now
        for row in self.store.tool_versions.values():
            if row.get("tool_server_version_id") == version_id:
                row["embedding"] = hash_embedding(str(row.get("description") or ""))
        self._audit(actor, "tool_server.approved", server_id, {})
        self._event(
            "tool_server.review_decided",
            {"tool_server_version_id": str(version_id), "decision": "approved"},
        )
        return version_view(self.store, version)

    def reject(
        self, actor: Actor, server_id: uuid.UUID, version_id: uuid.UUID, notes: str
    ) -> dict[str, object]:
        self._need(actor, "tools:review")
        if not notes.strip():
            raise ValidationFailedError("notes are required")
        server = self._server(actor, server_id)
        version = self._version(version_id, server_id)
        version["review_status"] = "rejected"
        version["review_notes"] = notes
        version["reviewed_by"] = actor.user_id
        version["reviewed_at"] = utcnow()
        server["status"] = "rejected"
        server["updated_at"] = utcnow()
        self._audit(actor, "tool_server.rejected", server_id, {})
        self._event(
            "tool_server.review_decided",
            {"tool_server_version_id": str(version_id), "decision": "rejected"},
        )
        return version_view(self.store, version)

    def set_server_status(
        self, actor: Actor, server_id: uuid.UUID, action: str, reason: str = ""
    ) -> dict[str, object]:
        server = self._server(actor, server_id)
        if action == "deprecate":
            self._owner_or_review(actor, server)
            server["status"] = "deprecated"
            self._audit(actor, "tool_server.deprecated", server_id, {})
        elif action == "disable":
            self._need(actor, "tools:disable")
            if not reason.strip():
                raise ValidationFailedError("a reason is required")
            server["disabled_at"] = utcnow()
            server["disabled_reason"] = reason
            self._audit(actor, "tool_server.disabled", server_id, {"reason": reason})
        elif action == "enable":
            self._need(actor, "tools:disable")
            server["disabled_at"] = None
            server["disabled_reason"] = None
            self._audit(actor, "tool_server.enabled", server_id, {})
        else:
            raise ValidationFailedError("unknown action")
        server["updated_at"] = utcnow()
        return server_view(self.store, server)

    def list_tools(
        self,
        actor: Actor,
        *,
        q: str | None = None,
        server_id: uuid.UUID | None = None,
        risk_class: str | None = None,
    ) -> list[dict[str, object]]:
        rows = []
        for tool in self.store.tool_defs.values():
            if not self._tool_visible(actor, tool):
                continue
            if server_id and tool.get("tool_server_id") != server_id:
                continue
            version = self._current_tool_version(tool)
            if version is None:
                continue
            if risk_class and version.get("risk_class") != risk_class:
                continue
            if (
                q
                and q.lower()
                not in f"{version.get('qualified_name')} {version.get('description')}".lower()
            ):
                continue
            rows.append(tool_summary(self.store, tool, version))
        return rows

    def get_tool(self, actor: Actor, tool_id: uuid.UUID) -> dict[str, object]:
        tool = self._tool(actor, tool_id)
        version = self._current_tool_version(tool)
        if version is None:
            raise NotFoundError()
        body = tool_summary(self.store, tool, version)
        body["calls_7d"] = self._stats(tool_id)
        body["input_schema"] = version.get("input_schema") or {}
        return body

    def set_tool_enabled(
        self, actor: Actor, tool_id: uuid.UUID, *, enabled: bool, reason: str = ""
    ) -> dict[str, object]:
        self._need(actor, "tools:disable")
        tool = self._tool(actor, tool_id)
        if enabled:
            tool["disabled_at"] = None
            tool["disabled_reason"] = None
            self._audit(actor, "tool.enabled", tool_id, {})
        else:
            if not reason.strip():
                raise ValidationFailedError("a reason is required")
            tool["disabled_at"] = utcnow()
            tool["disabled_reason"] = reason
            self._audit(actor, "tool.disabled", tool_id, {"reason": reason})
        tool["updated_at"] = utcnow()
        if not enabled:
            from ar_domain.policy.bundle import store_bundle  # noqa: PLC0415

            store_bundle(self.store)
        version = self._current_tool_version(tool)
        if version is None:
            raise NotFoundError()
        return tool_summary(self.store, tool, version)

    def _add_version(
        self, actor: Actor, server_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        server = self.store.tool_servers[server_id]
        number = str(body.get("version") or "1.0.0")
        existing = [
            str(row.get("version"))
            for row in self.store.tool_server_versions.values()
            if row.get("tool_server_id") == server_id
        ]
        if existing and not semver_greater(number, existing):
            raise ValidationFailedError("version must be greater than the current versions")
        if not existing and semver_greater(number, []) is False:
            raise ValidationFailedError("version must be a semantic version")
        endpoint, auth_mode, config = self._endpoint(server, body)
        version_id = new_id()
        now = utcnow()
        self.store.tool_server_versions[version_id] = {
            "id": version_id,
            "tenant_id": server.get("tenant_id"),
            "tool_server_id": server_id,
            "version": number,
            "endpoint_url": endpoint,
            "config": config,
            "auth_mode": auth_mode,
            "secret_ref_id": body.get("secret_id"),
            "credential_provider_id": body.get("credential_provider_id"),
            "manifest": {},
            "manifest_hash": "",
            "upstream_hash": "",
            "review_status": "pending",
            "review_notes": "",
            "reviewed_by": None,
            "reviewed_at": None,
            "discovered_at": None,
            "created_by": actor.user_id,
            "created_at": now,
            "discovery_error": None,
        }
        self._audit(actor, "tool_server.version_created", version_id, {"version": number})
        try:
            tools = self._catalogue(server, self.store.tool_server_versions[version_id])
            self._replace_tools(server, self.store.tool_server_versions[version_id], tools, actor)
        except (ValidationFailedError, OpenApiError) as exc:
            self.store.tool_server_versions[version_id]["discovery_error"] = str(exc)
        return version_view(self.store, self.store.tool_server_versions[version_id], tools=True)

    def _endpoint(
        self, server: dict[str, object], body: dict[str, object]
    ) -> tuple[str, str, dict[str, object]]:
        kind = str(server.get("kind"))
        config = body.get("config") if isinstance(body.get("config"), dict) else {}
        config = cast("dict[str, object]", config)
        if kind == "remote_mcp":
            url = str(body.get("endpoint_url") or config.get("url") or "")
            if not (url.startswith("https://") or url.startswith("memory://")):
                raise ValidationFailedError("a remote MCP server needs an https or memory URL")
            return url, str(body.get("auth_mode") or "none"), config
        if kind == "openapi":
            return "memory://petstore", "internal_jwt", config
        if kind == "sql":
            return "memory://warehouse", "internal_jwt", config
        raise ValidationFailedError("kind must be remote_mcp, openapi or sql")

    def _catalogue(  # noqa: PLR0911
        self, server: dict[str, object], version: dict[str, object]
    ) -> list[dict[str, object]]:
        kind = str(server.get("kind"))
        endpoint = str(version.get("endpoint_url") or "")
        config = version.get("config") if isinstance(version.get("config"), dict) else {}
        if kind == "remote_mcp" and endpoint == "memory://echo":
            return [dict(item) for item in _ECHO]
        if kind == "remote_mcp" and endpoint == "memory://tickets":
            return []
        if kind == "remote_mcp" and endpoint.startswith(("https://", "http://")):
            try:
                return list_remote(self.store, endpoint)
            except RemoteError as exc:
                version["discovery_error"] = exc.reason
                return []
        if kind == "openapi":
            return self._openapi_tools(as_mapping(config))
        if kind == "sql":
            str(server.get("slug"))
            return [
                {
                    "name": "list_tables",
                    "title": "List tables",
                    "description": "List allowlisted tables.",
                    "input_schema": {"type": "object", "properties": {}},
                    "risk_class": "R0",
                    "annotations": {},
                },
                {
                    "name": "describe_table",
                    "title": "Describe a table",
                    "description": "Describe one table.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"table": {"type": "string"}},
                        "required": ["table"],
                    },
                    "risk_class": "R0",
                    "annotations": {},
                },
                {
                    "name": "run_query",
                    "title": "Run a query",
                    "description": "Run one read-only select.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                        "required": ["sql"],
                    },
                    "risk_class": "R1",
                    "annotations": {},
                },
            ]
        if endpoint.startswith("memory://") or endpoint.startswith("builtin://"):
            return []
        version["discovery_error"] = "discovery waits for the server"
        return []

    def _openapi_tools(self, config: dict[str, object]) -> list[dict[str, object]]:
        spec = config.get("spec")
        nested = config.get("openapi")
        if spec is None and isinstance(nested, dict):
            spec = nested.get("spec") or nested.get("document")
        if spec is None:
            raise ValidationFailedError("an OpenAPI document is required")
        selected = None
        if isinstance(nested, dict) and isinstance(nested.get("operations"), list):
            selected = [str(item) for item in nested["operations"]]
        try:
            return operations_from(
                load_document(spec if isinstance(spec, dict | str | bytes) else {}), selected
            )
        except OpenApiError as exc:
            raise ValidationFailedError(exc.reason) from exc

    def _replace_tools(
        self,
        server: dict[str, object],
        version: dict[str, object],
        tools: list[dict[str, object]],
        actor: Actor,
    ) -> None:
        version_id = version["id"]
        stale = [
            key
            for key, row in self.store.tool_versions.items()
            if row.get("tool_server_version_id") == version_id
        ]
        for key in stale:
            self.store.tool_versions.pop(key, None)
        slug = str(server.get("slug"))
        now = utcnow()
        names = []
        for item in tools:
            name = str(item["name"])
            if not name_ok(name):
                continue
            names.append(name)
            tool = self._ensure_tool(server, name, now)
            text = str(item.get("description") or name)
            risk = str(item.get("risk_class") or "R1")
            tool_version_id = new_id()
            self.store.tool_versions[tool_version_id] = {
                "id": tool_version_id,
                "tenant_id": server.get("tenant_id"),
                "tool_id": tool["id"],
                "tool_server_version_id": version_id,
                "name": name,
                "qualified_name": f"{slug}.{name}",
                "title": item.get("title") or name,
                "description": text,
                "description_hash": description_hash(text),
                "input_schema": item.get("input_schema") or {"type": "object"},
                "output_schema": None,
                "annotations": item.get("annotations") or {},
                "risk_class": risk,
                "proposed_risk_class": risk,
                "risk_confirmed": False,
                "data_classification": "internal",
                "timeout_s": 60,
                "rate_limit_per_minute": 60,
                "max_result_bytes": 65536,
                "idempotent": risk in {"R0", "R1"},
                "approval_preview": {},
                "embedding": hash_embedding(text),
                "changed_since_previous": False,
                "created_at": now,
            }
        manifest = {"tools": names}
        digest = manifest_hash(manifest)
        version["manifest"] = manifest
        version["manifest_hash"] = digest
        version["upstream_hash"] = digest
        version["discovered_at"] = now
        version["discovery_error"] = None
        del actor

    def _ensure_tool(self, server: dict[str, object], name: str, now: object) -> dict[str, object]:
        for row in self.store.tool_defs.values():
            if row.get("tool_server_id") == server["id"] and row.get("name") == name:
                return cast("dict[str, object]", row)
        tool_id = new_id()
        row = {
            "id": tool_id,
            "tenant_id": server.get("tenant_id"),
            "tool_server_id": server["id"],
            "name": name,
            "qualified_name": f"{server.get('slug')}.{name}",
            "disabled_at": None,
            "disabled_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        self.store.tool_defs[tool_id] = row
        return row

    def _apply_tool_patch(self, row: dict[str, object], body: dict[str, object]) -> None:
        for key in (
            "risk_class",
            "data_classification",
            "timeout_s",
            "rate_limit_per_minute",
            "max_result_bytes",
            "idempotent",
            "approval_preview",
        ):
            if key in body and body[key] is not None:
                row[key] = body[key]
                if key == "risk_class":
                    row["risk_confirmed"] = True
        override = body.get("description_override")
        if isinstance(override, str) and override.strip():
            notes = row.get("annotations")
            bag = dict(notes) if isinstance(notes, dict) else {}
            bag.setdefault("_upstream_description_hash", row.get("description_hash"))
            row["annotations"] = bag
            row["description"] = override
            row["description_hash"] = description_hash(override)
            row["embedding"] = hash_embedding(override)

    def _four_eyes(self, actor: Actor, version: dict[str, object]) -> None:
        if version.get("created_by") != actor.user_id:
            return
        settings = self.store.tenant_settings.get(actor.tenant_id, {})
        security = settings.get("security") if isinstance(settings, dict) else {}
        allowed = isinstance(security, dict) and security.get("allow_self_review") is True
        if not allowed:
            raise ArError(ErrorCode.FORBIDDEN, "four_eyes")

    def _server(self, actor: Actor, server_id: uuid.UUID) -> dict[str, object]:
        row = self.store.tool_servers.get(server_id)
        if not isinstance(row, dict) or not self._visible(actor, row):
            raise NotFoundError()
        return row

    def _visible(self, actor: Actor, row: dict[str, object]) -> bool:
        owner = row.get("tenant_id")
        return owner is None or owner == actor.tenant_id

    def _version(self, version_id: uuid.UUID, server_id: uuid.UUID) -> dict[str, object]:
        row = self.store.tool_server_versions.get(version_id)
        if not isinstance(row, dict) or row.get("tool_server_id") != server_id:
            raise NotFoundError()
        return row

    def _tool_version(self, tool_version_id: uuid.UUID, version_id: uuid.UUID) -> dict[str, object]:
        row = self.store.tool_versions.get(tool_version_id)
        if not isinstance(row, dict) or row.get("tool_server_version_id") != version_id:
            raise NotFoundError()
        return row

    def _tool(self, actor: Actor, tool_id: uuid.UUID) -> dict[str, object]:
        row = self.store.tool_defs.get(tool_id)
        if not isinstance(row, dict) or not self._tool_visible(actor, row):
            raise NotFoundError()
        return row

    def _tool_visible(self, actor: Actor, tool: dict[str, object]) -> bool:
        server = self.store.tool_servers.get(tool.get("tool_server_id"))
        return isinstance(server, dict) and self._visible(actor, server)

    def _current_tool_version(self, tool: dict[str, object]) -> dict[str, object] | None:
        server = self.store.tool_servers.get(tool.get("tool_server_id"))
        if not isinstance(server, dict):
            return None
        current = server.get("current_version_id")
        for row in self.store.tool_versions.values():
            if row.get("tool_id") == tool["id"] and row.get("tool_server_version_id") == current:
                return cast("dict[str, object]", row)
        return None

    def _slug_taken(self, tenant_id: uuid.UUID, slug: str) -> bool:
        for row in self.store.tool_servers.values():
            if row.get("slug") == slug and row.get("tenant_id") in {None, tenant_id}:
                return True
        return False

    def _where_used(self, slug: str) -> list[str]:
        used = []
        for agent in self.store.agents.values():
            if agent.get("status") != "published":
                continue
            version_id = agent.get("published_version_id")
            version = (
                self.store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
            )
            definition = version.get("definition") if isinstance(version, dict) else None
            tools = definition.get("tools") if isinstance(definition, dict) else None
            if isinstance(tools, list) and any(
                isinstance(item, dict) and item.get("server") == slug for item in tools
            ):
                used.append(str(agent.get("slug")))
        return used

    def _stats(self, tool_id: uuid.UUID) -> int:
        return sum(1 for row in self.store.tool_calls.values() if row.get("tool_id") == tool_id)

    def _owner_or_review(self, actor: Actor, server: dict[str, object]) -> None:
        if actor.has("tools:review") or server.get("owner_user_id") == actor.user_id:
            return
        raise ArError(ErrorCode.FORBIDDEN, "only the owner or a reviewer can change this server")

    def _need(self, actor: Actor, permission: str) -> None:
        if not actor.has(permission):
            raise ArError(ErrorCode.FORBIDDEN, f"{permission} is required")

    def _audit(
        self, actor: Actor, action: str, target_id: object, detail: dict[str, object]
    ) -> None:
        self.store.audit_log.append(
            {
                "tenant_id": str(actor.tenant_id),
                "actor_id": str(actor.user_id),
                "action": action,
                "target_type": "tool_server",
                "target_id": str(target_id),
                "detail": detail,
                "outcome": "success",
                "at": utcnow().isoformat(),
            }
        )

    def _event(self, topic: str, payload: dict[str, object]) -> None:
        self.store.domain_events.append(
            {"topic": topic, "payload": payload, "at": utcnow().isoformat()}
        )
