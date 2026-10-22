"""HTTP entrypoint for api."""

import os
from collections.abc import Awaitable, Callable

import orjson
from fastapi import FastAPI
from pydantic import SecretStr

from ar_api.auth.routes import router as auth_router
from ar_api.auth.session import MemorySessionStore, session_key_bytes
from ar_api.middleware.idempotency import IdempotencyMiddleware, MemoryIdempotencyStore
from ar_api.middleware.stack import AuthenticateMiddleware, CsrfMiddleware, RateLimitMiddleware
from ar_api.ratelimit import MemoryTokenBucket
from ar_api.routers.agents import router as agents_router
from ar_api.routers.api_keys import router as api_keys_router
from ar_api.routers.audit import router as audit_router
from ar_api.routers.builder import router as builder_router
from ar_api.routers.bundles import router as bundles_router
from ar_api.routers.connections import router as connections_router
from ar_api.routers.content_packs import router as packs_router
from ar_api.routers.credential_providers import router as providers_router
from ar_api.routers.data_connections import router as data_connections_router
from ar_api.routers.domains import router as domains_router
from ar_api.routers.groups import router as groups_router
from ar_api.routers.identity_providers import router as idp_router
from ar_api.routers.invitations import router as invitations_router
from ar_api.routers.m2 import router as m2_router
from ar_api.routers.me import router as me_router
from ar_api.routers.meta import router as meta_router
from ar_api.routers.notifications import router as notifications_router
from ar_api.routers.platform_plans import router as plans_router
from ar_api.routers.platform_tenants import router as platform_router
from ar_api.routers.roles import router as roles_router
from ar_api.routers.scim import router as scim_router
from ar_api.routers.scim_tokens import router as scim_tokens_router
from ar_api.routers.secrets import router as secrets_router
from ar_api.routers.service_accounts import router as service_accounts_router
from ar_api.routers.signup import router as signup_router
from ar_api.routers.support_access import router as support_router
from ar_api.routers.teams import router as teams_router
from ar_api.routers.tenant import router as tenant_router
from ar_api.routers.tool_servers import router as tool_servers_router
from ar_api.routers.tools import router as tools_router
from ar_api.routers.users import router as users_router
from ar_api.routers.webhooks import router as webhooks_router
from ar_api.secrets_runtime import MemorySecretApi
from ar_api.state import AuditApi, NotificationApi, PlatformApi, WebhookApi
from ar_common.host_ports import listen_port
from ar_common.settings import BaseServiceSettings, EnvName
from ar_common.web import create_app
from ar_domain.audit.service import install_platform_hook
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.db.context import Principal

LISTEN_PORT = 8000


class Settings(BaseServiceSettings):
    """API process settings. Names match the environment catalogue."""

    service_name: str = "api"
    public_url: str = "http://localhost:3000"
    oidc_issuer: str = "http://localhost:8180/realms/agentic-runtime"
    oidc_client_id: str = "ar-web"
    oidc_client_secret: SecretStr = SecretStr("ar-web-dev-secret")
    oidc_api_audience: str = "ar-api"
    session_encryption_key: SecretStr = SecretStr("")
    session_ttl_s: int = 43_200
    session_max_age_s: int = 604_800
    step_up_ttl_s: int = 600
    secrets_backend: str = "db_encrypted"
    db_encryption_keys: str = ""
    db_encryption_active_key: str = "k1"
    secret_cache_ttl_s: int = 60
    saas_self_signup: bool = False
    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_from: str = "noreply@dev.local"
    smtp_starttls: bool = False
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    webhook_allow_private: bool = False
    tenant_delete_grace_days: int = 7
    vault_addr: str = "http://localhost:8200"
    vault_token: SecretStr = SecretStr("")
    vault_kv_mount: str = "ar"
    vault_auth: str = "token"
    vault_role: str = ""


async def _complete_login(code: str, saved: dict[str, object]) -> dict[str, object]:
    from ar_api.auth.complete import complete_oidc_login  # noqa: PLC0415

    return await complete_oidc_login(Settings(), code, saved)


async def _resolve_principal(scope: object) -> object:
    from ar_api.middleware.stack import presented_credential  # noqa: PLC0415

    if not isinstance(scope, dict):
        return None
    found = presented_credential(scope)
    if found is None:
        return None
    loader = scope["app"].state.credential_loader
    return await loader(found[0], found[1])


