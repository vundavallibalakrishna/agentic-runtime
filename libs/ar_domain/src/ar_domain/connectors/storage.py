"""S3-compatible list, get and put. Credentials stay on the client, not in the result."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.connectors.mail import host_blocked

if TYPE_CHECKING:
    from typing import Any


def _client(store: Any, *, endpoint: str, region: str, access_key: str, secret_key: str) -> Any:
    factory = getattr(store, "connector_s3", None)
    if factory is not None:
        return factory()
    import boto3  # noqa: PLC0415

    endpoint = _pinned_endpoint(endpoint)
    client = boto3.client(
        "s3",
        endpoint_url=endpoint or None,
        region_name=region or "us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    return _bound(client, endpoint)


def _pinned_endpoint(endpoint: str) -> str:
    """Keep the hostname so TLS checks it. The socket is pinned at the call."""
    from urllib.parse import urlsplit  # noqa: PLC0415

    from ar_common.egress_http import EgressDenied, approved_addresses  # noqa: PLC0415
    from ar_common.egress_policy import closed_egress  # noqa: PLC0415

    if not closed_egress():
        return endpoint
    if not endpoint:
        raise OSError("an endpoint is required when egress is closed")
    host = urlsplit(endpoint).hostname
    if not host:
        raise OSError("an endpoint is required when egress is closed")
    try:
        approved_addresses(host)
    except EgressDenied as exc:
        raise OSError(exc.reason) from exc
    return endpoint


def _bound(client: Any, endpoint: str) -> Any:
    from urllib.parse import urlsplit  # noqa: PLC0415

    from ar_common.egress_http import approved_addresses, pin_dns  # noqa: PLC0415
    from ar_common.egress_policy import closed_egress  # noqa: PLC0415

    raw_host = urlsplit(endpoint).hostname if endpoint else None
    if not closed_egress() or not raw_host:
        return client
    host = raw_host

    class _Calls:
        def __getattr__(self, name: str) -> Any:
            method = getattr(client, name)

            def call(*args: object, **kwargs: object) -> object:
                with pin_dns(host, approved_addresses(host)):
                    return method(*args, **kwargs)

            return call

    return _Calls()


def _endpoint_host(endpoint: str) -> str | None:
    if not endpoint:
        return None
    from urllib.parse import urlparse  # noqa: PLC0415

    return urlparse(endpoint).hostname


def list_objects(store: Any, settings: dict[str, str], *, prefix: str) -> dict[str, object]:
    host = _endpoint_host(settings["endpoint"])
    if host:
        problem = host_blocked(store, host)
        if problem:
            return _fail(problem)
    try:
        client = _client(store, **_auth(settings))
        response = client.list_objects_v2(Bucket=settings["bucket"], Prefix=prefix, MaxKeys=50)
    except Exception as exc:  # noqa: BLE001 — the provider error is mapped, the secret is not
        return _fail(_safe(exc))
    contents = response.get("Contents") if isinstance(response, dict) else []
    rows = (
        [
            {"key": str(item.get("Key") or ""), "size": item.get("Size")}
            for item in contents
            if isinstance(item, dict)
        ]
        if isinstance(contents, list)
        else []
    )
    return {"text": f"{len(rows)} objects.", "structured": {"objects": rows}, "is_error": False}


def get_object(store: Any, settings: dict[str, str], *, key: str) -> dict[str, object]:
    host = _endpoint_host(settings["endpoint"])
    if host:
        problem = host_blocked(store, host)
        if problem:
            return _fail(problem)
    try:
        client = _client(store, **_auth(settings))
        response = client.get_object(Bucket=settings["bucket"], Key=key)
        body = response["Body"].read()
    except Exception as exc:  # noqa: BLE001
        return _fail(_safe(exc))
    if not isinstance(body, bytes):
        body = b""
    text = body[:4000].decode("utf-8", errors="replace")
    return {
        "text": text,
        "structured": {"key": key, "text": text, "size": len(body)},
        "is_error": False,
    }


def put_object(store: Any, settings: dict[str, str], *, key: str, text: str) -> dict[str, object]:
    host = _endpoint_host(settings["endpoint"])
    if host:
        problem = host_blocked(store, host)
        if problem:
            return _fail(problem)
    payload = text.encode()
    try:
        client = _client(store, **_auth(settings))
        client.put_object(Bucket=settings["bucket"], Key=key, Body=payload)
    except Exception as exc:  # noqa: BLE001
        return _fail(_safe(exc))
    return {
        "text": f"Wrote {key}.",
        "structured": {"key": key, "size": len(payload)},
        "is_error": False,
    }


def _auth(settings: dict[str, str]) -> dict[str, str]:
    return {
        "endpoint": settings["endpoint"],
        "region": settings["region"],
        "access_key": settings["access_key"],
        "secret_key": settings["secret_key"],
    }


def _safe(exc: Exception) -> str:
    text = str(exc)
    if len(text) > 180:
        text = text[:180]
    return f"The storage service refused the call. {exc.__class__.__name__}. {text}"


def _fail(text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": "upstream_error"}
