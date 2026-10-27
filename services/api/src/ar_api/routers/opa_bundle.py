"""OPA bundle. Spec: docs/03-specs/09-policy-approvals.md §3.2."""

import hmac

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import SecretStr

from ar_api.deps import expose
from ar_api.routers.tooling import chat
from ar_common.errors import UnauthenticatedError
from ar_domain.policy.bundle import build_bundle

router = APIRouter()


@router.get("/internal/v1/opa/bundles/ar.tar.gz")
@expose(public=True, permission=None)
async def opa_bundle(request: Request) -> Response:
    settings = request.app.state.settings
    configured = getattr(settings, "opa_bundle_token", "")
    expected = (
        configured.get_secret_value()
        if isinstance(configured, SecretStr)
        else str(configured or "")
    )
    if expected:
        header = request.headers.get("authorization", "")
        if not hmac.compare_digest(header.encode(), f"Bearer {expected}".encode()):
            raise UnauthenticatedError()
    store = chat(request)
    raw = store.opa_bundle
    etag = store.opa_etag
    if not raw:
        raw, etag = build_bundle(store)
        store.opa_bundle = raw
        store.opa_etag = etag
    quoted = f'"{etag}"'
    if request.headers.get("if-none-match") in {etag, quoted}:
        return Response(status_code=304, headers={"ETag": quoted})
    return Response(content=raw, media_type="application/gzip", headers={"ETag": quoted})
