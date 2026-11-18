"""OPA bundle. Spec: docs/03-specs/09-policy-approvals.md §3.2.

OPA sends ``Authorization: Bearer`` with ``AR_OPA_BUNDLE_TOKEN``. The route
does not open a chat read unit: a bundle is every tenant's active rules, and
OPA has no person and no tenant. An empty token is refused outside dev and ci.
"""

import hashlib
import hmac

from fastapi import APIRouter, Request
from fastapi.responses import Response

from ar_api.deps import expose
from ar_common.errors import UnauthenticatedError
from ar_common.settings import EnvName
from ar_domain.policy.bundle import build_bundle, bundle_from_engine
from ar_domain.readmodel.model import RepositoryReadModel

router = APIRouter()
_DEV = frozenset({EnvName.DEV, EnvName.CI})


def _configured_token(settings: object) -> str:
    raw = getattr(settings, "opa_bundle_token", "")
    getter = getattr(raw, "get_secret_value", None)
    if callable(getter):
        return str(getter() or "")
    return str(raw or "")


def _presented_token(header: str) -> str:
    scheme, _, token = header.strip().partition(" ")
    if scheme.lower() != "bearer" or not token:
        return ""
    return token


def _same_token(presented: str, expected: str) -> bool:
    """Compare two tokens in constant time, including when the lengths differ."""
    return hmac.compare_digest(
        hashlib.sha256(presented.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )


def _authorised(request: Request) -> None:
    settings = request.app.state.settings
    expected = _configured_token(settings)
    env = getattr(settings, "env", EnvName.DEV)
    if not expected:
        if env not in _DEV:
            raise UnauthenticatedError()
        return
    presented = _presented_token(request.headers.get("authorization", ""))
    if not _same_token(presented, expected):
        raise UnauthenticatedError()


async def current_bundle(source: object) -> tuple[bytes, str]:
    """Bytes and ETag for the process that is serving this request."""
    if isinstance(source, RepositoryReadModel):
        engine = await source.engine_for()
        return await bundle_from_engine(engine)
    return build_bundle(source)


@router.get("/internal/v1/opa/bundles/ar.tar.gz")
@expose(public=True, permission=None)
async def opa_bundle(request: Request) -> Response:
    _authorised(request)
    raw, etag = await current_bundle(request.app.state.chat)
    quoted = f'"{etag}"'
    if request.headers.get("if-none-match") in {etag, quoted}:
        return Response(status_code=304, headers={"ETag": quoted})
    return Response(content=raw, media_type="application/gzip", headers={"ETag": quoted})
