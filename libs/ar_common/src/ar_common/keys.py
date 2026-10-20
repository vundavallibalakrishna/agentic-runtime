"""Valkey key builders. Every key contains a tenant id or a UUID.

Spec: docs/02-architecture/tenancy-isolation.md §5.
"""

import uuid  # noqa: TC003 - tests call get_type_hints, which evaluates annotations


def session_key(session_id: uuid.UUID) -> str:
    """Server-side session hash."""
    return f"ar:sess:{session_id}"


def login_state_key(state_id: uuid.UUID) -> str:
    """OIDC login transaction."""
    return f"ar:login:{state_id}"


def jti_key(jti: uuid.UUID) -> str:
    """Internal-JWT replay cache entry."""
    return f"ar:jti:{jti}"


def run_events_key(tenant_id: uuid.UUID, run_id: uuid.UUID) -> str:
    """Live run event stream."""
    return f"ar:{{{tenant_id}}}:run:{run_id}:events"


def run_seq_key(tenant_id: uuid.UUID, run_id: uuid.UUID) -> str:
    """Monotonic sequence counter for a run."""
    return f"ar:{{{tenant_id}}}:run:{run_id}:seq"


def rate_limit_key(tenant_id: uuid.UUID, principal_id: uuid.UUID, bucket: str) -> str:
    """Token-bucket counter for a principal."""
    return f"ar:{{{tenant_id}}}:rl:{principal_id}:{bucket}"


def idempotency_key(tenant_id: uuid.UUID, key_id: uuid.UUID) -> str:
    """Stored response for an ``Idempotency-Key``."""
    return f"ar:{{{tenant_id}}}:idem:{key_id}"


def channel_invalidation_key(tenant_id: uuid.UUID, integration_id: uuid.UUID) -> str:
    """Pub/sub key that tells ``channels`` to reload one integration."""
    return f"ar:{{{tenant_id}}}:invalidate:channel_integration:{integration_id}"
