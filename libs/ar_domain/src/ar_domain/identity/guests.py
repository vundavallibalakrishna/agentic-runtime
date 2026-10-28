"""External guest principals. Spec: docs/03-specs/21-records-governance.md §4."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ar_common.errors import ArError, ErrorCode, NotFoundError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.records.access import audit, missing, own, public, require
from ar_domain.records.memory import bucket

if TYPE_CHECKING:
    from typing import Any, NoReturn

_MAX_DAYS = 90
_LINK_SECONDS = 900
_SESSION_SECONDS = 28800


class GuestBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_guests(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "guests:manage")
        rows = [
            self._out(row)
            for row in bucket(self.store, "guests").values()
            if own(row, actor.tenant_id)
        ]
        rows.sort(key=lambda item: str(item.get("email") or ""))
        return rows

    def invite(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        require(actor, "guests:invite")
        expires = utcnow() + timedelta(days=_max_days())
        requested = body.get("expires_at")
        if isinstance(requested, str) and requested:
            from datetime import datetime  # noqa: PLC0415

            parsed = datetime.fromisoformat(requested)
            if parsed > expires:
                raise ArError(ErrorCode.VALIDATION_FAILED, "guest lifetime exceeds the maximum")
            expires = parsed
        guest_id = new_id()
        now = utcnow()
        row = {
            "id": guest_id,
            "tenant_id": actor.tenant_id,
            "email": str(body.get("email") or "").lower(),
            "display_name": str(body.get("display_name") or ""),
            "kind": str(body.get("kind") or "external"),
            "status": "invited",
            "auth_method": str(body.get("auth_method") or "magic_link_totp"),
            "totp_secret_ref_id": None,
            "totp_secret": None,
            "federated_subject": None,
            "invited_by_user_id": actor.user_id,
            "expires_at": expires,
            "last_login_at": None,
            "created_at": now,
            "updated_at": now,
        }
        if row["kind"] not in {"external", "partner", "other"}:
            raise ArError(ErrorCode.VALIDATION_FAILED, "kind is invalid")
        bucket(self.store, "guests")[guest_id] = row
        grants = body.get("grants")
        if isinstance(grants, list):
            for grant in grants:
                if isinstance(grant, dict):
                    self._grant(actor, row, grant)
        self._challenge(row)
        audit(self.store, actor, "guest.invited", "guest", guest_id, {"email": row["email"]})
        return self._out(row)

    def get(self, actor: Actor, guest_id: uuid.UUID) -> dict[str, object]:
        require(actor, "guests:manage")
        return self._out(self._row(actor, guest_id))

    def revoke(self, actor: Actor, guest_id: uuid.UUID) -> dict[str, object]:
        require(actor, "guests:manage")
        row = self._row(actor, guest_id)
        row["status"] = "revoked"
        row["updated_at"] = utcnow()
        sessions = bucket(self.store, "guest_sessions")
        for key, session in list(sessions.items()):
            if session.get("guest_id") == guest_id:
                sessions.pop(key, None)
        audit(self.store, actor, "guest.revoked", "guest", guest_id, {})
        return self._out(row)

    def add_grant(
        self, actor: Actor, guest_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        require(actor, "guests:manage")
        row = self._row(actor, guest_id)
        grant = self._grant(actor, row, body)
        audit(
            self.store,
            actor,
            "guest.grant_created",
            "guest_grant",
            grant["id"],
            {"portal": grant["portal"]},
        )
        return public(grant)

    def revoke_grant(self, actor: Actor, guest_id: uuid.UUID, grant_id: uuid.UUID) -> None:
        require(actor, "guests:manage")
        self._row(actor, guest_id)
        grant = bucket(self.store, "guest_grants").get(grant_id)
        if (
            not isinstance(grant, dict)
            or grant.get("guest_id") != guest_id
            or not own(grant, actor.tenant_id)
        ):
            missing()
        bucket(self.store, "guest_grants").pop(grant_id, None)
        audit(self.store, actor, "guest.grant_revoked", "guest_grant", grant_id, {})

    def request_link(self, email: str, tenant_slug: str) -> None:
        """Always succeeds from the caller's point of view. Sends a link only for a live guest."""
        del tenant_slug
        now = utcnow()
        recent = [
            row
            for row in bucket(self.store, "guest_challenges").values()
            if str(row.get("email") or "") == email.lower()
            and isinstance(row.get("created_at"), type(now))
            and (now - row["created_at"]).total_seconds() < 3600  # type: ignore[operator]
        ]
        if len(recent) >= 5:
            return
        guest = self._by_email(email)
        if guest is None or guest.get("status") == "revoked":
            return
        expires = guest.get("expires_at")
        if isinstance(expires, type(now)) and expires < now:
            return
        self._challenge(guest)

    def session(self, token: str, totp_code: str) -> dict[str, object]:
        challenge = self._challenge_for(token)
        if not isinstance(challenge, dict) or challenge.get("consumed_at") is not None:
            self._fail(None, "unknown link")
        expires = challenge.get("expires_at")
        if isinstance(expires, type(utcnow())) and expires < utcnow():
            self._fail(challenge.get("guest_id"), "link expired")
        guest_id = challenge.get("guest_id")
        guest = bucket(self.store, "guests").get(guest_id)
        if not isinstance(guest, dict) or guest.get("status") == "revoked":
            self._fail(guest_id, "revoked")
        principal_expires = guest.get("expires_at")
        if isinstance(principal_expires, type(utcnow())) and principal_expires < utcnow():
            self._fail(guest_id, "guest expired")
        secret = guest.get("totp_secret")
        if isinstance(secret, bytes):
            if not totp_matches(secret, totp_code):
                self._fail(guest_id, "totp")
        elif totp_code:
            self._fail(guest_id, "not enrolled")
        challenge["consumed_at"] = utcnow()
        guest["status"] = "active"
        guest["last_login_at"] = utcnow()
        session_id = uuid.uuid4().hex
        bucket(self.store, "guest_sessions")[session_id] = {
            "id": session_id,
            "guest_id": guest_id,
            "tenant_id": guest.get("tenant_id"),
            "expires_at": utcnow() + timedelta(seconds=_session_seconds()),
            "enrolled": isinstance(secret, bytes),
        }
        tenant_id = guest.get("tenant_id")
        user_id = guest.get("id")
        if not isinstance(tenant_id, uuid.UUID) or not isinstance(user_id, uuid.UUID):
            self._fail(guest_id, "guest")
        actor = Actor(
            tenant_id=tenant_id,
            user_id=user_id,
            permissions=frozenset(),
            kind="guest",
        )
        audit(self.store, actor, "guest.login", "guest", guest_id, {})
        return {
            "session_id": session_id,
            "guest_id": str(guest_id),
            "enrolled": isinstance(secret, bytes),
            "email": guest.get("email"),
        }

    def enroll(self, session_id: str) -> dict[str, str]:
        session = bucket(self.store, "guest_sessions").get(session_id)
        if not isinstance(session, dict):
            raise NotFoundError()
        guest = bucket(self.store, "guests").get(session.get("guest_id"))
        if not isinstance(guest, dict):
            raise NotFoundError()
        if isinstance(guest.get("totp_secret"), bytes):
            raise ArError(ErrorCode.INVALID_STATE, "totp is already enrolled")
        secret = os.urandom(20)
        guest["totp_secret"] = secret
        guest["totp_secret_ref_id"] = new_id()
        self.store.secret_values[guest["totp_secret_ref_id"]] = secret
        session["enrolled"] = True
        encoded = base64.b32encode(secret).decode("ascii").rstrip("=")
        email = str(guest.get("email") or "guest")
        return {"otpauth_uri": f"otpauth://totp/Agentic:{email}?secret={encoded}&issuer=Agentic"}

    def principal_for(self, session_id: str) -> dict[str, object] | None:
        session = bucket(self.store, "guest_sessions").get(session_id)
        if not isinstance(session, dict):
            return None
        expires = session.get("expires_at")
        if isinstance(expires, type(utcnow())) and expires < utcnow():
            return None
        guest = bucket(self.store, "guests").get(session.get("guest_id"))
        if not isinstance(guest, dict) or guest.get("status") == "revoked":
            return None
        return guest

    def _grant(
        self, actor: Actor, guest: dict[str, object], body: dict[str, object]
    ) -> dict[str, object]:
        grant_id = new_id()
        raw_scope = body.get("scope")
        scope: dict[str, object] = raw_scope if isinstance(raw_scope, dict) else {}
        expires = guest.get("expires_at")
        grant = {
            "id": grant_id,
            "tenant_id": actor.tenant_id,
            "guest_id": guest["id"],
            "portal": str(body.get("portal") or "records"),
            "scope": {
                "evidence_ids": _id_list(scope.get("evidence_ids")),
                "binder_ids": _id_list(scope.get("binder_ids")),
                "pack_record_ids": _id_list(scope.get("pack_record_ids")),
            },
            "expires_at": expires,
            "watermark": body.get("watermark") is not False,
            "created_at": utcnow(),
        }
        bucket(self.store, "guest_grants")[grant_id] = grant
        return grant

    def _challenge(self, guest: dict[str, object]) -> str:
        token = uuid.uuid4().hex
        row_id = new_id()
        bucket(self.store, "guest_challenges")[row_id] = {
            "id": row_id,
            "tenant_id": guest.get("tenant_id"),
            "guest_id": guest.get("id"),
            "email": guest.get("email"),
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
            "token": token,
            "expires_at": utcnow() + timedelta(seconds=_link_seconds()),
            "consumed_at": None,
            "created_at": utcnow(),
        }
        return token

    def _challenge_for(self, token: str) -> dict[str, object] | None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        for row in bucket(self.store, "guest_challenges").values():
            if row.get("token_hash") == digest or row.get("token") == token:
                return row
        return None

    def _by_email(self, email: str) -> dict[str, object] | None:
        for row in bucket(self.store, "guests").values():
            if str(row.get("email") or "").lower() == email.lower():
                return row
        return None

    def _row(self, actor: Actor, guest_id: uuid.UUID) -> dict[str, object]:
        row = bucket(self.store, "guests").get(guest_id)
        if not isinstance(row, dict) or not own(row, actor.tenant_id):
            missing()
        return row

    def _out(self, row: dict[str, object]) -> dict[str, object]:
        body = public(row)
        body.pop("totp_secret", None)
        body["grants"] = [
            public(grant)
            for grant in bucket(self.store, "guest_grants").values()
            if grant.get("guest_id") == row.get("id")
        ]
        return body

    def _fail(self, guest_id: object, reason: str) -> NoReturn:
        if isinstance(guest_id, uuid.UUID):
            guest = bucket(self.store, "guests").get(guest_id)
            tenant = guest.get("tenant_id") if isinstance(guest, dict) else None
            if isinstance(tenant, uuid.UUID):
                actor = Actor(
                    tenant_id=tenant, user_id=guest_id, permissions=frozenset(), kind="guest"
                )
                audit(
                    self.store,
                    actor,
                    "guest.login_failed",
                    "guest",
                    guest_id,
                    {"reason": reason},
                    outcome="failure",
                )
        raise ArError(ErrorCode.UNAUTHENTICATED, "guest login failed")


