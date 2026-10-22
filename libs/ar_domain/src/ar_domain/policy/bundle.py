"""OPA bundle bytes. Spec: docs/03-specs/09-policy-approvals.md §3.2."""

import hashlib
import io
import tarfile
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from ar_common.errors import ValidationFailedError
from ar_domain.policy.service import active_rules

if TYPE_CHECKING:
    from typing import Any

_ROOT = Path(__file__).resolve().parents[5] / "policies" / "rego" / "ar"


def build_bundle(store: Any) -> tuple[bytes, str]:
    """Tar the platform Rego plus one rules document per tenant."""
    tenants: dict[str, object] = {}
    seen: set[object] = set()
    for policy in store.policies.values():
        tenant_id = policy.get("tenant_id")
        if tenant_id in seen or tenant_id is None:
            continue
        seen.add(tenant_id)
        settings = store.tenant_settings.get(tenant_id, {})
        security = settings.get("security") if isinstance(settings, dict) else {}
        flag = True
        if isinstance(security, dict):
            flag = bool(security.get("require_step_up_for_w3", True))
        tenants[str(tenant_id)] = {
            "rules": _public_rules(active_rules(store, tenant_id)),
            "settings": {"require_step_up_for_w3": flag},
        }
    data = orjson.dumps({"tenants": tenants})
    blob = io.BytesIO()
    with tarfile.open(fileobj=blob, mode="w:gz") as archive:
        _add(archive, "ar/policy.rego", _read("policy.rego"))
        _add(archive, "ar/jsonpath.rego", _read("jsonpath.rego"))
        _add(archive, "data.json", data)
        digest = hashlib.sha256(data).hexdigest()
        _add(archive, ".manifest", orjson.dumps({"revision": digest}))
    raw = blob.getvalue()
    return raw, hashlib.sha256(raw).hexdigest()


def store_bundle(store: Any) -> str:
    """Cache the bundle on the process store and return its ETag."""
    import time  # noqa: PLC0415

    from ar_domain.policy.metrics import BUNDLE_SECONDS  # noqa: PLC0415

    started = time.perf_counter()
    raw, etag = build_bundle(store)
    store.opa_bundle = raw
    store.opa_etag = etag
    BUNDLE_SECONDS.observe(time.perf_counter() - started)
    return etag


def opa_check(rego: str) -> None:
    """Reject a custom module that does not declare the tightening package shape."""
    if "deny" not in rego and "require_approval" not in rego:
        raise ValidationFailedError("custom rego can only add deny or require_approval")
    if "allow" in rego.split("package", 1)[-1] and "default allow" in rego:
        raise ValidationFailedError("custom rego cannot grant allow")


def _public_rules(rules: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "id": rule.get("id"),
            "policy_name": rule.get("policy_name"),
            "priority": rule.get("priority"),
            "effect": rule.get("effect"),
            "message": rule.get("message"),
            "match": rule.get("match"),
            "approval": rule.get("approval"),
        }
        for rule in rules
    ]


def _read(name: str) -> bytes:
    path = _ROOT / name
    if path.is_file():
        return path.read_bytes()
    return b"package ar.policy\n"


def _add(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))
