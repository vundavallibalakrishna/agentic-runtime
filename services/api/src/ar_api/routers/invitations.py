"""Invitations. Spec: docs/03-specs/02-identity-tenancy.md §3.4."""

import asyncio
import uuid
from functools import partial

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from ar_api.deps import IdentityDep, expose, require_permission
from ar_common.settings import get_settings
from ar_contracts.api_model import ApiModel
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
    body: InvitationCreate, identity: IdentityDep, request: Request
) -> list[dict[str, object]]:
    created = await identity.invite(body.emails, body.role_keys)
    tenant = await identity.store.get_tenant()
    send = partial(
        _send,
        public_url=str(request.app.state.settings.public_url),
        tenant=str(getattr(tenant, "name", "") or ""),
        days=get_settings().invitation_ttl_days,
    )
    sent: list[dict[str, object]] = []
    for row, token in created:
        mailed = await asyncio.to_thread(send, row.email, token)
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


def _send(email: str, token: str, *, public_url: str, tenant: str, days: int) -> dict[str, str]:
    """Mail one invitation through the install's server and say what happened."""
    link = f"{public_url.rstrip('/')}/invite?token={token}"
    return send_install_mail(
        email,
        f"You are invited to join {tenant}" if tenant else "You are invited",
        f"Open this link to choose your name and password:\n\n{link}\n\n"
        f"The link works once, for {days} days.",
    )
