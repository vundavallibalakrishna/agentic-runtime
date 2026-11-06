"""Turn a completed sign-in into a tenant and a person.

The token's organization must be the tenant this process serves, and the address must be
an active user of that tenant. Roles and permissions come from the tenant's rows.
"""

from fastapi import Request

from ar_api.auth.complete import LoginError
from ar_api.deps import identity_store
from ar_domain.db.context import Principal, TenantContext
from ar_domain.durable.bind import binding_from
from ar_domain.identity.service import IdentityService


async def resolve_login_identity(request: Request, result: dict[str, object]) -> dict[str, object]:
    """Return the session fields for this sign-in, or raise ``LoginError``."""
    store = request.app.state.chat
    binding = binding_from(store)
    if binding is None:
        # No tenant is being served, so nobody can sign in.
        raise LoginError("tenant_not_found")
    organization = str(result.get("organization") or "")
    if organization and organization.lower() != binding.slug.lower():
        raise LoginError("tenant_not_found")
    principal = Principal(kind="system", id="login", tenant_id=binding.tenant_id)
    ctx = TenantContext.from_principal(principal, str(request.state.request_id))
    async with identity_store(request, ctx, engine=store.durable_engine) as identity:
        tenant = await identity.get_tenant()
        if tenant is None:
            raise LoginError("tenant_not_found")
        if tenant.status != "active":
            raise LoginError("tenant_suspended")
        user = await identity.get_user_by_email(str(result.get("email", "")).lower())
        if user is None:
            raise LoginError("tenant_not_found")
        if user.status != "active":
            raise LoginError("user_suspended")
        permissions, roles = await IdentityService(identity).effective_for(user.id)
        await identity.audit_login(user)
        # Policy and approvals read a person's roles from the store.
        store.user_roles[user.id] = set(roles)
        store.display_names[user.id] = user.display_name
        store.user_emails[user.id] = str(user.email).lower()
        store.user_statuses[user.id] = user.status
        return {
            **result,
            "tenant_id": str(tenant.id),
            "user_id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "permissions": sorted(permissions),
            "roles": sorted(roles),
        }