def _session_loader(app: FastAPI) -> Callable[[str, str], Awaitable[Principal | None]]:
    """Resolve ``ar_session`` to the person stored on that session."""

    async def load(kind: str, value: str) -> Principal | None:
        if kind != "session":
            return None
        sessions = app.state.sessions
        data = await sessions.get(value)
        if data is None:
            return None
        from ar_api.auth.dev_users import by_id  # noqa: PLC0415

        known = by_id(data.user_id)
        email = data.email or (known.email if known is not None else "")
        display_name = data.display_name or (known.display_name if known is not None else email)
        permissions = (
            frozenset(data.permissions)
            if data.permissions
            else (known.permissions if known is not None else frozenset())
        )
        roles = (
            frozenset(data.roles)
            if data.roles
            else (frozenset(known.roles) if known is not None else frozenset())
        )
        return Principal(
            kind="user",
            id=str(data.user_id),
            tenant_id=data.tenant_id,
            permissions=permissions,
            auth_method="session",
            email=email,
            display_name=display_name or "Signed in",
            session_id=value,
            csrf_token=data.csrf_token,
            roles=roles,
        )

    return load


async def _signup(slug: str, name: str, email: str) -> str:
    del slug, name, email
    return "pending"


def _configure_chat(chat: ChatService, settings: Settings) -> None:
    """Pack trust follows the environment. Dev and CI accept unsigned packs."""
    raw = os.environ.get("AR_PACK_SIGNATURE_REQUIRED")
    if raw is None:
        chat.pack_signature_required = settings.env not in {EnvName.DEV, EnvName.CI}
    else:
        chat.pack_signature_required = raw.strip().lower() in {"1", "true", "yes"}
    keys = os.environ.get("AR_PACK_TRUSTED_KEYS")
    if not keys:
        return
    loaded = orjson.loads(keys)
    if isinstance(loaded, dict):
        chat.pack_trusted_keys = {str(key): str(value) for key, value in loaded.items()}


def create_application() -> FastAPI:
    """Build the ASGI app. Health does not connect to Postgres or Temporal."""
    settings = Settings()
    docs = None if settings.env is EnvName.PROD else "/api/docs"
    inner: list[tuple[type, dict[str, object]]] = [
        (AuthenticateMiddleware, {}),
        (CsrfMiddleware, {}),
        (RateLimitMiddleware, {}),
        (IdempotencyMiddleware, {}),
    ]
    app = create_app(
        "api",
        settings,
        routers=[
            meta_router,
            auth_router,
            tenant_router,
            me_router,
            users_router,
            invitations_router,
            groups_router,
            teams_router,
            roles_router,
            service_accounts_router,
            api_keys_router,
            audit_router,
            secrets_router,
            domains_router,
            idp_router,
            scim_router,
            scim_tokens_router,
            support_router,
            signup_router,
            platform_router,
            plans_router,
            notifications_router,
            webhooks_router,
            agents_router,
            bundles_router,
            packs_router,
            builder_router,
            m2_router,
            tool_servers_router,
            tools_router,
            providers_router,
            connections_router,
            data_connections_router,
        ],
        inner_middleware=inner,
        docs_url=docs,
        camel_json=True,
    )
    key = session_key_bytes(
        settings.session_encryption_key.get_secret_value(),
        settings.cursor_secret.get_secret_value(),
        prod=settings.env is EnvName.PROD,
    )
    app.state.sessions = MemorySessionStore(key)
    app.state.login_states = {}
    app.state.complete_login = _complete_login
    app.state.resolve_principal = _resolve_principal
    app.state.credential_loader = _session_loader(app)
    app.state.chat = ChatService(
        allow_loopback=settings.env in {EnvName.DEV, EnvName.CI},
        scanner="none" if settings.env in {EnvName.DEV, EnvName.CI} else "clamav",
    )
    _configure_chat(app.state.chat, settings)
    if settings.env in {EnvName.DEV, EnvName.CI}:
        app.state.chat.seed_showcase()
    app.state.demo_user_id = demo_id("admin")
    app.state.demo_tenant_id = demo_id("tenant")
    app.state.allow_test_auth = False
    app.state.rate_limiter = MemoryTokenBucket()
    app.state.rate_limit = 600
    app.state.idempotency = MemoryIdempotencyStore()
    app.state.identity_override = None
    app.state.secret_api = MemorySecretApi()
    app.state.audit_api = AuditApi()
    app.state.platform = PlatformApi()
    app.state.notifications = NotificationApi()
    app.state.webhooks = WebhookApi()
    app.state.signup = _signup
    install_platform_hook()
    return app


def main() -> None:
    """Listen on ``AR_PORT`` (default 8000)."""
    import uvicorn  # noqa: PLC0415

    uvicorn.run(
        create_application(),
        host="0.0.0.0",  # noqa: S104
        port=listen_port("AR_PORT", LISTEN_PORT),
    )


LoginCompleter = Callable[[str, dict[str, object]], Awaitable[dict[str, object]]]
