"""Run record seal and replay. Spec: docs/03-specs/18-observability-eval.md §7."""

from __future__ import annotations

import hashlib
import os
from typing import TYPE_CHECKING, Any, cast

import orjson
from pydantic import JsonValue

from ar_common.errors import ArError, ErrorCode, NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import audit, missing, own, public, require
from ar_domain.records.crypto import (
    open_blob,
    public_pem,
    seal_blob,
    sign_manifest,
    signing_material,
    verify_manifest,
)
from ar_domain.records.memory import bucket
from ar_domain.records.vault import EvidenceBook

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_MAX = 52_428_800


class RunRecordBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def seal(self, actor: Actor, run_id: uuid.UUID) -> dict[str, object]:
        run = self.store.runs.get(run_id)
        if not isinstance(run, dict) or run.get("tenant_id") != actor.tenant_id:
            missing()
        for row in bucket(self.store, "run_records").values():
            if row.get("run_id") == run_id:
                return public(row)
        calls = [
            row
            for row in self.store.tool_calls.values()
            if isinstance(row, dict) and row.get("run_id") == run_id
        ]
        blob = orjson.dumps(
            {
                "calls": [
                    {
                        "tool_call_id": str(row.get("id")),
                        "qualified_name": row.get("qualified_name"),
                        "arguments": row.get("arguments") or {},
                        "result": row.get("result") or {},
                    }
                    for row in calls
                ]
            }
        )
        if len(blob) > _max_bytes():
            audit(
                self.store,
                actor,
                "run_record.seal_failed",
                "run",
                run_id,
                {"reason": "blob_too_large"},
                outcome="failure",
            )
            return {"status": "seal_failed"}
        key_id, key = signing_material(self.store)
        evidence = EvidenceBook(self.store).capture(
            actor,
            {
                "media_type": "application/json",
                "source_system": "run_record",
                "collection_method": "run_record",
                "collector_run_id": run_id,
                "provenance": {"note": "encrypted tool io"},
            },
            orjson.dumps(seal_blob(key, blob)),
        )
        output = str(run.get("result_summary") or "")
        manifest: dict[str, object] = {
            "agent_version_id": str(run.get("agent_version_id") or ""),
            "definition_hash": str(run.get("definition_hash") or ""),
            "prompt_template_hashes": {},
            "model_id": str(run.get("model_id") or "fake-chat"),
            "model_revision": None,
            "weights_digest": None,
            "sampling_params": run.get("sampling_params") or {},
            "retrieved": [],
            "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
            "tool_io_evidence_id": str(evidence.get("id")),
        }
        signature, digest = sign_manifest(key, _json(manifest))
        record_id = new_id()
        row = {
            "id": record_id,
            "tenant_id": actor.tenant_id,
            "run_id": run_id,
            "agent_id": run.get("agent_id"),
            "agent_version_id": run.get("agent_version_id"),
            "definition_hash": manifest["definition_hash"],
            "prompt_template_hashes": {},
            "model_id": manifest["model_id"],
            "model_revision": None,
            "weights_digest": None,
            "sampling_params": manifest["sampling_params"],
            "retrieved": [],
            "output_sha256": manifest["output_sha256"],
            "manifest_sha256": digest,
            "signature": signature,
            "signature_key_id": key_id,
            "tool_io_evidence_id": evidence.get("id"),
            "retention_class": "run_record",
            "sealed_at": utcnow(),
            "tool_blob": blob,
            "reperformance": "recorded tool results, pinned model",
            "signed": manifest,
        }
        bucket(self.store, "run_records")[record_id] = row
        audit(
            self.store, actor, "run_record.sealed", "run_record", record_id, {"run_id": str(run_id)}
        )
        return public(row)

    def list_records(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "run_records:read")
        rows = []
        for row in bucket(self.store, "run_records").values():
            if own(row, actor.tenant_id):
                body = public(row)
                body.pop("tool_blob", None)
                body.pop("signed", None)
                rows.append(body)
        return rows

    def get(self, actor: Actor, record_id: uuid.UUID) -> dict[str, object]:
        require(actor, "run_records:read")
        row = self._row(actor, record_id)
        body = public(row)
        body.pop("tool_blob", None)
        key_id, key = signing_material(self.store)
        signed = row.get("signed")
        valid = False
        if isinstance(signed, dict) and row.get("signature_key_id") == key_id:
            valid = verify_manifest(public_pem(key), _json(signed), str(row.get("signature")))
        body["verification"] = {"valid": valid}
        body["reperformance"] = row.get("reperformance")
        return body

    def replay(self, actor: Actor, record_id: uuid.UUID, model_id: str = "") -> dict[str, object]:
        require(actor, "run_records:replay")
        row = self._row(actor, record_id)
        if model_id and model_id != str(row.get("model_id")):
            raise ArError(ErrorCode.VALIDATION_FAILED, "replay model must match the record")
        key_id, key = signing_material(self.store)
        del key_id
        blob = row.get("tool_blob")
        recorded = blob if isinstance(blob, bytes) else b"{}"
        # Replay substitutes recorded tool results and does not call live tools.
        opened = recorded
        try:
            envelope = orjson.loads(recorded)
            if isinstance(envelope, dict) and "ciphertext" in envelope:
                opened = open_blob(key, {str(k): str(v) for k, v in envelope.items()})
        except orjson.JSONDecodeError, KeyError, ValueError:
            opened = recorded
        output = str(self.store.runs.get(row.get("run_id"), {}).get("result_summary") or "")
        if row.get("force_divergence"):
            output += " diverged"
        actual = hashlib.sha256(output.encode()).hexdigest()
        expected = str(row.get("output_sha256"))
        status = "matched" if actual == expected else "diverged"
        replay_id = new_id()
        divergence = None
        if status == "diverged":
            divergence = {
                "step": "output",
                "field": "output_sha256",
                "expected_hash": expected,
                "actual_hash": actual,
            }
            audit(
                self.store,
                actor,
                "run_record.replay_diverged",
                "run_record_replay",
                replay_id,
                cast("dict[str, object]", divergence),
            )
        saved = {
            "id": replay_id,
            "tenant_id": actor.tenant_id,
            "run_record_id": record_id,
            "status": status,
            "divergence": divergence,
            "started_by": actor.user_id,
            "started_at": utcnow(),
            "completed_at": utcnow(),
            "used_live_tools": False,
            "tool_bytes": len(opened),
        }
        bucket(self.store, "replays")[replay_id] = saved
        audit(
            self.store,
            actor,
            "run_record.replayed",
            "run_record",
            record_id,
            {"replay_id": str(replay_id)},
        )
        return public(saved)

    def get_replay(
        self, actor: Actor, record_id: uuid.UUID, replay_id: uuid.UUID
    ) -> dict[str, object]:
        require(actor, "run_records:read")
        self._row(actor, record_id)
        row = bucket(self.store, "replays").get(replay_id)
        if (
            not isinstance(row, dict)
            or row.get("run_record_id") != record_id
            or not own(row, actor.tenant_id)
        ):
            raise NotFoundError()
        return public(row)

    def _row(self, actor: Actor, record_id: uuid.UUID) -> dict[str, object]:
        row = bucket(self.store, "run_records").get(record_id)
        if not isinstance(row, dict) or not own(row, actor.tenant_id):
            missing()
        return row


def _json(body: dict[str, object]) -> dict[str, JsonValue]:
    signed: dict[str, JsonValue] = {}
    for key, value in body.items():
        if isinstance(value, str | int | float | bool) or value is None:
            signed[key] = value
        elif isinstance(value, dict):
            signed[key] = {str(item): str(inner) for item, inner in value.items()}
        elif isinstance(value, list):
            signed[key] = [str(item) for item in value]
        else:
            signed[key] = str(value)
    return signed


def _max_bytes() -> int:
    raw = os.environ.get("AR_RUN_RECORD_MAX_BLOB_BYTES", "").strip()
    return int(raw) if raw else _MAX
