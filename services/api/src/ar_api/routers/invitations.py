"""Invitations. Spec: docs/03-specs/02-identity-tenancy.md §3.4."""

import asyncio
import uuid

from fastapi import APIRouter, Depends
from pydantic import Field

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.api_model import ApiModel
from ar_domain.identity.tokens import sha256_hex
from ar_domain.notifications.smtp_mail import send_install_mail

router = APIRouter()


class InvitationCreate(ApiModel):
    emails: list[str] = Field(min_length=1, max_length=100)
    role_keys: list[str] = Field(default_factory=lambda: ["member"])


def _invite(row: object) -> dict[str, object]:
    return {
        "id": str(row.id),  # type: ignore[attr-defined]
        "email": row.email,  # type: ignore[attr-defined]
        "role_keys": list(row.role_keys),  # type: ignore[attr-defined]
        "expires_at": row.expires_at.isoformat(),  # type: ignore[attr-defined]
        "accepted_at": None if row.accepted_at is None else row.accepted_at.isoformat(),  # type: ignore[attr-defined]
    }


@router.get("/api/v1/invitations", dependencies=[Depends(require_permission("users:manage"))])
@expose(public=False, permission="users:manage")
async def list_invitations(identity: IdentityDep) -> dict[str, object]:
    rows = await identity.store.list_invitations()
    return {"data": [_invite(row) for row in rows], "next_cursor": None}


@router.post("/api/v1/invitations", dependencies=[Depends(require_permission("users:manage"))])
@expose(public=False, permission="users:manage")
async def create_invitations(
    body: InvitationCreate, identity: IdentityDep
) -> list[dict[str, object]]:
    created = await identity.invite(body.emails, body.role_keys)
    sent: list[dict[str, object]] = []
    for row, token in created:
        mailed = await asyncio.to_thread(_send, row.email, token)
        # The invitation exists either way; the caller is told whether its mail went out.
        sent.append(_invite(row) | {"token": token, "mail": mailed})
    return sent


@router.delete(
    "/api/v1/invitations/{invitation_id}",
    dependencies=[Depends(require_permission("users:manage"))],
)
@expose(public=False, permission="users:manage")
async def revoke_invitation(invitation_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    await identity.revoke_invitation(invitation_id)
    return {"revoked": True}


@router.post("/api/v1/invitations/{token}:accept")
@expose(public=True, permission=None)
async def accept_invitation(token: str, identity: IdentityDep) -> dict[str, str]:
    row = await identity.accept_invitation(sha256_hex(token), identity.ctx.principal.email or "")
    return {"email": row.email, "status": "accepted"}


def _send(email: str, token: str) -> dict[str, str]:
    """Mail one invitation through the install's server and say what happened."""
    return send_install_mail(email, "You are invited", f"Open /invite/{token} to join.")
