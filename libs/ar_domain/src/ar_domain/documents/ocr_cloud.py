"""Cloud OCR through a named secret. A missing secret stays not_live.

The secret value is an endpoint URL and is not written to logs. Proof is
``contract`` when a transport answers a recorded body, and ``unit`` when no
secret is configured. A live label is only for certify_live on a machine that
holds the provider key.
"""

from __future__ import annotations

from typing import Any  # noqa: TC003

import httpx

from ar_common.offload import blocking
from ar_domain.tools.named_secrets import read_named_secret

_SECRET = {
    "google_document_ai": "ocr_google",
    "aws_textract": "ocr_aws",
    "azure_document_intelligence": "ocr_azure",
}


def read_cloud(
    store: Any,
    tenant_id: object,
    engine: str,
    data: bytes,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, object] | None:
    """Read a page when the tenant named a secret. None when the engine is unwired."""
    secret_name = _SECRET.get(engine)
    if secret_name is None:
        return None
    endpoint = read_named_secret(store, tenant_id, secret_name) or ""
    if not endpoint and transport is None:
        return None
    if not endpoint:
        endpoint = "https://ocr.invalid/process"
    headers = {"content-type": "application/octet-stream"}
    client = httpx.Client(transport=transport or httpx.HTTPTransport(), timeout=30)
    try:
        post = client.post
        response = blocking(post, endpoint, content=data, headers=headers)
    except httpx.HTTPError:
        return None
    finally:
        client.close()
    if response.status_code >= 400:
        return None
    body = response.json()
    text = ""
    if isinstance(body, dict):
        text = str(body.get("text") or "")
    if not text:
        return None
    return {
        "text": text,
        "structured": {
            "kind": "ocr",
            "engine": engine,
            "proof": "contract",
            "status": "extracted",
            "secret_name": secret_name,
        },
        "is_error": False,
    }
