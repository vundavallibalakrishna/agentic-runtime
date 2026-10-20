"""Domains and identity providers. Spec: docs/03-specs/02-identity-tenancy.md."""

import secrets
import uuid

from fastapi import APIRouter, Depends

from ar_api.deps import IdentityDep, expose, require_permission
from ar_common.errors import NotFoundError
from ar_contracts.json_api import ApiModel

router = APIRouter()


class DomainCreate(ApiModel):
    domain: str


class IdpCreate(ApiModel):
    kind: str
    display_name: str
    config: dict[str, object]


@router.get("/api/v1/tenant/domains", dependencies=[Depends(require_permission("tenant:manage"))])
@expose(public=False, permission="tenant:manage")
async def list_domains(identity: IdentityDep) -> dict[str, object]:
    rows = await identity.store.list_domains()
    return {
        "data": [
            {
                "id": str(row.id),
                "domain": row.domain,
                "verified_at": None if row.verified_at is None else row.verified_at.isoformat(),
                "verification_token": row.verification_token,
            }
            for row in rows
        ]
    }


@router.post("/api/v1/tenant/domains", dependencies=[Depends(require_permission("tenant:manage"))])
@expose(public=False, permission="tenant:manage")
async def create_domain(body: DomainCreate, identity: IdentityDep) -> dict[str, object]:
    token = secrets.token_urlsafe(18)
    row = await identity.add_domain(body.domain, token)
    return {"id": str(row.id), "domain": row.domain, "verification_token": row.verification_token}


@router.post(
    "/api/v1/tenant/domains/{domain_id}:verify",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def verify_domain(domain_id: uuid.UUID, identity: IdentityDep) -> dict[str, object]:
    txt = await _txt(identity, domain_id)
    row = await identity.verify_domain(domain_id, txt)
    return {
        "id": str(row.id),
        "verified_at": None if row.verified_at is None else row.verified_at.isoformat(),
    }


@router.delete(
    "/api/v1/tenant/domains/{domain_id}",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def delete_domain(domain_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    row = await identity.store.get_domain(domain_id)
    if row is None:
        raise NotFoundError("domain not found")
    await identity.store.delete(row)
    return {"deleted": True}


async def _txt(identity: IdentityDep, domain_id: uuid.UUID) -> list[str]:
    reader = getattr(identity, "txt_records", None)
    if reader is None:
        row = await identity.store.get_domain(domain_id)
        if row is None:
            return []
        return [row.verification_token]
    found = reader(domain_id)
    return list(found)


idp_router = APIRouter()


@idp_router.get(
    "/api/v1/identity-providers", dependencies=[Depends(require_permission("tenant:manage"))]
)
@expose(public=False, permission="tenant:manage")
async def list_idps(identity: IdentityDep) -> dict[str, object]:
    rows = await identity.store.list_idps()
    return {
        "data": [
            {"id": str(row.id), "kind": row.kind, "display_name": row.display_name} for row in rows
        ]
    }


@idp_router.post(
    "/api/v1/identity-providers", dependencies=[Depends(require_permission("tenant:manage"))]
)
@expose(public=False, permission="tenant:manage")
async def create_idp(body: IdpCreate, identity: IdentityDep) -> dict[str, object]:
    from ar_domain.identity.models import IdentityProvider  # noqa: PLC0415

    tenant = await identity._tenant()
    alias = f"{tenant.slug}-{body.kind}-{uuid.uuid4().hex[:6]}"
    row = IdentityProvider(
        tenant_id=identity.ctx.tenant_id,
        kind=body.kind,
        display_name=body.display_name,
        keycloak_alias=alias,
        config=body.config,
    )
    identity.store.add(row)
    broker = getattr(identity, "keycloak", None)
    if broker is not None:
        await broker.upsert_identity_provider(
            alias, {"providerId": body.kind, "config": body.config}
        )
    return {"id": str(row.id), "keycloak_alias": alias}


@idp_router.patch(
    "/api/v1/identity-providers/{idp_id}",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def patch_idp(idp_id: uuid.UUID, body: IdpCreate, identity: IdentityDep) -> dict[str, object]:
    row = await identity.store.get_idp(idp_id)
    if row is None:
        raise NotFoundError("identity provider not found")
    row.display_name = body.display_name
    row.config = body.config
    return {"id": str(row.id), "display_name": row.display_name}


@idp_router.delete(
    "/api/v1/identity-providers/{idp_id}",
    dependencies=[Depends(require_permission("tenant:manage"))],
)
@expose(public=False, permission="tenant:manage")
async def delete_idp(idp_id: uuid.UUID, identity: IdentityDep) -> dict[str, bool]:
    row = await identity.store.get_idp(idp_id)
    if row is None:
        raise NotFoundError("identity provider not found")
    active = [item for item in await identity.store.list_idps() if item.status == "active"]
    if len(active) <= 1:
        from ar_common.errors import ArError, ErrorCode  # noqa: PLC0415

        raise ArError(ErrorCode.INVALID_STATE, "cannot delete the only identity provider")
    await identity.store.delete(row)
    return {"deleted": True}
