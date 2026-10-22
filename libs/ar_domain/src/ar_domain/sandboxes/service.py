"""Sandbox templates and live computers. Spec: docs/03-specs/12-sandbox-manager.md."""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Any

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.sandboxkit import digest_pinned, download_headers, png_chart
from ar_common.time import utcnow
from ar_contracts.tenants import PlanLimits
from ar_domain.audit.memory import remember
from ar_domain.sandboxes.metrics import SANDBOXES
from ar_domain.sandboxes.runtime import (
    ensure_scope,
    list_workspace,
    read_workspace,
    resume_row,
    terminate_row,
    workspace_root,
)
from ar_domain.sandboxes.runtime import suspend as suspend_row

_HIDDEN = frozenset({"token", "auth_token_hash", "browser", "manifest"})
_IMAGE = "registry.local/ar/ar-sandbox@sha256:" + ("ab" * 32)
_PLATFORMS: tuple[tuple[str, str, bool, bool, list[str]], ...] = (
    ("default", "Default", False, False, []),
    ("python-data", "Python data", False, False, []),
    ("browser", "Browser", True, False, ["example.org", "example.com"]),
    ("data-science", "Data science", False, True, ["pypi.org", "files.pythonhosted.org"]),
)


class SandboxBook:
    """Templates, caps and the public view of a computer."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def ensure_platform(self) -> None:
        """Insert the platform templates once. Tenants cannot delete them."""
        from ar_domain.chat.service import demo_id  # noqa: PLC0415

        templates = self.store.sandbox_templates
        for slug, name, browser, packages, egress in _PLATFORMS:
            template_id = demo_id(f"sandbox-template-{slug}")
            if template_id in templates:
                continue
            now = utcnow()
            templates[template_id] = {
                "id": template_id,
                "tenant_id": None,
                "slug": slug,
                "name": name,
                "image_ref": _IMAGE,
                "runtime_class": "gvisor",
                "cpu_millis": 2000,
                "memory_mb": 4096,
                "disk_gb": 10,
                "allow_browser": browser,
                "allow_packages": packages,
                "egress_allowlist": list(egress),
                "max_classification": "confidential",
                "idle_suspend_s": 900,
                "max_lifetime_s": 86400,
                "exec_timeout_s": 120,
                "retention_days": 7,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }

    def seed_chart(self, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """A finished chart thread so the computer panel is not empty."""
        from ar_domain.chat.service import demo_id  # noqa: PLC0415

        conversation_id = demo_id("showcase-revenue")
        if conversation_id in self.store.conversations:
            return
        agent = _agent(self.store, tenant_id, "revenue-analyst")
        if agent is None:
            return
        now = utcnow()
        self.store.conversations[conversation_id] = {
            "id": conversation_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "title": "Revenue by month",
            "status": "active",
            "pinned": False,
            "is_preview": False,
            "agent_version_id": agent.get("published_version_id"),
            "active_run_id": None,
            "plan": [],
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        question = "Analyse the attached CSV and chart revenue by month"
        answer = "wrote revenue-by-month.png"
        self._message(tenant_id, conversation_id, user_id, role="user", text=question, now=now)
        self._message(tenant_id, conversation_id, user_id, role="assistant", text=answer, now=now)
        png = png_chart([12000, 15000, 18000, 14000, 21000, 19000])
        file_id = demo_id("showcase-revenue-png")
        self.store.files[file_id] = {
            "id": file_id,
            "tenant_id": tenant_id,
            "owner_user_id": user_id,
            "conversation_id": conversation_id,
            "kind": "artifact",
            "name": "revenue-by-month.png",
            "mime_type": "image/png",
            "size_bytes": len(png),
            "status": "ready",
            "scan_status": "skipped",
            "preview": {},
            "created_at": now,
            "deleted_at": None,
        }
        self.store.blobs[file_id] = png
        sandbox_id = demo_id("showcase-revenue-sandbox")
        self.store.sandboxes[sandbox_id] = {
            "id": sandbox_id,
            "tenant_id": tenant_id,
            "template_id": demo_id("sandbox-template-python-data"),
            "template_slug": "python-data",
            "scope": "conversation",
            "scope_key": f"conv:{conversation_id}",
            "conversation_id": conversation_id,
            "agent_id": agent["id"],
            "user_id": user_id,
            "status": "ready",
            "driver": "docker",
            "driver_ref": f"local:{sandbox_id}",
            "created_at": now,
            "updated_at": now,
            "last_active_at": now,
        }
        root = workspace_root(sandbox_id)
        (root / "workspace" / "outputs").mkdir(parents=True, exist_ok=True)
        (root / "workspace" / "outputs" / "revenue-by-month.png").write_bytes(png)

    def list_templates(self, actor: Any) -> list[dict[str, object]]:
        self._manage(actor)
        return [self._template_out(row) for row in self._visible_templates(actor.tenant_id)]

    def create_template(self, actor: Any, body: dict[str, object]) -> dict[str, object]:
        self._manage(actor)
        slug = str(body.get("slug") or "").strip().lower()
        if not slug or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-" for char in slug):
            raise ValidationFailedError("slug is invalid")
        if any(row.get("slug") == slug for row in self._visible_templates(actor.tenant_id)):
            raise ConflictError("a template with that slug already exists")
        image = str(body.get("image_ref") or _IMAGE)
        problem = digest_pinned(image, _registries())
        if problem:
            raise ValidationFailedError(problem)
        cpu = _int(body.get("cpu_millis"), 2000)
        memory = _int(body.get("memory_mb"), 4096)
        from ar_domain.identity.plan_limits import guard  # noqa: PLC0415

        guard(self.store, actor.tenant_id, "max_sandbox_cpu_millis", cpu)
        guard(self.store, actor.tenant_id, "max_sandbox_memory_mb", memory)
        now = utcnow()
        template_id = new_id()
        row = {
            "id": template_id,
            "tenant_id": actor.tenant_id,
            "slug": slug,
            "name": str(body.get("name") or slug),
            "image_ref": image,
            "runtime_class": str(body.get("runtime_class") or "gvisor"),
            "cpu_millis": cpu,
            "memory_mb": memory,
            "disk_gb": _int(body.get("disk_gb"), 10),
            "allow_browser": body.get("allow_browser") is True,
            "allow_packages": body.get("allow_packages") is True,
            "egress_allowlist": _strings(body.get("egress_allowlist")),
            "max_classification": str(body.get("max_classification") or "confidential"),
            "idle_suspend_s": _int(body.get("idle_suspend_s"), 900),
            "max_lifetime_s": _int(body.get("max_lifetime_s"), 86400),
            "exec_timeout_s": _int(body.get("exec_timeout_s"), 120),
            "retention_days": _int(body.get("retention_days"), 7),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        self.store.sandbox_templates[template_id] = row
        _audit(self.store, actor, "sandbox_template.created", template_id, {"slug": slug})
        return self._template_out(row)

    def patch_template(
        self, actor: Any, template_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        self._manage(actor)
        row = self._owned_template(actor, template_id)
        if row.get("tenant_id") is None:
            raise ConflictError("platform templates cannot be changed")
        if "image_ref" in body:
            image = str(body.get("image_ref") or "")
            problem = digest_pinned(image, _registries())
            if problem:
                raise ValidationFailedError(problem)
            row["image_ref"] = image
        for key in ("name", "runtime_class", "max_classification", "status"):
            if key in body and body[key] is not None:
                row[key] = body[key]
        for key in (
            "cpu_millis",
            "memory_mb",
            "disk_gb",
            "idle_suspend_s",
            "max_lifetime_s",
            "exec_timeout_s",
            "retention_days",
        ):
            if key in body and body[key] is not None:
                row[key] = _int(body[key], _int(row.get(key), 0))
        if "allow_browser" in body:
            row["allow_browser"] = body.get("allow_browser") is True
        if "allow_packages" in body:
            row["allow_packages"] = body.get("allow_packages") is True
        if "egress_allowlist" in body:
            row["egress_allowlist"] = _strings(body.get("egress_allowlist"))
        limits = _limits(self.store, actor.tenant_id)
        if (
            _int(row.get("cpu_millis"), 0) > limits.max_sandbox_cpu_millis
            or _int(row.get("memory_mb"), 0) > limits.max_sandbox_memory_mb
        ):
            raise ValidationFailedError("template exceeds the plan sandbox limits")
        row["updated_at"] = utcnow()
        _audit(self.store, actor, "sandbox_template.updated", template_id, {"slug": row["slug"]})
        return self._template_out(row)

    def delete_template(self, actor: Any, template_id: uuid.UUID) -> None:
        self._manage(actor)
        row = self._owned_template(actor, template_id)
        if row.get("tenant_id") is None:
            raise ConflictError("platform templates cannot be deleted")
        live = {"terminated", "failed"}
        if any(
            item.get("template_id") == template_id and item.get("status") not in live
            for item in self.store.sandboxes.values()
        ):
            raise ConflictError("template is still referenced by a computer")
        self.store.sandbox_templates.pop(template_id, None)
        _audit(self.store, actor, "sandbox_template.deleted", template_id, {"slug": row["slug"]})

    def list_sandboxes(self, actor: Any) -> list[dict[str, object]]:
        self._manage(actor)
        rows = [
            self._sandbox_out(row)
            for row in self.store.sandboxes.values()
            if row.get("tenant_id") == actor.tenant_id
        ]
        _gauge(rows)
        return rows

    def get_sandbox(self, actor: Any, sandbox_id: uuid.UUID) -> dict[str, object]:
        return self._sandbox_out(self._visible_sandbox(actor, sandbox_id))

    def conversation_sandbox(self, actor: Any, conversation_id: uuid.UUID) -> dict[str, object]:
        self._conversation(actor, conversation_id)
        for row in self.store.sandboxes.values():
            if row.get("tenant_id") != actor.tenant_id:
                continue
            if row.get("conversation_id") == conversation_id and row.get("status") not in {
                "terminated",
                "failed",
            }:
                return self._sandbox_out(row)
        raise NotFoundError("computer not found")

    def terminate(self, actor: Any, sandbox_id: uuid.UUID) -> dict[str, object]:
        row = self._visible_sandbox(actor, sandbox_id)
        owner = row.get("user_id") == actor.user_id
        if not actor.has("sandboxes:manage") and not owner:
            raise NotFoundError("computer not found")
        if row.get("status") not in {"terminated", "failed"}:
            terminate_row(self.store, row, actor=actor.user_id)
        return self._sandbox_out(row)

    def suspend(self, actor: Any, sandbox_id: uuid.UUID) -> dict[str, object]:
        row = self._visible_sandbox(actor, sandbox_id)
        suspend_row(self.store, row)
        return self._sandbox_out(row)

    def ensure(self, actor: Any, body: dict[str, object]) -> dict[str, object]:
        template_id = body.get("template_id")
        template = self.store.sandbox_templates.get(template_id)
        if not isinstance(template, dict):
            raise NotFoundError("template not found")
        try:
            row = ensure_scope(
                self.store,
                tenant_id=actor.tenant_id,
                template_slug=str(template.get("slug")),
                scope=str(body.get("scope") or "conversation"),
                scope_key=str(body.get("scope_key") or ""),
                conversation_id=_uuid(body.get("conversation_id")),
                agent_id=_uuid(body.get("agent_id")),
                user_id=actor.user_id,
            )
        except LookupError as exc:
            raise NotFoundError("template not found") from exc
        except RuntimeError as exc:
            raise ValidationFailedError(str(exc)) from exc
        view = self._sandbox_out(row)
        view["token"] = row.get("token")
        view["endpoint_url"] = row.get("endpoint_url")
        return view

    def files(self, actor: Any, sandbox_id: uuid.UUID, path: str) -> list[dict[str, object]]:
        row = self._open(actor, sandbox_id)
        try:
            return list_workspace(row, path or "/workspace", recursive=True)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc

    def file_bytes(
        self, actor: Any, sandbox_id: uuid.UUID, path: str
    ) -> tuple[bytes, dict[str, str]]:
        row = self._open(actor, sandbox_id)
        if row.get("status") == "suspended":
            resume_row(self.store, row)
        try:
            data = read_workspace(row, path)
        except FileNotFoundError as exc:
            raise NotFoundError("file not found") from exc
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc
        name = path.rsplit("/", 1)[-1] or "download"
        mime = "text/html" if name.endswith((".html", ".htm")) else "application/octet-stream"
        if name.endswith(".svg"):
            mime = "image/svg+xml"
        elif name.endswith(".png"):
            mime = "image/png"
        elif name.endswith(".csv"):
            mime = "text/csv"
        return data, download_headers(name, mime, inline=False)

    def _open(self, actor: Any, sandbox_id: uuid.UUID) -> dict[str, object]:
        return self._visible_sandbox(actor, sandbox_id)

    def _message(
        self,
        tenant_id: uuid.UUID,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        role: str,
        text: str,
        now: object,
    ) -> None:
        message_id = new_id()
        self.store.messages[message_id] = {
            "id": message_id,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "parent_message_id": None,
            "role": role,
            "content": [{"type": "text", "text": text}],
            "text": text,
            "status": "completed",
            "is_active_branch": True,
            "attachments": [],
            "created_at": now,
            "author_user_id": user_id if role == "user" else None,
        }

    def _visible_templates(self, tenant_id: uuid.UUID) -> list[dict[str, object]]:
        return [
            row
            for row in self.store.sandbox_templates.values()
            if row.get("tenant_id") is None or row.get("tenant_id") == tenant_id
        ]

    def _owned_template(self, actor: Any, template_id: uuid.UUID) -> dict[str, object]:
        row = self.store.sandbox_templates.get(template_id)
        if not isinstance(row, dict):
            raise NotFoundError("template not found")
        owner = row.get("tenant_id")
        if owner is not None and owner != actor.tenant_id:
            raise NotFoundError("template not found")
        return row

    def _visible_sandbox(self, actor: Any, sandbox_id: uuid.UUID) -> dict[str, object]:
        row = self.store.sandboxes.get(sandbox_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("computer not found")
        if actor.has("sandboxes:manage") or row.get("user_id") == actor.user_id:
            return row
        conversation = self.store.conversations.get(row.get("conversation_id"))
        if isinstance(conversation, dict) and conversation.get("user_id") == actor.user_id:
            return row
        raise NotFoundError("computer not found")

    def _conversation(self, actor: Any, conversation_id: uuid.UUID) -> dict[str, object]:
        row = self.store.conversations.get(conversation_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("conversation not found")
        if row.get("user_id") != actor.user_id and not actor.has("sandboxes:manage"):
            raise NotFoundError("conversation not found")
        return row

    def _manage(self, actor: Any) -> None:
        if not actor.has("sandboxes:manage"):
            raise NotFoundError("template not found")

    def _template_out(self, row: dict[str, object]) -> dict[str, object]:
        return {key: _public(value) for key, value in row.items()}

    def _sandbox_out(self, row: dict[str, object]) -> dict[str, object]:
        return {key: _public(value) for key, value in row.items() if key not in _HIDDEN}


def _agent(store: Any, tenant_id: uuid.UUID, slug: str) -> dict[str, object] | None:
    for row in store.agents.values():
        if isinstance(row, dict) and row.get("tenant_id") == tenant_id and row.get("slug") == slug:
            return cast("dict[str, object]", row)
    return None


def _limits(store: Any, tenant_id: uuid.UUID) -> PlanLimits:
    settings = store.tenant_settings.get(tenant_id, {})
    raw = settings.get("plan_limits") if isinstance(settings, dict) else None
    if isinstance(raw, dict):
        return PlanLimits.model_validate(raw)
    return PlanLimits()


def _registries() -> tuple[str, ...]:
    raw = os.environ.get("AR_SANDBOX_ALLOWED_REGISTRIES", "registry.local/ar")
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _audit(
    store: Any, actor: Any, action: str, target: uuid.UUID, detail: dict[str, object]
) -> None:
    remember(
        store,
        tenant_id=actor.tenant_id,
        actor_id=actor.user_id,
        action=action,
        target_type="sandbox_template",
        target_id=target,
        detail=detail,
    )


def _gauge(rows: list[dict[str, object]]) -> None:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    for status, count in counts.items():
        SANDBOXES.labels(status=status).set(count)


def _public(value: object) -> object:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        rendered = isoformat()
        return rendered if isinstance(rendered, str) else str(rendered)
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _int(value: object, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return default


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None
