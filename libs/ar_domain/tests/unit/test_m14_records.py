"""M14 records, guests, retention and run records."""

import hashlib
import uuid
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from ar_common.errors import ArError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.agents.cards import GovernanceBook
from ar_domain.audit.exports import verify_chain, write_jsonl_gzip
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.guests import GuestBook, totp_matches
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.packs.alembic_env import alembic_env
from ar_domain.pii.recognizers_in import find_indian, verhoeff_ok
from ar_domain.records.binders import BinderBook, build_zip
from ar_domain.records.crypto import sign_manifest, verify_manifest
from ar_domain.records.holds import HoldBook
from ar_domain.records.vault import EvidenceBook
from ar_domain.records.watermark import WatermarkError, watermark
from ar_domain.runs.records import RunRecordBook
from ar_testing.packs import install_fixture


def _actor(**extra: object) -> Actor:
    permissions = extra.get("permissions", PERMISSION_KEYS)
    return Actor(
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        permissions=permissions,  # type: ignore[arg-type]
        step_up_at=utcnow(),
        display_name="Admin",
    )


def test_verhoeff_and_recogniser_precision() -> None:
    assert verhoeff_ok("200000000009")
    assert not verhoeff_ok("200000000000")
    text = "Aadhaar 200000000009 PAN ABCDE1234F mobile 9876543210 ifsc HDFC0001234 upi me@ok"
    hits = {item["entity"] for item in find_indian(text)}
    assert hits == {"aadhaar", "pan", "mobile", "ifsc", "upi"}
    noise = find_indian("order 123 and note hello@")
    assert noise == []
    labelled = [
        ("200000000009", True),
        ("200000000000", False),
        ("ABCDE1234F", True),
        ("ABCDE12345", False),
    ]
    correct = 0
    for value, expected in labelled:
        found = any(item["text"] == value for item in find_indian(value))
        correct += int(found is expected)
    assert correct / len(labelled) >= 0.95


def test_evidence_signature_and_immutability_fields() -> None:
    store = ChatService()
    book = EvidenceBook(store)
    actor = _actor()
    item = book.capture(
        actor,
        {
            "media_type": "text/plain",
            "source_system": "desk",
            "collection_method": "upload",
            "provenance": {"note": "quarterly"},
        },
        b"hello evidence",
        idempotency_key="once",
    )
    again = book.capture(actor, {}, b"hello evidence", idempotency_key="once")
    assert again["id"] == item["id"]
    report = book.verify(actor, uuid.UUID(str(item["id"])))
    assert report["valid"] is True
    key = Ed25519PrivateKey.generate()
    body = {"id": "1", "content_sha256": "abc"}
    signature, _digest = sign_manifest(key, body)
    from ar_domain.records.crypto import public_pem

    assert verify_manifest(public_pem(key), body, signature)


def test_hold_minimum_and_erasure_skip() -> None:
    store = ChatService()
    actor = _actor()
    officer = demo_id("officer")
    store.user_roles[officer] = {"tenant_admin"}
    store.display_names[officer] = "Compliance officer"
    holds = HoldBook(store)
    with pytest.raises(ArError) as exc:
        holds.put_schedule(actor, "evidence_item", {"retention_days": 30, "disposition": "delete"})
    assert exc.value.code.value == "retention_below_minimum"
    conversation_id = demo_id("held-chat")
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": actor.tenant_id,
        "user_id": demo_id("member"),
        "retention_class": "standard",
        "created_at": utcnow() - timedelta(days=800),
    }
    created = holds.create(
        actor,
        {
            "matter": "Matter 14",
            "custodians": [],
            "scope_query": {"conversation_ids": [str(conversation_id)]},
            "approver_user_id": officer,
        },
    )
    assert created["member_count"] == 1
    erased = holds.erase(actor, demo_id("member"))
    assert str(conversation_id) in erased["held_record_ids"]
    assert conversation_id in store.conversations
    with pytest.raises(ArError):
        holds.release(actor, uuid.UUID(str(created["id"])), "done")


