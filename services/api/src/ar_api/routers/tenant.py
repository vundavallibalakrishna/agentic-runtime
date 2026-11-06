"""Current tenant. Spec: docs/03-specs/02-identity-tenancy.md §3.1."""

from fastapi import APIRouter, Depends, Request

from ar_api.deps import IdentityDep, TenantWriterDep, expose, require_permission
from ar_contracts.api_model import ApiModel

router = APIRouter()


class MaskingKind(ApiModel):
    name: str
    source: str
    masked: bool
    default: bool


class MaskingView(ApiModel):
    enabled: bool
    uses_default: bool
    min_score: float
    default_min_score: float
    kinds: list[MaskingKind]


class TenantPatch(ApiModel):
    name: str | None = None
    settings: dict[str, object] | None = None


@router.get("/api/v1/tenant", dependencies=[Depends(require_permission("tenant:read"))])
@expose(public=False, permission="tenant:read")
async def get_tenant(identity: IdentityDep) -> dict[str, object]:
    tenant = await identity.store.get_tenant()
    if tenant is None:
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError("tenant not found")
    plan = await identity.store.get_plan(tenant.plan_id)
    return {
        "id": str(tenant.id),
        "slug": tenant.slug,
        "name": tenant.name,
        "status": tenant.status,
        "plan": None
        if plan is None
        else {"key": plan.key, "name": plan.name, "limits": plan.limits},
        "isolation_tier": tenant.isolation_tier,
        "data_residency": tenant.data_residency,
        "billing_currency": tenant.billing_currency.strip(),
        "settings": tenant.settings,
        "created_at": tenant.created_at.isoformat(),
    }


@router.get("/api/v1/tenant/masking", dependencies=[Depends(require_permission("tenant:read"))])
@expose(public=False, permission="tenant:read")
async def get_masking(identity: IdentityDep) -> MaskingView:
    """Every kind of personal data the product recognises, and what this tenant masks."""
    from ar_common.errors import NotFoundError  # noqa: PLC0415
    from ar_domain.pii.settings import masking_view  # noqa: PLC0415

    tenant = await identity.store.get_tenant()
    if tenant is None:
        raise NotFoundError("tenant not found")
    return MaskingView.model_validate(masking_view(tenant.settings))


@router.patch("/api/v1/tenant", dependencies=[Depends(require_permission("tenant:manage"))])
@expose(public=False, permission="tenant:manage")
async def patch_tenant(
    body: TenantPatch, identity: TenantWriterDep, request: Request
) -> dict[str, object]:
    tenant = await identity.update_tenant(name=body.name, settings_patch=body.settings)
    request.app.state.chat.tenant_settings[tenant.id] = tenant.settings
    return {"id": str(tenant.id), "name": tenant.name, "settings": tenant.settings}
