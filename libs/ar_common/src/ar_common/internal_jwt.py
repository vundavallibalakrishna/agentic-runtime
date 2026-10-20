"""Internal service JWTs (EdDSA). Spec: docs/05-contracts/internal-apis.md §1."""

import base64
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from ar_common.errors import ForbiddenError, UnauthenticatedError
from ar_common.ids import new_id
from ar_common.keys import jti_key
from ar_common.time import utcnow

if TYPE_CHECKING:
    from collections.abc import Mapping

MAX_TTL_S = 60


class JtiCache(Protocol):
    """Remembers a ``jti`` until it expires. ``claim`` is false when the id was already used."""

    async def claim(self, jti: uuid.UUID, ttl_s: int) -> bool: ...


class MemoryJtiCache:
    """Process-local replay cache used by unit tests."""

    def __init__(self) -> None:
        self._seen: set[uuid.UUID] = set()

    async def claim(self, jti: uuid.UUID, ttl_s: int) -> bool:
        del ttl_s
        if jti in self._seen:
            return False
        self._seen.add(jti)
        return True


class ValkeyJtiCache:
    """Replay cache stored in Valkey."""

    def __init__(self, client: object) -> None:
        self._client = client

    async def claim(self, jti: uuid.UUID, ttl_s: int) -> bool:
        created = await self._client.set(jti_key(jti), "1", nx=True, ex=ttl_s)  # type: ignore[attr-defined]
        return bool(created)


@dataclass(frozen=True)
class InternalClaims:
    """Verified acting context carried by an internal JWT."""

    iss: str
    aud: str
    jti: uuid.UUID
    tenant_id: uuid.UUID | None
    user_id: uuid.UUID | None
    run_id: uuid.UUID | None
    agent_id: uuid.UUID | None
    scopes: frozenset[str]


def generate_keypair() -> tuple[str, str]:
    """Return ``(private_pem, public_pem)`` for a new Ed25519 key."""
    private = Ed25519PrivateKey.generate()
    private_pem = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def public_jwk(public_pem: str, kid: str) -> dict[str, str]:
    """Build an OKP JWK for an Ed25519 public key."""
    key = serialization.load_pem_public_key(public_pem.encode())
    if not isinstance(key, Ed25519PublicKey):
        raise UnauthenticatedError("Internal JWT key is not Ed25519")
    raw = key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "kty": "OKP",
        "crv": "Ed25519",
        "x": base64.urlsafe_b64encode(raw).decode().rstrip("="),
        "kid": kid,
        "use": "sig",
        "alg": "EdDSA",
    }


def sign_internal_jwt(
    *,
    private_pem: str,
    kid: str,
    iss: str,
    aud: str,
    scopes: list[str],
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    ttl_s: int = MAX_TTL_S,
) -> str:
    """Sign an internal JWT. ``ttl_s`` must be between 1 and 60 seconds."""
    if ttl_s < 1 or ttl_s > MAX_TTL_S:
        raise ForbiddenError("Internal JWT lifetime must be between 1 and 60 seconds")
    issued = int(utcnow().timestamp())
    claims: dict[str, object] = {
        "iss": iss,
        "aud": aud,
        "iat": issued,
        "exp": issued + ttl_s,
        "jti": str(new_id()),
        "tenant_id": None if tenant_id is None else str(tenant_id),
        "user_id": None if user_id is None else str(user_id),
        "scopes": scopes,
    }
    if run_id is not None:
        claims["run_id"] = str(run_id)
    if agent_id is not None:
        claims["agent_id"] = str(agent_id)
    token = jwt.encode(claims, private_pem, algorithm="EdDSA", headers={"kid": kid})
    return token if isinstance(token, str) else token.decode()


def _optional_uuid(value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    return uuid.UUID(str(value))


async def verify_internal_jwt(
    token: str,
    *,
    aud: str,
    jwks: Mapping[str, str],
    cache: JtiCache,
    allowed_callers: Mapping[str, Mapping[str, frozenset[str]]],
) -> InternalClaims:
    """Verify signature, audience, lifetime, caller and replay protection.

    ``jwks`` maps ``kid`` to a PEM public key. ``allowed_callers`` maps the
    target audience to ``{caller: required scopes}``.
    """
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Internal JWT is malformed") from exc
    kid = str(header.get("kid", ""))
    public_pem = jwks.get(kid)
    if public_pem is None:
        raise UnauthenticatedError("Internal JWT signing key is unknown")
    try:
        decoded = jwt.decode(
            token,
            public_pem,
            algorithms=["EdDSA"],
            audience=aud,
            options={"require": ["exp", "iat", "iss", "jti", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthenticatedError("Internal JWT has expired") from exc
    except jwt.InvalidAudienceError as exc:
        raise ForbiddenError("Internal JWT audience does not match") from exc
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("Internal JWT is invalid") from exc
    issued = int(decoded["iat"])
    expires = int(decoded["exp"])
    if expires - issued > MAX_TTL_S:
        raise UnauthenticatedError("Internal JWT lifetime exceeds 60 seconds")
    iss = str(decoded["iss"])
    callers = allowed_callers.get(aud, {})
    if iss not in callers:
        raise ForbiddenError("Caller is not allowed to reach this service")
    token_scopes = frozenset(str(item) for item in decoded.get("scopes", []))
    if not callers[iss] <= token_scopes:
        raise ForbiddenError("Internal JWT is missing a required scope")
    jti = uuid.UUID(str(decoded["jti"]))
    remaining = max(1, expires - int(utcnow().timestamp()))
    fresh = await cache.claim(jti, remaining)
    if not fresh:
        raise UnauthenticatedError("Internal JWT has already been used")
    return InternalClaims(
        iss=iss,
        aud=aud,
        jti=jti,
        tenant_id=_optional_uuid(decoded.get("tenant_id")),
        user_id=_optional_uuid(decoded.get("user_id")),
        run_id=_optional_uuid(decoded.get("run_id")),
        agent_id=_optional_uuid(decoded.get("agent_id")),
        scopes=token_scopes,
    )
