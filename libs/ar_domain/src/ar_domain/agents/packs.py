"""Content packs. Spec: docs/03-specs/05-agent-registry.md §10.

Declarative packs install through the bundle importer. A manifest that sets
``extension`` is refused until pack migrations exist. ``dropSchema`` is the
same refusal.
"""

import base64
import hashlib
import uuid
from typing import TYPE_CHECKING, Any, cast

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from pydantic import JsonValue, ValidationError

from ar_common.errors import ArError, ErrorCode, NotFoundError
from ar_common.ids import new_id
from ar_common.jcs import canonical_json
from ar_common.time import utcnow
from ar_contracts.definitions import ContentPack
from ar_domain.bundles.import_ import import_bundle

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


def manifest_digest(manifest: dict[str, object]) -> tuple[str, bytes]:
    """Hex and raw SHA-256 of the JCS encoding."""
    raw = hashlib.sha256(canonical_json(cast("JsonValue", manifest))).digest()
    return raw.hex(), raw


def verify_signature(public_pem: str, signature: str, digest: bytes) -> bool:
    """Ed25519 over the raw SHA-256 digest. ``signature`` is standard base64."""
    key = load_pem_public_key(public_pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        return False
    try:
        key.verify(base64.b64decode(signature), digest)
    except InvalidSignature, ValueError:
        return False
    return True


def _refusal(payload: dict[str, object]) -> str:
    """One line per resource the bundle refused. Empty when every resource was accepted."""
    lines: list[str] = []
    for item in _result_rows(payload):
        if not isinstance(item, dict) or item.get("action") != "error":
            continue
        errors = item.get("errors")
        detail = ""
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            detail = str(errors[0].get("msg") or "")
        lines.append(f"{item.get('kind')} {item.get('key')}: {detail}".strip())
    return "; ".join(lines)


def _result_rows(payload: dict[str, object]) -> list[object]:
    rows = payload.get("results")
    return list(rows) if isinstance(rows, list) else []


def _semver(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3:
        raise ArError(ErrorCode.VALIDATION_FAILED, "version must be major.minor.patch")
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError as exc:
        raise ArError(ErrorCode.VALIDATION_FAILED, "version must be major.minor.patch") from exc


def _audit(
    store: Any,
    actor: Actor,
    action: str,
    target_id: str,
    detail: dict[str, object],
    *,
    outcome: str = "success",
) -> None:
    store.audit_log.append(
        {
            "tenant_id": str(actor.tenant_id),
            "actor_id": str(actor.user_id),
            "action": action,
            "target_type": "pack",
            "target_id": target_id,
            "detail": detail,
            "outcome": outcome,
        }
    )


class PackService:
    """Install, upgrade and uninstall declarative packs."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def _check_signature(
        self, actor: Actor, manifest: dict[str, object], signature: str | None, key_id: str | None
    ) -> tuple[str, str]:
        digest_hex, digest = manifest_digest(manifest)
        if not self.store.pack_signature_required and not signature:
            return digest_hex, ""
        public = self.store.pack_trusted_keys.get(key_id or "")
        if (
            not signature
            or not key_id
            or not isinstance(public, str)
            or not verify_signature(public, signature, digest)
        ):
            _audit(
                self.store,
                actor,
                "pack.signature_rejected",
                str(manifest.get("metadata")),
                {},
                outcome="failure",
            )
            raise ArError(ErrorCode.PACK_SIGNATURE_INVALID, "pack signature is invalid")
        return digest_hex, key_id

    def _parsed(self, manifest: dict[str, object]) -> ContentPack:
        try:
            return ContentPack.model_validate(manifest)
        except ValidationError as exc:
            raise ArError(ErrorCode.VALIDATION_FAILED, "manifest is invalid") from exc

    def list_packs(self, actor: Actor) -> list[dict[str, object]]:
        rows = [
            self._out(row)
            for row in self.store.packs.values()
            if row.get("tenant_id") == actor.tenant_id and row.get("status") == "installed"
        ]
        rows.sort(key=lambda item: str(item.get("pack_id")))
        return rows

    def get(self, actor: Actor, pack_id: str) -> dict[str, object]:
        row = self._current(actor, pack_id)
        body = self._out(row)
        body["resources"] = [
            {
                "kind": item.get("kind"),
                "slug": item.get("slug"),
                "resource_id": str(item.get("resource_id")),
            }
            for item in self.store.pack_resources.values()
            if item.get("pack_row_id") == row["id"]
        ]
        return body

    def install(
        self,
        actor: Actor,
        manifest: dict[str, object],
        *,
        signature: str | None,
        key_id: str | None,
        stepped_up: bool = False,
    ) -> dict[str, object]:
        if not actor.has("packs:manage") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission packs:manage")
        parsed = self._parsed(manifest)
        digest_hex, used_key = self._check_signature(actor, manifest, signature, key_id)
        if parsed.spec.extension is not None:
            from ar_domain.packs.registry import apply_extension  # noqa: PLC0415

            apply_extension(self.store, actor, parsed)
        existing = self._by_version(actor.tenant_id, parsed.metadata.id, parsed.metadata.version)
        if existing is not None and existing.get("status") == "installed":
            _seed_settings(self.store, actor, manifest)
            _apply_policies(self.store, actor, manifest, stepped_up=stepped_up)
            body = self._out(existing)
            body["import_results"] = []
            return body
        for rule_set in parsed.spec.rule_sets:
            from ar_domain.documents.rules import import_rule_set  # noqa: PLC0415

            import_rule_set(self.store, actor, rule_set.model_dump(by_alias=False))
        bundle_resources = [
            item
            for item in parsed.spec.resources
            if not (isinstance(item, dict) and item.get("kind") == "Policy")
        ]
        bundle = {
            "apiVersion": "agentic-runtime.dev/v1",
            "kind": "Bundle",
            "spec": {"resources": bundle_resources},
        }
        preview = import_bundle(self.store, actor, bundle, dry_run=True)
        refused = _refusal(preview)
        if refused:
            raise ArError(ErrorCode.VALIDATION_FAILED, refused)
        imported = import_bundle(
            self.store,
            actor,
            bundle,
            dry_run=False,
        )
        refused = _refusal(imported)
        if refused:
            raise ArError(ErrorCode.VALIDATION_FAILED, refused)
        now = utcnow()
        row_id = new_id()
        row = {
            "id": row_id,
            "tenant_id": actor.tenant_id,
            "pack_id": parsed.metadata.id,
            "version": parsed.metadata.version,
            "status": "installed",
            "manifest": manifest,
            "manifest_hash": digest_hex,
            "signature": signature,
            "signature_key_id": used_key,
            "installed_by": actor.user_id,
            "installed_at": now,
        }
        self.store.packs[row_id] = row
        for item in _result_rows(imported):
            if not isinstance(item, dict) or item.get("action") not in {
                "create",
                "new_version",
                "unchanged",
            }:
                continue
            resource_id = item.get("id")
            if not isinstance(resource_id, str):
                continue
            link_id = new_id()
            self.store.pack_resources[link_id] = {
                "id": link_id,
                "tenant_id": actor.tenant_id,
                "pack_row_id": row_id,
                "kind": item.get("kind"),
                "slug": item.get("key"),
                "resource_id": uuid.UUID(resource_id),
                "created_at": now,
            }
        _seed_settings(self.store, actor, manifest)
        _apply_policies(self.store, actor, manifest, stepped_up=stepped_up)
        _audit(
            self.store,
            actor,
            "pack.installed",
            parsed.metadata.id,
            {"version": parsed.metadata.version},
        )
        self.store.domain_events.append(
            {
                "topic": "pack.installed",
                "payload": {"pack_id": parsed.metadata.id, "version": parsed.metadata.version},
            }
        )
        body = self._out(row)
        body["import_results"] = imported["results"]
        return body

    def upgrade(
        self,
        actor: Actor,
        pack_id: str,
        manifest: dict[str, object],
        *,
        signature: str | None,
        key_id: str | None,
        accept_conflicts: bool,
        stepped_up: bool = False,
    ) -> dict[str, object]:
        if not actor.has("packs:manage") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission packs:manage")
        current = self._current(actor, pack_id)
        parsed = self._parsed(manifest)
        if parsed.metadata.id != pack_id:
            raise ArError(ErrorCode.VALIDATION_FAILED, "manifest id does not match the pack")
        self._check_signature(actor, manifest, signature, key_id)
        if parsed.spec.extension is not None:
            from ar_domain.packs.registry import apply_extension  # noqa: PLC0415

            apply_extension(self.store, actor, parsed)
        if _semver(parsed.metadata.version) <= _semver(str(current["version"])):
            raise ArError(ErrorCode.INVALID_STATE, "upgrade version must be strictly greater")
        preview = import_bundle(
            self.store,
            actor,
            {"spec": {"resources": parsed.spec.resources}},
            dry_run=True,
        )
        conflicts = [
            item
            for item in _result_rows(preview)
            if isinstance(item, dict) and item.get("action") == "conflict"
        ]
        if conflicts and not accept_conflicts:
            return {
                "pack_id": pack_id,
                "version": parsed.metadata.version,
                "results": preview["results"],
            }
        if conflicts and accept_conflicts:
            for agent in self.store.agents.values():
                if agent.get("tenant_id") == actor.tenant_id:
                    agent["dirty"] = False
        installed = self.install(
            actor, manifest, signature=signature, key_id=key_id, stepped_up=stepped_up
        )
        _audit(self.store, actor, "pack.upgraded", pack_id, {"version": parsed.metadata.version})
        current["status"] = "uninstalled"
        return installed

    def uninstall(self, actor: Actor, pack_id: str, *, drop_schema: bool) -> dict[str, object]:
        if not actor.has("packs:manage") and not actor.has("agents:manage_all"):
            raise ArError(ErrorCode.FORBIDDEN, "missing permission packs:manage")
        if drop_schema:
            from ar_domain.packs.registry import drop_pack_schema  # noqa: PLC0415

            drop_pack_schema(self.store, actor, pack_id)
        row = self._current(actor, pack_id)
        row["status"] = "uninstalled"
        _audit(self.store, actor, "pack.uninstalled", pack_id, {"version": row.get("version")})
        return self._out(row)

    def _current(self, actor: Actor, pack_id: str) -> dict[str, object]:
        rows = [
            row
            for row in self.store.packs.values()
            if row.get("tenant_id") == actor.tenant_id
            and row.get("pack_id") == pack_id
            and row.get("status") == "installed"
        ]
        if not rows:
            raise NotFoundError()
        return cast("dict[str, object]", rows[-1])

    def _by_version(
        self, tenant_id: uuid.UUID, pack_id: str, version: str
    ) -> dict[str, object] | None:
        for row in self.store.packs.values():
            if (
                row.get("tenant_id") == tenant_id
                and row.get("pack_id") == pack_id
                and row.get("version") == version
            ):
                return cast("dict[str, object]", row)
        return None

    def _out(self, row: dict[str, object]) -> dict[str, object]:
        installed = row.get("installed_at")
        return {
            "id": str(row.get("id")),
            "pack_id": row.get("pack_id"),
            "version": row.get("version"),
            "status": row.get("status"),
            "installed_at": installed.isoformat() if hasattr(installed, "isoformat") else installed,
            "manifest_hash": row.get("manifest_hash"),
            "signature_key_id": row.get("signature_key_id"),
        }


def _seed_settings(store: Any, actor: Actor, manifest: dict[str, object]) -> None:
    """Version 1 when a resource has no settings. A changed schema merges, it does not replace."""
    from ar_domain.config_docs.book import SettingsBook  # noqa: PLC0415

    book = SettingsBook(store)
    for item in _resources(manifest):
        body = item.get("spec") if isinstance(item.get("spec"), dict) else None
        if not isinstance(body, dict):
            continue
        schema = body.get("settingsSchema") or body.get("settings_schema")
        document = body.get("settings")
        if not isinstance(schema, dict) or not isinstance(document, dict):
            continue
        resource_id = _resource_id(item)
        if not resource_id:
            continue
        kind = str(item.get("kind") or "agent").lower()
        try:
            current = book.latest(actor.tenant_id, kind, resource_id)
        except NotFoundError:
            book.save(actor.tenant_id, actor.user_id, kind, resource_id, schema, document)
            continue
        if current.get("schema") == schema:
            continue
        book.save(
            actor.tenant_id,
            actor.user_id,
            kind,
            resource_id,
            schema,
            _merge_settings(schema, document, current.get("document")),
        )


def _apply_policies(
    store: Any, actor: Actor, manifest: dict[str, object], *, stepped_up: bool = False
) -> None:
    """Install each Policy through PolicyBook. A second install updates that policy."""
    from ar_domain.policy.service import PolicyBook  # noqa: PLC0415

    group = _approval_group(store, actor, manifest)
    slugs = _agent_slugs(manifest)
    book = PolicyBook(store)
    for item in _resources(manifest):
        if item.get("kind") != "Policy":
            continue
        body = item.get("spec") if isinstance(item.get("spec"), dict) else None
        document = body.get("document") if isinstance(body, dict) else None
        if not isinstance(document, dict):
            continue
        rewritten = _scope_rules(_with_group(document, group), slugs)
        name = str(_meta(item).get("name") or "Pack policy")
        existing = book._named(actor.tenant_id, name)
        if existing is None:
            created = book.create(
                actor, {"name": name, "kind": "rules", "document": rewritten, "priority": 100}
            )
            policy_id = uuid.UUID(str(created["id"]))
            number = 1
        else:
            raw_id = existing["id"]
            policy_id = raw_id if isinstance(raw_id, uuid.UUID) else uuid.UUID(str(raw_id))
            latest = book._latest(existing)
            same = isinstance(latest, dict) and latest.get("document") == rewritten
            if same and existing.get("status") == "active":
                continue
            raw_version = latest.get("version") if isinstance(latest, dict) else None
            if same and isinstance(raw_version, int):
                number = raw_version
            else:
                added = book.add_version(actor, policy_id, {"document": rewritten})
                added_version = added.get("version")
                number = added_version if isinstance(added_version, int) else 1
        book.activate(actor, policy_id, number, stepped_up=stepped_up)


def _approval_group(store: Any, actor: Actor, manifest: dict[str, object]) -> str:
    """The approver group named in this pack's own settings. No shared default."""
    from ar_common.errors import NotFoundError  # noqa: PLC0415
    from ar_domain.config_docs.book import SettingsBook  # noqa: PLC0415

    book = SettingsBook(store)
    for item in _resources(manifest):
        if str(item.get("kind") or "").lower() != "agent":
            continue
        resource_id = _resource_id(item)
        document: object = None
        if resource_id:
            try:
                document = book.latest(actor.tenant_id, "agent", resource_id).get("document")
            except NotFoundError:
                document = None
        if not isinstance(document, dict):
            spec = item.get("spec") if isinstance(item.get("spec"), dict) else None
            document = spec.get("settings") if isinstance(spec, dict) else None
        group = document.get("approvalGroup") if isinstance(document, dict) else None
        if isinstance(group, str) and group.strip():
            return group.strip()
    return ""


def _agent_slugs(manifest: dict[str, object]) -> list[str]:
    slugs = [
        _resource_id(item)
        for item in _resources(manifest)
        if str(item.get("kind") or "") == "Agent" and _resource_id(item)
    ]
    if slugs:
        return slugs
    pack_id = str(_meta(manifest).get("id") or "pack")
    return [pack_id]


def _scope_rules(document: dict[str, object], slugs: list[str]) -> dict[str, object]:
    """Every rule applies only to this pack's agents."""
    rules = document.get("rules")
    if not isinstance(rules, list):
        return document
    scoped: list[object] = []
    for rule in rules:
        if not isinstance(rule, dict):
            scoped.append(rule)
            continue
        copy = dict(rule)
        raw_match = copy.get("match")
        match: dict[str, object] = dict(raw_match) if isinstance(raw_match, dict) else {}
        listed = match.get("agents")
        if isinstance(listed, list) and listed:
            kept = [str(item) for item in listed if str(item) in slugs]
            match["agents"] = kept or list(slugs)
        else:
            match["agents"] = list(slugs)
        copy["match"] = match
        scoped.append(copy)
    rewritten = dict(document)
    rewritten["rules"] = scoped
    return rewritten


def _resources(manifest: dict[str, object]) -> list[dict[str, object]]:
    spec = manifest.get("spec") if isinstance(manifest.get("spec"), dict) else None
    resources = spec.get("resources") if isinstance(spec, dict) else None
    if not isinstance(resources, list):
        return []
    return [item for item in resources if isinstance(item, dict)]


def _meta(item: dict[str, object]) -> dict[str, object]:
    raw = item.get("metadata")
    return raw if isinstance(raw, dict) else {}


def _resource_id(item: dict[str, object]) -> str:
    meta = _meta(item)
    return str(meta.get("slug") or meta.get("id") or "")


def _merge_settings(
    schema: dict[str, object], defaults: dict[str, object], current: object
) -> dict[str, object]:
    """Pack defaults fill gaps. A value the tenant already set stays."""
    merged = dict(defaults)
    if isinstance(current, dict):
        merged.update(current)
    properties = schema.get("properties")
    if isinstance(properties, dict):
        merged = {key: value for key, value in merged.items() if key in properties}
        for key, value in defaults.items():
            if key in properties and key not in merged:
                merged[key] = value
    return merged


def _with_group(document: dict[str, object], group: str) -> dict[str, object]:
    """Replace the placeholder group so the approver set comes from settings."""
    import orjson  # noqa: PLC0415

    text = orjson.dumps(document).decode().replace("{{approvalGroup}}", group)
    loaded = orjson.loads(text)
    return loaded if isinstance(loaded, dict) else document