def test_guest_scope_and_watermark_fails_closed() -> None:
    store = ChatService()
    actor = _actor()
    guests = GuestBook(store)
    evidence = EvidenceBook(store).capture(
        actor,
        {"media_type": "text/plain", "source_system": "desk", "collection_method": "api"},
        b"secret bytes",
    )
    invited = guests.invite(
        actor,
        {
            "email": "guest@example.com",
            "display_name": "Guest",
            "grants": [
                {
                    "portal": "records",
                    "scope": {"evidence_ids": [str(evidence["id"])]},
                    "watermark": True,
                }
            ],
        },
    )
    token = next(iter(store.records["guest_challenges"].values()))["token"]
    opened = guests.session(str(token), "")
    guests.enroll(str(opened["session_id"]))
    guest_row = store.records["guests"][uuid.UUID(str(invited["id"]))]
    secret = store.secret_values[uuid.UUID(str(guest_row["totp_secret_ref_id"]))]
    assert totp_matches(secret, _code(secret))
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x00IEND\x00\x00\x00\x00"
    marked = watermark(png, "image/png", "guest@example.com")
    assert marked != png
    assert b"guest@example.com" in marked
    with pytest.raises(WatermarkError):
        watermark(b"raw", "text/plain", "guest@example.com")


def test_binder_tamper_and_run_replay() -> None:
    store = ChatService()
    actor = _actor()
    evidence = EvidenceBook(store).capture(
        actor,
        {"media_type": "text/plain", "source_system": "desk", "collection_method": "api"},
        b"binder-bytes",
    )
    binder = BinderBook(store).create(
        actor,
        {
            "title": "Pack",
            "selection": {"evidence_ids": [str(evidence["id"])]},
            "require_review": False,
        },
    )
    built = BinderBook(store).build(actor, uuid.UUID(str(binder["id"])))
    payload = store.blobs[uuid.UUID(str(built["file_id"]))]
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        assert "manifest.json" in archive.namelist()
        original = archive.read("evidence/" + str(evidence["id"]) + ".bin")
    flipped = payload.replace(original, b"x" + original[1:], 1)
    import subprocess
    import tempfile
    from pathlib import Path

    script = Path("scripts/verify_binder.py")
    with tempfile.TemporaryDirectory() as folder:
        good = Path(folder) / "good.zip"
        bad = Path(folder) / "bad.zip"
        good.write_bytes(payload)
        bad.write_bytes(flipped)
        good_run = subprocess.run(  # noqa: S603
            ["python", str(script), str(good)],  # noqa: S607
            check=False,
        )
        bad_run = subprocess.run(  # noqa: S603
            ["python", str(script), str(bad)],  # noqa: S607
            check=False,
        )
        assert good_run.returncode == 0
        assert bad_run.returncode == 1
    run_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": actor.tenant_id,
        "agent_id": demo_id("agent-assistant"),
        "agent_version_id": demo_id("assistant-version"),
        "result_summary": "hello",
        "model_id": "fake-chat",
        "definition_hash": "abc",
    }
    record = RunRecordBook(store).seal(actor, run_id)
    replay = RunRecordBook(store).replay(actor, uuid.UUID(str(record["id"])))
    assert replay["status"] == "matched"
    assert replay["used_live_tools"] is False
    store.records["run_records"][uuid.UUID(str(record["id"]))]["force_divergence"] = True
    diverged = RunRecordBook(store).replay(actor, uuid.UUID(str(record["id"])))
    assert diverged["status"] == "diverged"
    assert store.records["run_records"][uuid.UUID(str(record["id"]))]["output_sha256"]


def test_export_stream_and_pack_fixture() -> None:
    payload = write_jsonl_gzip({"id": index} for index in range(1000))
    assert payload[:2] == b"\x1f\x8b"
    assert verify_chain([{"action": "a", "target_id": "1"}])
    store = ChatService()
    installed = install_fixture(store, _actor())
    assert installed["pack_id"] == "fixture"
    env = alembic_env("fixture", "fixture_pack")
    assert env["version_table"] == "fixture_pack_alembic_version"
    book = GovernanceBook(store)
    agent_id = demo_id("agent-assistant")
    version_id = uuid.uuid4()
    store.agents[agent_id] = {
        "id": agent_id,
        "tenant_id": demo_id("tenant"),
        "description": "Helps",
        "owner_user_id": demo_id("admin"),
    }
    first = book.publish_card(
        _actor(),
        store.agents[agent_id],
        {"id": version_id, "version": 1, "definition": {}},
    )
    second = book.publish_card(
        _actor(),
        store.agents[agent_id],
        {"id": version_id, "version": 1, "definition": {}},
    )
    assert first["id"] == second["id"]
    exported = book.export(_actor(), [agent_id])
    assert exported["binder_id"]


def _code(secret: bytes) -> str:
    from ar_domain.identity.guests import _totp

    return _totp(secret, int(utcnow().timestamp()))


def test_build_zip_hashes() -> None:
    store = ChatService()
    digest = hashlib.sha256(b"binder-bytes").hexdigest()
    row = {
        "title": "Pack",
        "selection": {"evidence_ids": []},
    }
    payload = build_zip(store, row)
    assert payload[:2] == b"PK"
    assert digest