def guest_allows(store: Any, actor: Actor, kind: str, record_id: uuid.UUID) -> bool:
    now = utcnow()
    for grant in bucket(store, "guest_grants").values():
        if grant.get("guest_id") != actor.user_id or grant.get("tenant_id") != actor.tenant_id:
            continue
        expires = grant.get("expires_at")
        if isinstance(expires, type(now)) and expires < now:
            continue
        scope = grant.get("scope")
        if not isinstance(scope, dict):
            continue
        key = "evidence_ids" if kind == "evidence" else "binder_ids"
        if str(record_id) in {str(item) for item in scope.get(key, [])}:
            return True
    return False


def totp_matches(secret: bytes, code: str, *, when: datetime | None = None) -> bool:
    moment = when if isinstance(when, datetime) else utcnow()
    stamp = int(moment.timestamp())
    return any(_totp(secret, stamp + offset) == code for offset in (-30, 0, 30))


def _totp(secret: bytes, stamp: int) -> str:
    counter = int(stamp // 30).to_bytes(8, "big")
    digest = hmac.new(secret, counter, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(binary % 1_000_000).zfill(6)


def _id_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _max_days() -> int:
    raw = os.environ.get("AR_GUEST_MAX_TTL_DAYS", "").strip()
    return int(raw) if raw else _MAX_DAYS


def _link_seconds() -> int:
    raw = os.environ.get("AR_GUEST_MAGIC_LINK_TTL_S", "").strip()
    return int(raw) if raw else _LINK_SECONDS


def _session_seconds() -> int:
    raw = os.environ.get("AR_GUEST_SESSION_TTL_S", "").strip()
    return int(raw) if raw else _SESSION_SECONDS
