"""HTTP entrypoint for api."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from pydantic import SecretStr

from ar_api.auth.routes import router as auth_router
from ar_api.auth.session import MemorySessionStore, session_key_bytes
from ar_api.middleware.idempotency import IdempotencyMiddleware, MemoryIdempotencyStore
from ar_api.middleware.stack import AuthenticateMiddleware, CsrfMiddleware, RateLimitMiddleware
from ar_api.ratelimit import MemoryTokenBucket
from ar_api.routers.api_keys import router as api_keys_router
from ar_api.routers.audit import router as audit_router
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
from ar_domain.identity.permissions import PERMISSION_KEYS

LISTEN_PORT = 8000


class Settings(BaseServiceSettings):
    """API process settings. Names match the environment catalogue."""

    service_name: str = "api"
    public_url: str = "http://localhost:3000"
    oidc_issuer: str = "http://localhost:8180/realms/agentic-runtime"
    oidc_client_id: str = "ar-web"
    oidc_client_secret: SecretStr = SecretStr("")
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


async def _complete_login(code: str, saved: dict[str, object]) -> dict[str, str]:
    del code, saved
    raise RuntimeError("login completion is provided by the OIDC callback adapter")


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
    """Resolve ``ar_session`` to the dev principal stored in the session map."""

    async def load(kind: str, value: str) -> Principal | None:
        if kind != "session":
            return None
        sessions = app.state.sessions
        data = await sessions.get(value)
        if data is None:
            return None
        return Principal(
            kind="user",
            id=str(data.user_id),
            tenant_id=data.tenant_id,
            permissions=PERMISSION_KEYS,
            auth_method="session",
            email="admin@dev.local",
            display_name="Dev Admin",
            session_id=value,
            csrf_token=data.csrf_token,
            roles=frozenset({"tenant_admin"}),
        )

    return load


async def _signup(slug: str, name: str, email: str) -> str:
    del slug, name, email
    return "pending"


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
            m2_router,
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


LoginCompleter = Callable[[str, dict[str, object]], Awaitable[dict[str, str]]]
