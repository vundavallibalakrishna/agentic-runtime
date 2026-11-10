"""Install a catalogue connector onto a connection the person owns."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.connectors.catalog import CONNECTORS, ConnectorDef, connector_by_slug
from ar_domain.connectors.dispatch import probe_install
from ar_domain.connectors.live_pack import shown_verification
from ar_domain.proof import connector_proof

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor


class ConnectorBook:
    """Catalogue plus the caller's installs. Secrets stay on the connection."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_items(
        self, actor: Actor, *, q: str = "", category: str = ""
    ) -> list[dict[str, object]]:
        needle = q.strip().lower()
        rows = []
        for connector in CONNECTORS:
            if category and connector.category != category:
                continue
            if (
                needle
                and needle
                not in f"{connector.name} {connector.summary} {connector.category}".lower()
            ):
                continue
            rows.append(self._card(actor, connector))
        return rows

    def get(self, actor: Actor, slug: str) -> dict[str, object]:
        connector = connector_by_slug(slug)
        if connector is None:
            raise NotFoundError()
        return self._detail(actor, connector)

    def get_install(self, actor: Actor, install_id: uuid.UUID) -> dict[str, object]:
        row = self._own(actor, install_id)
        connector = connector_by_slug(str(row.get("slug") or ""))
        if connector is None:
            raise NotFoundError()
        detail = self._detail(actor, connector)
        detail["install"] = _install_view(row)
        return detail

    def install(self, actor: Actor, slug: str, body: dict[str, object]) -> dict[str, object]:
        connector = connector_by_slug(slug)
        if connector is None:
            raise NotFoundError()
        if self._find(actor, slug) is not None:
            raise ConflictError("that connector is already installed")
        connection_name = str(body.get("connection_name") or body.get("name") or slug).strip()
        secret = str(body.get("secret") or "")
        if secret or body.get("client_id"):
            self._connection(actor, connector, connection_name, body, secret)
        elif not connector.allows_anonymous:
            raise ValidationFailedError("a connection secret is required")
        raw_config = body.get("config")
        config = raw_config if isinstance(raw_config, dict) else {}
        now = utcnow()
        row = {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "owner_user_id": actor.user_id,
            "slug": slug,
            "connection_name": connection_name
            if secret or body.get("client_id") or _named(self.store, actor, connection_name)
            else "",
            "connection_id": _connection_id(self.store, actor, connection_name),
            "status": "installed",
            "disabled_tools": [],
            "config": {str(key): value for key, value in config.items()},
            "last_tested_at": None,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }
        _book(self.store)[row["id"]] = row
        _audit(self.store, actor, "connector.installed", row["id"], {"slug": slug})
        return self._detail(actor, connector)

    def update(
        self, actor: Actor, install_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._own(actor, install_id)
        connector = connector_by_slug(str(row.get("slug") or ""))
        if connector is None:
            raise NotFoundError()
        known = {tool.name for tool in connector.tools}
        disabled = body.get("disabled_tools")
        if isinstance(disabled, list):
            row["disabled_tools"] = [str(item) for item in disabled if str(item) in known]
        incoming = body.get("config")
        if isinstance(incoming, dict):
            current = row.get("config")
            merged = dict(current) if isinstance(current, dict) else {}
            merged.update(incoming)
            row["config"] = merged
        if body.get("connection_name"):
            name = str(body["connection_name"])
            row["connection_name"] = name
            row["connection_id"] = _connection_id(self.store, actor, name)
        if body.get("status") in {"installed", "disabled"}:
            row["status"] = str(body["status"])
        row["updated_at"] = utcnow()
        _audit(self.store, actor, "connector.updated", install_id, {"slug": row.get("slug")})
        return self._detail(actor, connector)

    def remove(self, actor: Actor, install_id: uuid.UUID) -> None:
        row = self._own(actor, install_id)
        _book(self.store).pop(install_id, None)
        _audit(self.store, actor, "connector.removed", install_id, {"slug": row.get("slug")})

    def test(self, actor: Actor, install_id: uuid.UUID) -> dict[str, object]:
        row = self._own(actor, install_id)
        result = probe_install(self.store, row, actor.tenant_id, actor.user_id)
        row["last_tested_at"] = utcnow()
        row["last_error"] = None if result.get("ok") else str(result.get("error") or "")
        row["updated_at"] = utcnow()
        _audit(
            self.store,
            actor,
            "connector.tested",
            install_id,
            {"ok": bool(result.get("ok")), "slug": row.get("slug")},
        )
        return result

    def _card(self, actor: Actor, connector: ConnectorDef) -> dict[str, object]:
        install = self._find(actor, connector.slug)
        return {
            "slug": connector.slug,
            "name": connector.name,
            "category": connector.category,
            "summary": connector.summary,
            "implementation": connector.implementation,
            "verification": shown_verification(connector),
            "proof": connector_proof(connector),
            "verification_note": connector.verification_note,
            "docs": connector.docs,
            "installed": install is not None,
            "install_id": None if install is None else str(install["id"]),
            "status": None if install is None else install.get("status"),
            "last_error": None if install is None else install.get("last_error"),
        }

    def _detail(self, actor: Actor, connector: ConnectorDef) -> dict[str, object]:
        install = self._find(actor, connector.slug)
        disabled: set[str] = set()
        if install is not None:
            current_disabled = install.get("disabled_tools")
            if isinstance(current_disabled, list):
                disabled = {str(item) for item in current_disabled}
        card = self._card(actor, connector)
        card.update(
            {
                "auth_kind": connector.auth_kind,
                "auth_kinds": list(connector.auth_kinds),
                "scopes": list(connector.scopes),
                "registration_url": connector.registration_url,
                "authorize_url": connector.authorize_url,
                "token_url": connector.token_url,
                "steps": list(connector.steps),
                "rate_per_minute": connector.rate_per_minute,
                "fields": [
                    {"name": field.name, "label": field.label, "placeholder": field.placeholder}
                    for field in connector.fields
                ],
                "tools": [
                    {
                        "name": tool.name,
                        "title": tool.title,
                        "description": tool.description,
                        "risk": tool.risk,
                        "proof": connector_proof(connector),
                        "enabled": install is not None
                        and tool.name not in disabled
                        and install.get("status") == "installed"
                        and connector_proof(connector) == "live",
                    }
                    for tool in connector.tools
                ],
                "install": None if install is None else _install_view(install),
            }
        )
        return card

    def _find(self, actor: Actor, slug: str) -> dict[str, object] | None:
        for row in _book(self.store).values():
            if (
                row.get("tenant_id") == actor.tenant_id
                and row.get("owner_user_id") == actor.user_id
                and row.get("slug") == slug
            ):
                return row
        return None

    def _own(self, actor: Actor, install_id: uuid.UUID) -> dict[str, object]:
        row = _book(self.store).get(install_id)
        if (
            not isinstance(row, dict)
            or row.get("tenant_id") != actor.tenant_id
            or row.get("owner_user_id") != actor.user_id
        ):
            raise NotFoundError()
        return row

    def _connection(
        self,
        actor: Actor,
        connector: ConnectorDef,
        name: str,
        body: dict[str, object],
        secret: str,
    ) -> None:
        from ar_domain.tools.service_connections import ConnectionBook  # noqa: PLC0415

        kind = str(body.get("kind") or connector.auth_kind)
        if kind not in connector.auth_kinds:
            raise ValidationFailedError("that auth type is not used by this connector")
        authorize_url, token_url = _oauth_urls(connector, body, kind)
        if _named(self.store, actor, name):
            return
        ConnectionBook(self.store).create(
            actor,
            {
                "name": name,
                "kind": kind,
                "secret": secret,
                "username": str(body.get("username") or ""),
                "header_name": (
                    "X-AR-Service-Account" if connector.slug == "gcp" else "Authorization"
                ),
                "authorize_url": authorize_url,
                "token_url": token_url,
                "client_id": str(body.get("client_id") or ""),
                "scopes": list(connector.scopes),
                "probe_url": _probe_url(connector, body),
            },
        )


def _book(store: Any) -> dict[Any, dict[str, object]]:
    book = getattr(store, "connector_installs", None)
    if not isinstance(book, dict):
        store.connector_installs = {}
        book = store.connector_installs
    return book


def _named(store: Any, actor: Actor, name: str) -> bool:
    from ar_domain.tools.service_connections import _book as connections  # noqa: PLC0415

    for row in connections(store).values():
        if (
            row.get("tenant_id") == actor.tenant_id
            and row.get("owner_user_id") == actor.user_id
            and str(row.get("name")).lower() == name.lower()
        ):
            return True
    return False


def _connection_id(store: Any, actor: Actor, name: str) -> uuid.UUID | None:
    from ar_domain.tools.service_connections import _book as connections  # noqa: PLC0415

    for row in connections(store).values():
        if (
            row.get("tenant_id") == actor.tenant_id
            and row.get("owner_user_id") == actor.user_id
            and str(row.get("name")).lower() == name.lower()
        ):
            found = row.get("id")
            if isinstance(found, uuid.UUID):
                return found
    return None


def _oauth_urls(connector: ConnectorDef, body: dict[str, object], kind: str) -> tuple[str, str]:
    raw = body.get("config")
    config = raw if isinstance(raw, dict) else {}
    tenant = str(config.get("tenantId") or "").strip()
    base = str(config.get("baseUrl") or connector.base_url or "").rstrip("/")
    if kind.startswith("oauth") and "{tenant}" in connector.token_url and not tenant:
        raise ValidationFailedError("tenantId is required")
    if kind.startswith("oauth") and "{baseUrl}" in connector.token_url and not base:
        raise ValidationFailedError("baseUrl is required")
    filled = tenant or "common"
    authorize = connector.authorize_url.replace("{tenant}", filled).replace("{baseUrl}", base)
    token = connector.token_url.replace("{tenant}", filled).replace("{baseUrl}", base)
    return authorize, token


def _probe_url(connector: ConnectorDef, body: dict[str, object]) -> str:
    raw_config = body.get("config")
    config = raw_config if isinstance(raw_config, dict) else {}
    base = str(config.get("baseUrl") or connector.base_url or "").rstrip("/")
    if not base or not connector.probe_path:
        return ""
    return base + connector.probe_path


def _install_view(row: dict[str, object]) -> dict[str, object]:
    disabled = row.get("disabled_tools")
    config = row.get("config")
    return {
        "id": str(row["id"]),
        "slug": row.get("slug"),
        "connection_name": row.get("connection_name") or "",
        "connection_id": (
            None if row.get("connection_id") is None else str(row.get("connection_id"))
        ),
        "status": row.get("status"),
        "disabled_tools": list(disabled) if isinstance(disabled, list) else [],
        "config": config if isinstance(config, dict) else {},
        "last_error": row.get("last_error"),
        "last_tested_at": _iso(row.get("last_tested_at")),
    }


def _iso(value: object) -> str | None:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    return str(value)


def _audit(
    store: Any, actor: Actor, action: str, target: object, detail: dict[str, object]
) -> None:
    log = getattr(store, "audit_log", None)
    if not isinstance(log, list):
        return
    log.append(
        {
            "tenant_id": str(actor.tenant_id),
            "actor_id": str(actor.user_id),
            "action": action,
            "target_type": "connector_install",
            "target_id": str(target),
            "detail": detail,
            "outcome": "success",
            "at": utcnow().isoformat(),
        }
    )
