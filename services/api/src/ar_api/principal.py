"""Principal construction. Spec: docs/03-specs/01-api-bff.md §5."""

import hashlib
import uuid  # noqa: TC003
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003

from ar_domain.db.context import Principal
from ar_domain.identity.tokens import constant_time_equal, sha256_hex


@dataclass(frozen=True, slots=True)
class PresentedCredential:
    """A credential extracted from the request, before it is resolved."""

    kind: str
    value: str


def classify_authorization(header: str | None, cookie: str | None) -> PresentedCredential | None:
    """Prefer ``Authorization`` over the session cookie."""
    if header:
        scheme, _, token = header.partition(" ")
        if scheme.lower() == "bearer" and token:
            if token.startswith("ark_"):
                return PresentedCredential("api_key", token)
            if token.startswith("scim_"):
                return PresentedCredential("scim", token)
            if token.startswith("eyJ"):
                return PresentedCredential("bearer", token)
        return None
    if cookie:
        return PresentedCredential("session", cookie)
    return None


def content_hidden(request: object) -> None:
    """Metadata support access is a 404 on content routes."""
    from ar_api.actors import principal_of  # noqa: PLC0415
    from ar_common.errors import NotFoundError  # noqa: PLC0415

    principal = principal_of(request)  # type: ignore[arg-type]
    if not principal.can_read_content():
        raise NotFoundError()


def api_key_prefix(token: str) -> str:
    """The 12 hex characters after ``ark_``."""
    body = token.removeprefix("ark_")
    return body[:12]


def api_key_matches(token: str, secret_hash: str) -> bool:
    return constant_time_equal(sha256_hex(token), secret_hash)


def principal_from_user(
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    email: str,
    display_name: str,
    permissions: frozenset[str],
    team_permissions: frozenset[tuple[uuid.UUID, str]],
    roles: frozenset[str],
    auth_method: str,
    tenant_status: str = "active",
    user_status: str = "active",
    scopes: frozenset[str] = frozenset(),
    session_id: str | None = None,
    csrf_token: str | None = None,
    step_up_at: datetime | None = None,
    api_key_id: uuid.UUID | None = None,
) -> Principal:
    """Build a user or API-key principal."""
    method = (
        auth_method if auth_method in {"session", "bearer", "api_key", "scim", "system"} else "none"
    )
    return Principal(
        kind="user",
        id=str(user_id),
        tenant_id=tenant_id,
        permissions=permissions,
        team_permissions=team_permissions,
        scopes=scopes,
        auth_method=method,  # type: ignore[arg-type]
        email=email,
        display_name=display_name,
        session_id=session_id,
        csrf_token=csrf_token,
        step_up_at=step_up_at,
        tenant_status=tenant_status,
        user_status=user_status,
        api_key_id=api_key_id,
        roles=roles,
    )


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()
