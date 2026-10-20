"""Helpers that mint internal JWTs and fake web sessions."""

from typing import TYPE_CHECKING

from ar_common.internal_auth import ALLOWED_CALLERS
from ar_common.internal_jwt import generate_keypair, sign_internal_jwt

if TYPE_CHECKING:
    import uuid


def mint_internal_jwt(
    *,
    iss: str,
    aud: str,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    ttl_s: int = 60,
) -> tuple[str, dict[str, str]]:
    """Return a signed token and a one-key JWKS (kid → PEM)."""
    private_pem, public_pem = generate_keypair()
    scopes = sorted(ALLOWED_CALLERS[aud][iss])
    token = sign_internal_jwt(
        private_pem=private_pem,
        kid="test",
        iss=iss,
        aud=aud,
        scopes=scopes,
        tenant_id=tenant_id,
        user_id=user_id,
        ttl_s=ttl_s,
    )
    return token, {"test": public_pem}


def fake_session(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, str]:
    """Return the session fields later milestones store in Valkey."""
    return {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "csrf_token": "dev-csrf",
    }
