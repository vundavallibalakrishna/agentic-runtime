"""Invitations. Spec: docs/03-specs/02-identity-tenancy.md §3.4."""

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import IdentityDep, expose, require_permission
from ar_contracts.json_api import ApiModel
from ar_domain.identity.mail import send_email
from ar_domain.identity.tokens import sha256_hex

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
    body: InvitationCreate, identity: IdentityDep, request: Request
) -> list[dict[str, object]]:
    created = await identity.invite(body.emails, body.role_keys)
    settings = request.app.state.settings
    sent: list[dict[str, object]] = []
    for row, token in created:
        _send(settings, row.email, token)
        sent.append(_invite(row) | {"token": token})
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


def _send(settings: object, email: str, token: str) -> None:
    host = str(getattr(settings, "smtp_host", ""))
    if not host:
        return
    try:
        send_email(
            host=host,
            port=int(getattr(settings, "smtp_port", 1025)),
            sender=str(getattr(settings, "smtp_from", "noreply@localhost")),
            recipient=email,
            subject="You are invited to Agentic Runtime",
            body=f"Open /invite/{token} to join.",
            username=str(getattr(settings, "smtp_username", "")),
            password=getattr(settings, "smtp_password", ""),
            starttls=bool(getattr(settings, "smtp_starttls", False)),
        )
    except OSError:
        return
