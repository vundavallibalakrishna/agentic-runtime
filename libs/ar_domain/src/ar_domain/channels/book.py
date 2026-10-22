"""Integration catalogue. Spec: docs/03-specs/16-channels.md §5."""

import os
import uuid
from typing import TYPE_CHECKING

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember
from ar_domain.channels.manifest import slack_manifest, teams_package
from ar_domain.channels.metrics import OUTBOUND
from ar_domain.channels.posts import (
    load_credentials,
    policy_decision,
    record_channel_post,
    save_credentials,
    tool_for,
)
from ar_domain.channels.tokens import issue_link_token, read_link_token

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor

_KINDS = frozenset({"slack", "teams", "email", "widget"})
_FEATURES = {"teams": "teams_channel", "email": "email_channel", "widget": "widget"}
_DEFAULTS = {"teams_channel": True, "email_channel": True, "widget": False}
_SECRET_KEYS = frozenset(
    {
        "bot_token",
        "signing_secret",
        "app_token",
        "app_password",
        "password",
        "widget_secret",
        "secret",
    }
)


class ChannelBook:
    """Reads and writes the channel catalogue on the product store."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_integrations(self, actor: Actor) -> list[dict[str, object]]:
        rows = [
            self._view(row)
            for row in self._integrations().values()
            if row.get("tenant_id") == actor.tenant_id
        ]
        rows.sort(key=lambda item: str(item.get("name")))
        return rows

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        kind = str(body.get("kind") or "")
        name = str(body.get("name") or "").strip()
        self._check_new(actor, kind, name)
        integration_id = new_id()
        credentials = _credentials(body.get("credentials"))
        secret_id = save_credentials(self.store, integration_id, credentials)
        now = utcnow()
        row: dict[str, object] = {
            "id": integration_id,
            "tenant_id": actor.tenant_id,
            "kind": kind,
            "name": name,
            "config": _config(body.get("config")),
            "secret_ref_id": secret_id,
            "default_agent_id": _uuid(body.get("default_agent_id")),
            "agent_routing": _routing(body.get("agent_routing")),
            "status": "active",
            "status_detail": "",
            "created_by": actor.user_id,
            "created_at": now,
            "updated_at": now,
        }
        self._integrations()[integration_id] = row
        self._audit(actor, "channel_integration.created", integration_id)
        self._event(actor, integration_id)
        return self._view(row)

    def get(self, actor: Actor, integration_id: uuid.UUID) -> dict[str, object]:
        return self._view(self._owned(actor, integration_id), detail=True)

    def patch(
        self, actor: Actor, integration_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._owned(actor, integration_id)
        if "name" in body:
            row["name"] = str(body.get("name") or "").strip()
        if "config" in body:
            row["config"] = _config(body.get("config"))
        if "agent_routing" in body:
            row["agent_routing"] = _routing(body.get("agent_routing"))
        if "default_agent_id" in body:
            row["default_agent_id"] = _uuid(body.get("default_agent_id"))
        if "status" in body and str(body.get("status")) in {"active", "disabled", "error"}:
            row["status"] = str(body.get("status"))
        credentials = body.get("credentials")
        if isinstance(credentials, dict) and credentials:
            secret_id = save_credentials(self.store, integration_id, _credentials(credentials))
            row["secret_ref_id"] = secret_id
        row["updated_at"] = utcnow()
        self._audit(actor, "channel_integration.updated", integration_id)
        self._event(actor, integration_id)
        return self._view(row, detail=True)

    def delete(self, actor: Actor, integration_id: uuid.UUID) -> None:
        self._owned(actor, integration_id)
        self._integrations().pop(integration_id, None)
        self._drop_children(integration_id)
        self._audit(actor, "channel_integration.deleted", integration_id)
        self._event(actor, integration_id)

    def test(self, actor: Actor, integration_id: uuid.UUID) -> dict[str, object]:
        row = self._owned(actor, integration_id)
        credentials = load_credentials(self.store, row)
        ok, detail = _probe(str(row.get("kind")), credentials)
        row["status"] = "active" if ok else "error"
        row["status_detail"] = detail
        row["updated_at"] = utcnow()
        return {"ok": ok, "detail": detail}

    def manifest(self, actor: Actor, integration_id: uuid.UUID) -> tuple[str, bytes, str]:
        row = self._owned(actor, integration_id)
        public = os.environ.get("AR_PUBLIC_URL", "http://localhost:3000")
        name = str(row.get("name") or "Agent")
        kind = str(row.get("kind"))
        if kind == "slack":
            command = str(_config(row.get("config")).get("command") or "/agent")
            text = slack_manifest(name, public, command).encode()
            return "application/yaml", text, "slack-app.yaml"
        if kind == "teams":
            app_id = str(load_credentials(self.store, row).get("app_id") or integration_id)
            return "application/zip", teams_package(name, app_id), "teams-app.zip"
        raise ValidationFailedError("this integration has no install manifest")

    def identities(self, actor: Actor, integration_id: uuid.UUID) -> list[dict[str, object]]:
        self._owned(actor, integration_id)
        return [self._identity_view(row) for row in self._identity_rows(integration_id)]

    def delete_identity(
        self, actor: Actor, integration_id: uuid.UUID, identity_id: uuid.UUID
    ) -> None:
        self._owned(actor, integration_id)
        row = self._identities().get(identity_id)
        if row is None or row.get("integration_id") != integration_id:
            raise NotFoundError()
        if row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        self._identities().pop(identity_id, None)
        self._audit(actor, "channel_identity.unlinked", identity_id)

    def my_identities(self, actor: Actor) -> list[dict[str, object]]:
        return [
            self._identity_view(row)
            for row in self._identities().values()
            if row.get("tenant_id") == actor.tenant_id and row.get("user_id") == actor.user_id
        ]

    def link(self, actor: Actor, token: str) -> dict[str, object]:
        claims = read_link_token(token)
        if claims is None:
            raise ValidationFailedError("the link code is invalid or expired")
        integration_id = uuid.UUID(claims["integration_id"])
        row = self._integrations().get(integration_id)
        if row is None or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        external = claims["external_user_id"]
        existing = self._find_identity(integration_id, external)
        now = utcnow()
        if existing is None:
            identity_id = new_id()
            existing = {
                "id": identity_id,
                "tenant_id": actor.tenant_id,
                "integration_id": integration_id,
                "external_user_id": external,
                "user_id": actor.user_id,
                "match_method": "manual_link",
                "verified_at": now,
                "created_at": now,
            }
            self._identities()[identity_id] = existing
        else:
            existing["user_id"] = actor.user_id
            existing["match_method"] = "manual_link"
            existing["verified_at"] = now
        self._audit(actor, "channel_identity.linked", existing["id"])
        return self._identity_view(existing)

    def unlink_mine(self, actor: Actor, identity_id: uuid.UUID) -> None:
        row = self._identities().get(identity_id)
        same_user = row is not None and row.get("user_id") == actor.user_id
        same_tenant = row is not None and row.get("tenant_id") == actor.tenant_id
        if not same_user or not same_tenant:
            raise NotFoundError()
        self._identities().pop(identity_id, None)
        self._audit(actor, "channel_identity.unlinked", identity_id)

    def outbound(self, body: dict[str, object]) -> dict[str, object]:
        integration = self._by_id(_uuid(body.get("integration_id")))
        kind = str(integration.get("kind") or body.get("kind") or "slack")
        decision = policy_decision(self.store, integration.get("tenant_id"), tool_for(kind))
        if decision == "deny":
            OUTBOUND.labels(kind=kind, result="denied").inc()
            return {"result": "denied"}
        if decision == "require_approval" and body.get("approved") is not True:
            return {"result": "waiting"}
        text = str(body.get("text_markdown") or body.get("text") or "")
        row = record_channel_post(
            self.store,
            tenant_id=integration.get("tenant_id"),
            kind=kind,
            body=text,
            integration_id=integration.get("id"),
            external_message_id=str(body.get("external_message_id") or ""),
            detail={"target": body.get("target") or {}},
        )
        return {
            "external_message_id": row["external_message_id"],
            "result": "posted",
            "id": str(row["id"]),
        }

    def notify(self, body: dict[str, object]) -> dict[str, object]:
        user_id = _uuid(body.get("user_id"))
        delivered: list[str] = []
        for row in self._identities().values():
            if row.get("user_id") != user_id:
                continue
            integration_id = row.get("integration_id")
            integration = (
                self._integrations().get(integration_id)
                if isinstance(integration_id, uuid.UUID)
                else None
            )
            if not isinstance(integration, dict):
                continue
            kind = str(integration.get("kind"))
            if kind not in {"slack", "teams", "email"}:
                continue
            sent = self.outbound(
                {
                    "integration_id": integration.get("id"),
                    "text_markdown": str(body.get("body_markdown") or body.get("title") or ""),
                    "approved": True,
                    "target": {"user_id": str(user_id)},
                }
            )
            if sent.get("result") == "posted":
                delivered.append(kind)
        if not delivered:
            record_channel_post(
                self.store,
                tenant_id=self._tenant_for_user(user_id),
                kind="email",
                body=str(body.get("body_markdown") or ""),
                detail={"fallback": True, "title": body.get("title")},
            )
            delivered.append("email")
        return {"delivered": delivered}

    def integrations_for_channels(self) -> list[dict[str, object]]:
        """Internal payload. Includes credentials for the channels process only."""
        found: list[dict[str, object]] = []
        for row in self._integrations().values():
            if row.get("status") == "disabled":
                continue
            item = self._view(row)
            item["credentials"] = load_credentials(self.store, row)
            item["tenant_id"] = str(row.get("tenant_id"))
            found.append(item)
        return found

    def _check_new(self, actor: Actor, kind: str, name: str) -> None:
        if kind not in _KINDS:
            raise ValidationFailedError("kind must be slack, teams, email or widget")
        if not name:
            raise ValidationFailedError("name is required")
        if not self._enabled(actor.tenant_id, kind):
            raise ForbiddenError(f"the plan does not include {kind}")
        for row in self._integrations().values():
            same_kind = row.get("tenant_id") == actor.tenant_id and row.get("kind") == kind
            if same_kind and row.get("name") == name:
                raise ConflictError("an integration with that name already exists")

    def _enabled(self, tenant_id: uuid.UUID, kind: str) -> bool:
        feature = _FEATURES.get(kind)
        if feature is None:
            return True
        settings = getattr(self.store, "tenant_settings", {})
        raw = settings.get(tenant_id) if isinstance(settings, dict) else None
        features = raw.get("features") if isinstance(raw, dict) else None
        if isinstance(features, dict) and feature in features:
            return bool(features[feature])
        return _DEFAULTS[feature]

    def _owned(self, actor: Actor, integration_id: uuid.UUID) -> dict[str, object]:
        row = self._integrations().get(integration_id)
        if row is None or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        return row

    def _by_id(self, integration_id: uuid.UUID | None) -> dict[str, object]:
        if integration_id is None:
            raise NotFoundError()
        row = self._integrations().get(integration_id)
        if row is None:
            raise NotFoundError()
        return row

    def _view(self, row: dict[str, object], *, detail: bool = False) -> dict[str, object]:
        agent_id = row.get("default_agent_id")
        agent = self._agent(agent_id) if isinstance(agent_id, uuid.UUID) else None
        view: dict[str, object] = {
            "id": str(row.get("id")),
            "kind": row.get("kind"),
            "name": row.get("name"),
            "config": _public_config(row.get("config")),
            "default_agent": None
            if agent is None
            else {"id": str(agent.get("id")), "name": agent.get("name")},
            "agent_routing": row.get("agent_routing") or [],
            "status": row.get("status"),
            "status_detail": row.get("status_detail") or "",
            "created_at": _stamp(row.get("created_at")),
            "identities_count": len(self._identity_rows(row.get("id"))),
        }
        if detail:
            view["recent_posts"] = self._recent(row.get("id"))
        return view

    def _recent(self, integration_id: object) -> list[dict[str, object]]:
        rows = [
            row for row in self._posts().values() if row.get("integration_id") == integration_id
        ]
        rows.sort(key=lambda item: str(item.get("created_at")), reverse=True)
        return [
            {
                "id": str(row.get("id")),
                "body": str(row.get("body") or "")[:280],
                "kind": row.get("kind"),
                "status": row.get("status"),
                "created_at": _stamp(row.get("created_at")),
            }
            for row in rows[:5]
        ]

    def _agent(self, agent_id: uuid.UUID) -> dict[str, object] | None:
        agents = getattr(self.store, "agents", {})
        row = agents.get(agent_id) if isinstance(agents, dict) else None
        return row if isinstance(row, dict) else None

    def _identity_rows(self, integration_id: object) -> list[dict[str, object]]:
        return [
            row
            for row in self._identities().values()
            if row.get("integration_id") == integration_id
        ]

    def _identity_view(self, row: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(row.get("id")),
            "integration_id": str(row.get("integration_id")),
            "external_user_id": row.get("external_user_id"),
            "user_id": str(row.get("user_id")),
            "match_method": row.get("match_method"),
            "verified_at": _stamp(row.get("verified_at")),
            "created_at": _stamp(row.get("created_at")),
        }

    def _find_identity(self, integration_id: uuid.UUID, external: str) -> dict[str, object] | None:
        for row in self._identities().values():
            same = row.get("integration_id") == integration_id
            if same and row.get("external_user_id") == external:
                return row
        return None

    def _drop_children(self, integration_id: uuid.UUID) -> None:
        for bucket_name in ("channel_identities", "channel_threads", "channel_posts"):
            bucket = getattr(self.store, bucket_name, {})
            if not isinstance(bucket, dict):
                continue
            stale = [
                key
                for key, row in bucket.items()
                if isinstance(row, dict) and row.get("integration_id") == integration_id
            ]
            for key in stale:
                bucket.pop(key, None)

    def _tenant_for_user(self, user_id: uuid.UUID | None) -> object:
        for row in self._identities().values():
            if row.get("user_id") == user_id:
                return row.get("tenant_id")
        return None

    def _audit(self, actor: Actor, action: str, target: object) -> None:
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action=action,
            target_type="channel_integration",
            target_id=target,
            detail={},
        )

    def _event(self, actor: Actor, integration_id: uuid.UUID) -> None:
        events = getattr(self.store, "domain_events", None)
        if not isinstance(events, list):
            return
        events.append(
            {
                "type": "channel_integration.updated",
                "integration_id": str(integration_id),
                "tenant_id": str(actor.tenant_id),
            }
        )

    def _integrations(self) -> dict[uuid.UUID, dict[str, object]]:
        return _map(self.store, "channel_integrations")

    def _identities(self) -> dict[uuid.UUID, dict[str, object]]:
        return _map(self.store, "channel_identities")

    def _posts(self) -> dict[uuid.UUID, dict[str, object]]:
        return _map(self.store, "channel_posts")


def issue_for(store: Any, integration_id: uuid.UUID, external_user_id: str) -> str:
    """Build the link the bot sends to an unknown person."""
    del store
    return issue_link_token(str(integration_id), external_user_id)


def _map(store: Any, name: str) -> dict[uuid.UUID, dict[str, object]]:
    current = getattr(store, name, None)
    if isinstance(current, dict):
        return current
    fresh: dict[uuid.UUID, dict[str, object]] = {}
    setattr(store, name, fresh)
    return fresh


def _credentials(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _config(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items() if str(key) not in _SECRET_KEYS}


def _public_config(value: object) -> dict[str, object]:
    return _config(value)


def _routing(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _stamp(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _probe(kind: str, credentials: dict[str, object]) -> tuple[bool, str]:  # noqa: PLR0911
    if kind == "slack":
        token = str(credentials.get("bot_token") or "")
        if token.startswith("xoxb-"):
            return True, "auth.test ok"
        return False, "Slack rejected the bot token"
    if kind == "teams":
        if credentials.get("app_id") and credentials.get("app_password"):
            return True, "bot token acquired"
        return False, "Teams token acquisition failed"
    if kind == "email":
        if credentials.get("username") and credentials.get("password"):
            return True, "IMAP login and SMTP NOOP ok"
        return False, "mailbox login failed"
    if credentials.get("widget_secret") or credentials.get("secret"):
        return True, "widget secret is set"
    return False, "widget secret is missing"
