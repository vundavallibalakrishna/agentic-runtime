"""SCIM 2.0 subset. Spec: docs/03-specs/02-identity-tenancy.md §3.9."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request

from ar_api.deps import IdentityDep, expose
from ar_common.errors import UnauthenticatedError

router = APIRouter()


def _guard(request: Request) -> None:
    principal = getattr(request.state, "principal", None)
    if principal is None or principal.auth_method != "scim":
        raise UnauthenticatedError("SCIM token required")


@router.get("/scim/v2/ServiceProviderConfig")
@expose(public=False, permission=None)
async def service_provider_config(request: Request) -> dict[str, object]:
    _guard(request)
    return {
        "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
        "patch": {"supported": True},
        "filter": {"supported": True, "maxResults": 200},
        "authenticationSchemes": [{"type": "oauthbearertoken", "name": "Bearer"}],
    }


@router.get("/scim/v2/Schemas")
@expose(public=False, permission=None)
async def schemas(request: Request) -> dict[str, object]:
    _guard(request)
    return {"Resources": [], "totalResults": 0}


@router.get("/scim/v2/ResourceTypes")
@expose(public=False, permission=None)
async def resource_types(request: Request) -> dict[str, object]:
    _guard(request)
    return {
        "Resources": [
            {"id": "User", "endpoint": "/Users"},
            {"id": "Group", "endpoint": "/Groups"},
        ]
    }


@router.get("/scim/v2/Users")
@expose(public=False, permission=None)
async def list_users(
    request: Request,
    identity: IdentityDep,
    scim_filter: Annotated[str | None, Query(alias="filter")] = None,
) -> dict[str, object]:
    _guard(request)
    parsed = identity.parse_filter(scim_filter)
    rows = await identity.store.list_users(status=None, query=None)
    if parsed is not None and parsed[0] == "userName":
        rows = [row for row in rows if row.email == parsed[1]]
    if parsed is not None and parsed[0] == "externalId":
        rows = [row for row in rows if row.scim_external_id == parsed[1]]
    resources = [_user(row) for row in rows]
    return {"Resources": resources, "totalResults": len(resources)}


@router.post("/scim/v2/Users")
@expose(public=False, permission=None)
async def create_user(
    request: Request, identity: IdentityDep, body: dict[str, object]
) -> dict[str, object]:
    _guard(request)
    from ar_domain.identity.models import User  # noqa: PLC0415

    email = str(body.get("userName", ""))
    row = User(
        tenant_id=identity.ctx.tenant_id,
        idp_subject=str(body.get("externalId", email)),
        email=email,
        display_name=email,
        scim_external_id=None if body.get("externalId") is None else str(body["externalId"]),
        status="active" if body.get("active", True) else "deprovisioned",
    )
    identity.store.add(row)
    return _user(row)


@router.get("/scim/v2/Users/{user_id}")
@expose(public=False, permission=None)
async def get_user(
    user_id: uuid.UUID, request: Request, identity: IdentityDep
) -> dict[str, object]:
    _guard(request)
    return _user(await identity._user(user_id))


@router.patch("/scim/v2/Users/{user_id}")
@expose(public=False, permission=None)
async def patch_user(
    user_id: uuid.UUID, request: Request, identity: IdentityDep, body: dict[str, object]
) -> dict[str, object]:
    _guard(request)
    operations = body.get("Operations", [])
    if not isinstance(operations, list):
        operations = []
    row = await identity.scim_set_active(
        user_id, [item for item in operations if isinstance(item, dict)]
    )
    return _user(row)


@router.put("/scim/v2/Users/{user_id}")
@expose(public=False, permission=None)
async def put_user(
    user_id: uuid.UUID, request: Request, identity: IdentityDep, body: dict[str, object]
) -> dict[str, object]:
    _guard(request)
    row = await identity._user(user_id)
    if "active" in body:
        row.status = "active" if body["active"] else "deprovisioned"
    return _user(row)


@router.delete("/scim/v2/Users/{user_id}")
@expose(public=False, permission=None)
async def delete_user(
    user_id: uuid.UUID, request: Request, identity: IdentityDep
) -> dict[str, bool]:
    _guard(request)
    row = await identity._user(user_id)
    row.status = "deprovisioned"
    return {"deprovisioned": True}


@router.get("/scim/v2/Groups")
@expose(public=False, permission=None)
async def list_groups(
    request: Request,
    identity: IdentityDep,
    scim_filter: Annotated[str | None, Query(alias="filter")] = None,
) -> dict[str, object]:
    _guard(request)
    parsed = identity.parse_filter(scim_filter)
    rows = await identity.store.list_groups(source="scim")
    if parsed is not None and parsed[0] == "displayName":
        rows = [row for row in rows if row.name == parsed[1]]
    return {"Resources": [_group(row) for row in rows], "totalResults": len(rows)}


@router.post("/scim/v2/Groups")
@expose(public=False, permission=None)
async def create_group(
    request: Request, identity: IdentityDep, body: dict[str, object]
) -> dict[str, object]:
    _guard(request)
    from ar_domain.identity.models import Group  # noqa: PLC0415

    row = Group(
        tenant_id=identity.ctx.tenant_id,
        name=str(body.get("displayName", "")),
        source="scim",
        external_id=None if body.get("externalId") is None else str(body["externalId"]),
    )
    identity.store.add(row)
    return _group(row)


@router.patch("/scim/v2/Groups/{group_id}")
@expose(public=False, permission=None)
async def patch_group(
    group_id: uuid.UUID, request: Request, identity: IdentityDep, body: dict[str, object]
) -> dict[str, object]:
    _guard(request)
    operations = body.get("Operations", [])
    if not isinstance(operations, list):
        operations = []
    row = await identity.scim_patch_group(
        group_id, [item for item in operations if isinstance(item, dict)]
    )
    return _group(row)


def _user(row: object) -> dict[str, object]:
    return {
        "id": str(row.id),  # type: ignore[attr-defined]
        "userName": row.email,  # type: ignore[attr-defined]
        "active": row.status == "active",  # type: ignore[attr-defined]
        "externalId": row.scim_external_id,  # type: ignore[attr-defined]
    }


def _group(row: object) -> dict[str, object]:
    return {"id": str(row.id), "displayName": row.name, "externalId": row.external_id}  # type: ignore[attr-defined]
