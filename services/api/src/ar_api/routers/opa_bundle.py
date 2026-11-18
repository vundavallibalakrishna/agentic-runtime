"""OPA bundle. Spec: docs/03-specs/09-policy-approvals.md §3.2.

OPA is an internal caller. The route is authenticated by ``X-AR-Internal``
in the service middleware. It does not open a chat read unit: a bundle is
every tenant's active rules, and OPA has no person and no tenant.
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ar_api.deps import expose
from ar_domain.policy.bundle import build_bundle, bundle_from_engine
from ar_domain.readmodel.model import RepositoryReadModel

router = APIRouter()


async def current_bundle(source: object) -> tuple[bytes, str]:
    """Bytes and ETag for the process that is serving this request."""
    if isinstance(source, RepositoryReadModel):
        engine = await source.engine_for()
        return await bundle_from_engine(engine)
    return build_bundle(source)


@router.get("/internal/v1/opa/bundles/ar.tar.gz")
@expose(public=True, permission=None)
async def opa_bundle(request: Request) -> Response:
    raw, etag = await current_bundle(request.app.state.chat)
    quoted = f'"{etag}"'
    if request.headers.get("if-none-match") in {etag, quoted}:
        return Response(status_code=304, headers={"ETag": quoted})
    return Response(content=raw, media_type="application/gzip", headers={"ETag": quoted})
