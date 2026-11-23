"""Every route has a permission or an allowlist reason.

A route whose handler sets ``__permission__`` is enforced with
``require_permission``. A route with no permission must be listed here with the
reason it is not a tenant permission.
"""

from fastapi.routing import APIRoute


def _allow(*rows: tuple[str, str, str]) -> dict[tuple[str, str], str]:
    return {(method, path): reason for method, path, reason in rows}


# (method, path) → why this route has no tenant permission.
ROUTE_ALLOWLIST: dict[tuple[str, str], str] = _allow(
    ("GET", "/healthz", "Liveness. No tenant data."),
    ("GET", "/readyz", "Readiness. No tenant data."),
    ("GET", "/metrics", "Install HMAC. Not a user session."),
    ("GET", "/api/docs", "API docs outside production."),
    ("GET", "/api/docs/oauth2-redirect", "Docs helper outside production."),
    ("GET", "/openapi.json", "OpenAPI document outside production."),
    ("GET", "/redoc", "Docs helper outside production."),
    ("GET", "/api/v1/meta", "Product name and version."),
    ("GET", "/api/v1/openapi.json", "Public OpenAPI for integrators."),
    ("GET", "/api/v1/schemas/{kind}", "Definition schemas. No tenant rows."),
    ("POST", "/api/v1/auth/login", "Password sign-in."),
    ("GET", "/api/v1/auth/oidc/start", "Starts the OIDC redirect."),
    ("GET", "/api/v1/auth/callback", "OIDC callback."),
    ("POST", "/api/v1/auth/logout", "Ends the caller's session."),
    ("GET", "/api/v1/auth/session", "The caller's own session."),
    ("POST", "/api/v1/auth/switch-tenant", "The caller's own memberships."),
    ("POST", "/api/v1/auth/password-reset", "Starts a reset. Does not reveal accounts."),
    ("POST", "/api/v1/auth/password-reset/confirm", "Completes a reset with the token."),
    ("POST", "/api/v1/auth/invitation", "Says what a mailed invitation is for."),
    ("POST", "/api/v1/auth/invitation/accept", "Creates the invited person."),
    ("POST", "/api/v1/auth/step-up", "Confirms the caller's step-up."),
    ("GET", "/api/v1/.well-known/jwks.json", "Public signing keys."),
    ("GET", "/api/v1/me", "The signed-in user's profile."),
    ("PATCH", "/api/v1/me", "The signed-in user edits their profile."),
    ("GET", "/api/v1/me/usage", "Only the caller's own month."),
    ("GET", "/api/v1/me/export", "Only the caller's own rows."),
    ("GET", "/api/v1/permissions", "Permission catalogue. No tenant rows."),
    ("GET", "/api/v1/notifications", "The caller's own notifications."),
    ("POST", "/api/v1/notifications/{notification_id}:read", "The caller marks their own item."),
    ("POST", "/api/v1/notifications:read-all", "The caller marks their own items."),
    ("POST", "/api/v1/notifications/push-subscriptions", "The caller's own push subscription."),
    (
        "DELETE",
        "/api/v1/notifications/push-subscriptions/{subscription_id}",
        "The caller removes their own subscription.",
    ),
    ("GET", "/api/v1/notifications/events", "The caller's own notification stream."),
    ("POST", "/api/v1/hooks/routines/{token}", "The hook token is the credential."),
    ("POST", "/api/v1/auth/guest/request-link", "Sends a guest link."),
    ("POST", "/api/v1/auth/guest/session", "Redeems a guest link."),
    ("POST", "/api/v1/auth/guest/totp/enroll", "The guest session is the credential."),
    ("POST", "/api/v1/guest/agents/{agent_id}/turns", "The guest session is the credential."),
    ("GET", "/api/v1/widget/integrations/{integration_id}", "Integration id is the credential."),
    ("POST", "/api/v1/widget/sessions", "Opens a widget session cookie."),
    ("GET", "/internal/v1/opa/bundles/ar.tar.gz", "OPA bearer token. No chat read unit."),
    ("GET", "/scim/v2/ServiceProviderConfig", "SCIM bearer, checked in _guard."),
    ("GET", "/scim/v2/Schemas", "SCIM bearer, checked in _guard."),
    ("GET", "/scim/v2/ResourceTypes", "SCIM bearer, checked in _guard."),
    ("GET", "/scim/v2/Users", "SCIM bearer, checked in _guard."),
    ("POST", "/scim/v2/Users", "SCIM bearer, checked in _guard."),
    ("GET", "/scim/v2/Users/{user_id}", "SCIM bearer, checked in _guard."),
    ("PATCH", "/scim/v2/Users/{user_id}", "SCIM bearer, checked in _guard."),
    ("PUT", "/scim/v2/Users/{user_id}", "SCIM bearer, checked in _guard."),
    ("DELETE", "/scim/v2/Users/{user_id}", "SCIM bearer, checked in _guard."),
    ("GET", "/scim/v2/Groups", "SCIM bearer, checked in _guard."),
    ("POST", "/scim/v2/Groups", "SCIM bearer, checked in _guard."),
    ("PATCH", "/scim/v2/Groups/{group_id}", "SCIM bearer, checked in _guard."),
    ("GET", "/api/v1/platform/health", "platform_admin, checked in the handler."),
    ("GET", "/api/v1/platform/plans", "platform_admin, checked in the handler."),
    ("POST", "/api/v1/platform/plans", "platform_admin, checked in the handler."),
    ("PATCH", "/api/v1/platform/plans/{plan_id}", "platform_admin, checked in the handler."),
    ("GET", "/api/v1/platform/tenants", "platform_admin, checked in _saas."),
    ("POST", "/api/v1/platform/tenants", "platform_admin, checked in _saas."),
    ("GET", "/api/v1/platform/tenants/{tenant_id}", "platform_admin, checked in _saas."),
    ("POST", "/api/v1/platform/tenants/{tenant_id}:suspend", "platform_admin, checked in _saas."),
    ("POST", "/api/v1/platform/tenants/{tenant_id}:resume", "platform_admin, checked in _saas."),
    ("POST", "/api/v1/platform/tenants/{tenant_id}:delete", "platform_admin, checked in _saas."),
    ("GET", "/api/v1/platform/usage", "platform_admin, checked in the handler."),
    ("GET", "/api/v1/platform/usage/export", "platform_admin, checked in the handler."),
    ("GET", "/api/v1/platform/model-providers", "platform_admin, checked in the handler."),
    ("POST", "/api/v1/platform/model-providers", "platform_admin, checked in the handler."),
    ("GET", "/v1", "External API index."),
    ("GET", "/v1/openapi.json", "External OpenAPI document."),
    ("POST", "/v1/agents/{slug}/conversations", "Agent API key."),
    ("POST", "/v1/agents/{slug}/conversations/{conversation_id}/messages", "Agent API key."),
    ("POST", "/v1/agents/{slug}:run", "Agent API key."),
    ("POST", "/v1/agents/{slug}/files", "Agent API key."),
    ("GET", "/v1/agents/{slug}/runs/{run_id}", "Agent API key and owned_run."),
    ("GET", "/v1/agents/{slug}/runs/{run_id}/events", "Agent API key and owned_run."),
    ("GET", "/v1/agents/{slug}/.well-known/agent-card.json", "Agent API key."),
    ("GET", "/.well-known/agent-card.json", "Agent API key."),
    ("POST", "/v1/agents/{slug}/a2a", "Agent API key. HTTP JSON-RPC."),
    ("POST", "/v1/a2a", "Agent API key. HTTP JSON-RPC."),
    ("POST", "/v1/agents/{slug}/mcp", "Agent API key. Session id is not the key id."),
    ("POST", "/v1/mcp", "Agent API key. Session id is not the key id."),
    ("POST", "/v1/research/runs", "Agent API key. The run is granted to that key."),
    ("GET", "/v1/research/runs/{run_id}", "Agent API key and run_for_key."),
    ("GET", "/v1/research/runs/{run_id}/events", "Agent API key and run_for_key."),
)

_SKIPPED_METHODS = frozenset({"HEAD", "OPTIONS"})


def ungoverned(app: object) -> list[str]:
    """Routes with no permission and no allowlist reason."""
    missing: list[str] = []
    for route in getattr(app, "routes", []):
        if not isinstance(route, APIRoute):
            continue
        permission = getattr(route.endpoint, "__permission__", None)
        if permission:
            continue
        for method in sorted(route.methods or []):
            if method in _SKIPPED_METHODS:
                continue
            if (method, route.path) not in ROUTE_ALLOWLIST:
                missing.append(f"{method} {route.path}")
    return missing
