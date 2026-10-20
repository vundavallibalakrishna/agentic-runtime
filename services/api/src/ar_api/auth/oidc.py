"""OIDC login helpers. Spec: docs/03-specs/01-api-bff.md §3."""

import base64
import hashlib
import secrets
from urllib.parse import urlencode, urlparse


def new_pkce() -> tuple[str, str]:
    """Return ``(verifier, S256 challenge)``."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def safe_return_to(value: str | None) -> str:
    """Reject absolute return URLs. Default is ``/``."""
    if value is None or value == "" or not value.startswith("/") or value.startswith("//"):
        return "/"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return "/"
    return value


def authorize_url(
    *,
    issuer: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    challenge: str,
    tenant: str | None = None,
    idp: str | None = None,
) -> str:
    """Keycloak authorization endpoint with PKCE."""
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "openid profile email offline_access organization",
        "state": state,
        "nonce": nonce,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if tenant:
        query["organization"] = tenant
    if idp:
        query["kc_idp_hint"] = idp
    base = issuer.rstrip("/") + "/protocol/openid-connect/auth"
    return base + "?" + urlencode(query)
