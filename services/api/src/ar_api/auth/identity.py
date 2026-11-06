"""Turn a completed sign-in into a tenant and a person.

A process attached to a database matches the token's organization against the tenant it
serves and the address against that tenant's users. A store with no database behind it
(unit tests, a dev process without Postgres) holds only the demo tenant.
"""

from fastapi import Request

from ar_api.auth.complete import LoginError, login_result, profile_for
from ar_domain.audit.service import record
from ar_domain.db.context import Principal, TenantContext
from ar_domain.db.session import tenant_session
from ar_domain.durable.bind import binding_from
from ar_domain.identity.repository import IdentityRepository
from ar_domain.identity.service import IdentityService


async def resolve_login_identity(request: Request, result: dict[str, object]) -> dict[str, object]:
    """Return the session fields for this sign-in, or raise ``LoginError``."""
    store = request.app.state.chat
    if store.durable_engine is None:
        return _demo_identity(result)
    binding = binding_from(store)
    if binding is None:
        raise LoginError("tenant_not_found")
    organization = str(result.get("organization") or "")
    if organization and organization.lower() != binding.slug.lower():
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


def _demo_identity(result: dict[str, object]) -> dict[str, object]:
    """Sign-in against the demo tenant of a store that has no database."""
    if result.get("tenant_id") and result.get("user_id"):
        return result
    user = profile_for(str(result.get("email") or ""), str(result.get("organization") or ""))
    return login_result(
        user,
        access_token=str(result.get("access_token", "")),
        refresh_token=str(result.get("refresh_token", "")),
    )
