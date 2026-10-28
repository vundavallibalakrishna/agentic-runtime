"""Resolve local login sessions against the bound tenant's persisted identities."""

from fastapi import Request

from ar_api.auth.complete import LoginError
from ar_domain.audit.service import record
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.durable.bind import binding_from
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.service import IdentityService


async def resolve_login_identity(request: Request, result: dict[str, object]) -> dict[str, object]:
    """Keep retained database IDs and effective permissions; reject inactive accounts."""
    store = request.app.state.chat
    if store.durable_engine is None:
        return result
    binding = binding_from(store)
    if binding is None:
        raise LoginError("tenant_not_found")
    principal = Principal(kind="system", id="login", tenant_id=binding.tenant_id)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    async with tenant_session(ctx, engine=store.durable_engine) as session:
        repo = IdentityRepository(session, ctx)
        tenant = await repo.get_tenant()
        if tenant is None:
            raise LoginError("tenant_not_found")
        if tenant.status != "active":
            raise LoginError("tenant_suspended")
        user = await repo.get_user_by_email(str(result.get("email", "")).lower())
        if user is None:
            raise LoginError("tenant_not_found")
        if user.status != "active":
            raise LoginError("user_suspended")
        permissions, roles = await IdentityService(repo).effective_for(user.id)
        await record(
            session,
            tenant_id=tenant.id,
            actor_type="user",
            actor_id=str(user.id),
            action="auth.login",
            target_type="user",
            target_id=str(user.id),
        )
        return {
            **result,
            "tenant_id": str(tenant.id),
            "user_id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "permissions": sorted(permissions),
            "roles": sorted(roles),
        }
