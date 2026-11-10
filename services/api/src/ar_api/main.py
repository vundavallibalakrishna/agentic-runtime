"""HTTP entrypoint for api."""

import os
import uuid
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import orjson
from fastapi import FastAPI
from pydantic import SecretStr

from ar_api.auth.routes import router as auth_router
from ar_api.auth.session import session_key_bytes
from ar_api.middleware.durable import DurableMiddleware
from ar_api.middleware.idempotency import IdempotencyMiddleware
from ar_api.middleware.read_model import ReadModelMiddleware
from ar_api.middleware.security_headers import SecurityHeadersMiddleware
from ar_api.middleware.stack import AuthenticateMiddleware, CsrfMiddleware, RateLimitMiddleware
from ar_api.ratelimit import MemoryTokenBucket, ValkeyTokenBucket
from ar_api.routers.access import router as access_router
from ar_api.routers.agents import router as agents_router
from ar_api.routers.api_keys import router as api_keys_router
from ar_api.routers.approvals import router as approvals_router
from ar_api.routers.audit import router as audit_router
from ar_api.routers.builder import router as builder_router
from ar_api.routers.bundles import router as bundles_router
from ar_api.routers.channels import router as channels_router
from ar_api.routers.connections import router as connections_router
from ar_api.routers.connectors import router as connectors_router
from ar_api.routers.content_packs import router as packs_router
from ar_api.routers.credential_providers import router as providers_router
from ar_api.routers.data_connections import router as data_connections_router
from ar_api.routers.documents import router as documents_router
from ar_api.routers.domains import router as domains_router
from ar_api.routers.eval_runs import router as eval_runs_router
from ar_api.routers.eval_suites import router as eval_suites_router
from ar_api.routers.exposure import router as exposure_router
from ar_api.routers.feedback import router as feedback_router
from ar_api.routers.groups import router as groups_router
from ar_api.routers.identity_providers import router as idp_router
from ar_api.routers.invitations import router as invitations_router
from ar_api.routers.knowledge import router as knowledge_router
from ar_api.routers.m2 import router as m2_router
from ar_api.routers.me import router as me_router
from ar_api.routers.memory import router as memory_router
from ar_api.routers.meta import router as meta_router
from ar_api.routers.notifications import router as notifications_router
from ar_api.routers.observability import router as observability_router
from ar_api.routers.opa_bundle import router as opa_bundle_router
from ar_api.routers.openai_compat import router as openai_router
from ar_api.routers.platform_health import router as platform_health_router
from ar_api.routers.platform_plans import router as plans_router
from ar_api.routers.platform_tenants import router as platform_router
from ar_api.routers.platform_usage import router as platform_usage_router
from ar_api.routers.policies import router as policies_router
from ar_api.routers.quotas import router as quotas_router
from ar_api.routers.reviews import router as reviews_router
from ar_api.routers.roles import router as roles_router
from ar_api.routers.routines import router as routines_router
from ar_api.routers.sandboxes import router as sandboxes_router
from ar_api.routers.scim import router as scim_router
from ar_api.routers.scim_tokens import router as scim_tokens_router
from ar_api.routers.secrets import router as secrets_router
from ar_api.routers.service_accounts import router as service_accounts_router
from ar_api.routers.service_connections import router as service_connections_router
from ar_api.routers.skills import router as skills_router
from ar_api.routers.sod import router as sod_router
from ar_api.routers.standing_approvals import router as standing_router
from ar_api.routers.support_access import router as support_router
from ar_api.routers.teams import router as teams_router
from ar_api.routers.tenant import router as tenant_router
from ar_api.routers.tool_imports import router as tool_imports_router
from ar_api.routers.tool_servers import router as tool_servers_router
from ar_api.routers.tools import router as tools_router
from ar_api.routers.usage import router as usage_router
from ar_api.routers.users import router as users_router
from ar_api.routers.webhooks import router as webhooks_router
from ar_api.routers.widget import router as widget_router
from ar_api.secrets_runtime import MemorySecretApi
from ar_api.state import AuditApi, NotificationApi, PlatformApi, WebhookApi
from ar_common.host_ports import listen_port
from ar_common.settings import (
    BaseServiceSettings,
    EnvName,
    fake_models_allowed,
    files_scanner_name,
    loopback_allowed,
    unisolated_sandbox_allowed,
)
from ar_common.web import create_app
from ar_domain.audit.service import install_platform_hook
from ar_domain.chat.service import ChatBehaviour
from ar_domain.db.context import Principal
from ar_domain.files.logic import UPLOAD_BODY_LIMIT
from ar_domain.readmodel.boot import build_product_store
from ar_domain.readmodel.model import RepositoryReadModel

