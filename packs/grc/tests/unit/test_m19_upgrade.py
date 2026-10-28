"""Signed pack upgrade keeps a control and rejects a bad signature."""

from __future__ import annotations

import base64
import copy
from pathlib import Path

import pytest
import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from ar_common.errors import ArError, ErrorCode
from ar_common.ids import new_id
from ar_domain.agents.access import Actor
from ar_domain.agents.packs import PackService, manifest_digest
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.packs.registry import register_migrator
from ar_domain.records.memory import bucket
from ar_pack_grc.install import _migrate

ROOT = Path(__file__).resolve().parents[2]


def _signed(manifest: dict[str, object]) -> tuple[str, str]:
    key = Ed25519PrivateKey.generate()
    pem = key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    _hex, raw = manifest_digest(manifest)
    signature = base64.b64encode(key.sign(raw)).decode()
    return pem, signature


def test_signed_upgrade_keeps_the_control_and_rejects_a_bad_signature() -> None:
    from ar_api.main import create_application

    app = create_application()
    store = app.state.chat
    actor = Actor(
        demo_id("tenant"),
        demo_id("admin"),
        PERMISSION_KEYS,
        roles=frozenset({"tenant_admin"}),
    )
    register_migrator("grc", _migrate)
    current = yaml.safe_load((ROOT / "manifest.yaml").read_text(encoding="utf-8"))
    assert isinstance(current, dict)
    first = copy.deepcopy(current)
    first["metadata"]["version"] = "1.0.0"
    store.pack_signature_required = True
    pem, signature = _signed(first)
    store.pack_trusted_keys = {"grc": pem}
    PackService(store).install(actor, first, signature=signature, key_id="grc")
    control_id = new_id()
    bucket(store, "grc_controls")[control_id] = {
        "id": control_id,
        "tenant_id": actor.tenant_id,
        "key": "kept",
        "title": "Kept",
    }
    with pytest.raises(ArError) as rejected:
        PackService(store).upgrade(
            actor,
            "grc",
            current,
            signature="not-a-signature",
            key_id="grc",
            accept_conflicts=False,
        )
    assert rejected.value.code is ErrorCode.PACK_SIGNATURE_INVALID
    pem, signature = _signed(current)
    store.pack_trusted_keys = {"grc": pem}
    upgraded = PackService(store).upgrade(
        actor,
        "grc",
        current,
        signature=signature,
        key_id="grc",
        accept_conflicts=False,
    )
    assert upgraded["version"] == "1.1.0"
    assert bucket(store, "grc_controls")[control_id]["key"] == "kept"
    PackService(store).uninstall(actor, "grc", drop_schema=False)
    assert bucket(store, "grc_controls")[control_id]["key"] == "kept"
    flag = bucket(store, "pack_flags").get((str(actor.tenant_id), "grc"))
    assert isinstance(flag, dict)
    assert flag.get("schema_dropped") is not True
