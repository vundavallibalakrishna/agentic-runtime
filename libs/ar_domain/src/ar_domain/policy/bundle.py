"""OPA bundle bytes. Spec: docs/03-specs/09-policy-approvals.md §3.2."""

import gzip
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

# The decision rules are one set of files, ``policies/rego/ar`` in the repository. A built
# package carries its own copy beside this module (``libs/ar_domain/pyproject.toml``), so an
# installed service finds them wherever it runs; a source checkout reads the originals.
_PACKAGED = Path(__file__).resolve().parent / "rego"
_CHECKOUT = Path(__file__).resolve().parents[5] / "policies" / "rego" / "ar"


async def bundle_from_engine(engine: Any) -> tuple[bytes, str]:
    """Build the bundle from Postgres. The engine is the platform role, all tenants.

    This does not open a chat read unit. OPA has no tenant and no person.
    """
    from sqlalchemy import text  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import AsyncSession  # noqa: PLC0415

    view = _BundleRows()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        policies = await session.execute(text("SELECT * FROM policies"))
        for row in policies.mappings():
            item = dict(row)
            view.policies[item["id"]] = item
        versions = await session.execute(text("SELECT * FROM policy_versions"))
        for row in versions.mappings():
            item = dict(row)
            view.policy_versions[item["id"]] = item
        tenants = await session.execute(text("SELECT id, settings FROM tenants"))
        for row in tenants.mappings():
            settings = row["settings"]
            if isinstance(settings, dict):
                view.tenant_settings[row["id"]] = settings
    return build_bundle(view)


class _BundleRows:
    """The three buckets ``build_bundle`` reads. Nothing else."""

    def __init__(self) -> None:
        self.policies: dict[object, dict[str, object]] = {}
        self.policy_versions: dict[object, dict[str, object]] = {}
        self.tenant_settings: dict[object, dict[str, object]] = {}


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
    # The gzip header carries the time it was written. With the clock in it, the same
    # rules built a second apart were different bytes with a different ETag, so OPA was
    # sent the whole bundle again on every poll. The time is fixed at zero.
    with (
        gzip.GzipFile(fileobj=blob, mode="wb", mtime=0) as packed,
        tarfile.open(fileobj=packed, mode="w") as archive,
    ):
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
    """One rule file. A process that cannot find it must not hand OPA an empty policy."""
    for root in (_PACKAGED, _CHECKOUT):
        path = root / name
        if path.is_file():
            return path.read_bytes()
    raise FileNotFoundError(
        f"The policy rule file {name} is missing from this install, so no policy bundle "
        "can be built. The service image must be built with policies/rego/ar present."
    )


def _add(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))