if TYPE_CHECKING:
    from typing import Any

LISTEN_PORT = 8000


class Settings(BaseServiceSettings):
    """API process settings. Names match the environment catalogue."""

    service_name: str = "api"
    public_url: str = "http://localhost:3000"
    # Empty follows the environment: password in dev and ci, OIDC everywhere else.
    auth_mode: str = ""
    password_login: bool = False
    password_mfa: bool = False
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: SecretStr = SecretStr("")
    oidc_audience: str = "ar-api"
    oidc_jwks_url: str = ""
    oidc_redirect_url: str = ""
    oidc_require_mfa: bool = True
    oidc_mfa_amr: str = "mfa,otp,hwk,pop"
    oidc_mfa_acr: str = "mfa,otp"
    login_max_attempts: int = 10
    login_lockout_s: int = 300
    session_encryption_key: SecretStr = SecretStr("")
    session_ttl_s: int = 43_200
    session_max_age_s: int = 604_800
    step_up_ttl_s: int = 600
    opa_url: str = ""
    opa_timeout_ms: int = 200
    opa_bundle_token: SecretStr = SecretStr("")
    secrets_backend: str = "db_encrypted"
    db_encryption_keys: SecretStr = SecretStr("")
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
        if kind == "guest":
            from ar_domain.identity.guests import GuestBook  # noqa: PLC0415

            guest_store = app.state.chat
            if isinstance(guest_store, RepositoryReadModel):
                return None
            guest = GuestBook(guest_store).principal_for(value)
            tenant_id = guest.get("tenant_id") if isinstance(guest, dict) else None
            if not isinstance(guest, dict) or not isinstance(tenant_id, uuid.UUID):
                return None
            guest_id = guest.get("id")
            return Principal(
                kind="guest",
                id=str(guest_id),
                tenant_id=tenant_id,
                permissions=frozenset(),
                auth_method="session",
                email=str(guest.get("email") or ""),
                display_name=str(guest.get("display_name") or "Guest"),
                session_id=value,
            )
        if kind not in {"session", "widget"}:
            return None
        sessions = app.state.widget_sessions if kind == "widget" else app.state.sessions
        data = await sessions.get(value)
        if data is None:
            return None
        email = data.email
        display_name = data.display_name or email
        permissions = frozenset(data.permissions)
        roles = frozenset(data.roles)
        from ar_domain.packs.registry import permissions_for  # noqa: PLC0415

        product = await _product_view(app, data.tenant_id)
        permissions = permissions | permissions_for(product, data.tenant_id, roles)
        from ar_domain.identity.tenant_settings import permissions_for_features  # noqa: PLC0415

        permissions = permissions_for_features(product, data.tenant_id, permissions)
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
            step_up_at=data.step_up_at,
        )

    return load


async def _product_view(app: FastAPI, tenant_id: uuid.UUID) -> ChatBehaviour:
    """The store a session is read from. Production loads that tenant and drops it."""
    chat = app.state.chat
    if isinstance(chat, RepositoryReadModel):
        async with chat.open(tenant_id) as unit:
            if isinstance(unit, ChatBehaviour):
                return unit
            raise RuntimeError("read model did not open a unit")
    if isinstance(chat, ChatBehaviour):
        return chat
    raise RuntimeError("api has no product store")


def _configure_chat(chat: Any, settings: Settings) -> None:
    """Pack trust follows the environment. Dev and CI accept unsigned packs and fake models."""
    chat.fake_models_allowed = fake_models_allowed(settings.env)
    from ar_domain.tools.gateway_client import configure_gateway  # noqa: PLC0415

    configure_gateway(chat, env=str(settings.env.value))
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


def _configure_sandbox(chat: Any, settings: Settings) -> None:
    """Register the docker launcher so a tool call starts a container in this process.

    Opt-in: ``AR_SANDBOX_IMAGE`` names the local ``ar-sandbox`` image. The in-process docker
    launcher is the development and CI path (spec 12 §4.2) and runs without kernel isolation,
    so it is registered only when the install allows an unisolated sandbox. With no image set
    the computer tools run on the dev host, as before.
    """
    image = os.environ.get("AR_SANDBOX_IMAGE", "").strip()
    if not image or not unisolated_sandbox_allowed(settings):
        return
    from ar_common.sandbox_docker import DockerSandboxLauncher  # noqa: PLC0415

    network = os.environ.get("AR_SANDBOX_DOCKER_NETWORK", "").strip() or None
    chat.sandbox_launcher = DockerSandboxLauncher(image, network=network)


