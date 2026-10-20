"""Webhook delivery decisions. Spec: docs/03-specs/20-notifications-events.md §3."""

from ar_common.http import assert_public_url
from ar_domain.events.sign import next_backoff_s, public_json_bytes, sign_body


def event_body(payload: dict[str, object]) -> bytes:
    """Webhook body. Nested keys are camelCase before the signature is computed."""
    return public_json_bytes(payload)


def prepare_delivery(
    *,
    secret: str,
    body: bytes,
    timestamp: int,
    url: str,
    allow_private: bool,
) -> tuple[str, str]:
    """Return ``(url, signature)`` after the SSRF check."""
    if not allow_private:
        assert_public_url(url)
    return url, sign_body(secret, body, timestamp)


def delivery_outcome(status_code: int, attempts: int) -> tuple[str, int | None]:
    """Return ``(status, delay seconds)``. Delay is ``None`` when the delivery is finished."""
    if 200 <= status_code < 300:
        return "succeeded", None
    if status_code == 410:
        return "dead", None
    delay = next_backoff_s(attempts)
    if delay is None:
        return "dead", None
    return "pending", delay