def _configure_policy(chat: Any, settings: Settings) -> None:
    """An empty OPA URL keeps decisions in process (OQ-36).

    Pytest loads ``.env``. A developer ``AR_OPA_URL`` in that file points unit
    tests at a live bundle and makes policy tests fail in an order-dependent
    way. An explicit environment variable still wins.
    """
    url = settings.opa_url
    if os.environ.get("PYTEST_CURRENT_TEST") and "AR_OPA_URL" not in os.environ:
        url = ""
    chat.opa_url = url
    chat.opa_timeout_ms = settings.opa_timeout_ms


def create_application() -> FastAPI:
    """Build the ASGI app. ``/healthz`` does not connect. ``/readyz`` does."""
    from ar_api.readiness import api_readiness  # noqa: PLC0415

    settings = Settings()
    from ar_api.auth.mode import assert_auth_mode  # noqa: PLC0415

    assert_auth_mode(settings)
    docs = None if settings.env is EnvName.PROD else "/api/docs"
    inner: list[tuple[type, dict[str, object]]] = [
        (DurableMiddleware, {}),
        (AuthenticateMiddleware, {}),
        (ReadModelMiddleware, {}),
        (CsrfMiddleware, {}),
        (RateLimitMiddleware, {}),
        (IdempotencyMiddleware, {}),
        (SecurityHeadersMiddleware, {}),
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
            platform_router,
            platform_health_router,
            platform_usage_router,
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
            service_connections_router,
            tool_imports_router,
            data_connections_router,
            documents_router,
            policies_router,
            approvals_router,
            standing_router,
            reviews_router,
            sod_router,
            opa_bundle_router,
            sandboxes_router,
            knowledge_router,
            connectors_router,
            memory_router,
            skills_router,
            routines_router,
            quotas_router,
            usage_router,
            observability_router,
            eval_suites_router,
            eval_runs_router,
            feedback_router,
            channels_router,
            openai_router,
            exposure_router,
            widget_router,
            access_router,
        ],
        inner_middleware=inner,
        docs_url=docs,
        camel_json=True,
        readiness_checks=api_readiness(settings),
        # A route that takes a file accepts the upload cap, not the JSON body limit.
        body_limits={
            "/api/v1/files:upload": UPLOAD_BODY_LIMIT,
            "/api/v1/library-documents": UPLOAD_BODY_LIMIT,
            "/v1/agents/{slug}/files": UPLOAD_BODY_LIMIT,
        },
    )
    key = session_key_bytes(
        settings.session_encryption_key.get_secret_value(),
        settings.cursor_secret.get_secret_value(),
        prod=settings.env is EnvName.PROD,
    )
    app.state.resolve_principal = _resolve_principal
    from ar_api.auth.credentials import credential_loader  # noqa: PLC0415

    app.state.credential_loader = credential_loader(_session_loader(app), app)
    app.state.chat = build_product_store(
        settings,
        allow_loopback=loopback_allowed(settings),
        scanner=files_scanner_name(settings),
        # Read when the store seeds itself, so it is passed here and not set afterwards.
        fake_models_allowed=fake_models_allowed(settings.env),
    )
    _configure_chat(app.state.chat, settings)
    _configure_policy(app.state.chat, settings)
    _configure_sandbox(app.state.chat, settings)
    # Tool calls can run in this process. The engine that masks their results is built
    # now, on its own thread, not in the first call.
    from ar_domain.pii.analyzer import warm_up  # noqa: PLC0415

    warm_up()
    app.state.chat.model_gateway_url = settings.model_gateway_url
    from ar_api.plugins import attach_packs  # noqa: PLC0415

    attach_packs(app)
    packs_dir = os.environ.get("AR_PACKS_DIR", "")
    if packs_dir:
        from pathlib import Path  # noqa: PLC0415

        from ar_domain.packs.loader import load_pack_tree  # noqa: PLC0415

        load_pack_tree(
            app,
            Path(packs_dir),
            require_signature=os.environ.get("AR_PACK_SIGNATURE_REQUIRED") == "1",
        )
    app.state.allow_test_auth = False
    # Durable, shared rate limiting in real environments; process-local for dev/ci/tests.
    app.state.rate_limiter = (
        MemoryTokenBucket()
        if settings.env in {EnvName.DEV, EnvName.CI}
        else ValkeyTokenBucket(settings.valkey_url)
    )
    app.state.rate_limit = 600
    from ar_api.process import install_process_state  # noqa: PLC0415

    install_process_state(app, settings, key)
    app.state.identity_override = None
    # Identity is read from the database. Test setup may plug in another source here.
    app.state.identity_provider = None
    app.state.secret_api = MemorySecretApi()
    app.state.audit_api = AuditApi()
    app.state.platform = PlatformApi()
    app.state.notifications = NotificationApi()
    app.state.webhooks = WebhookApi()
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
