"""Public metadata. Spec: docs/03-specs/01-api-bff.md §6."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ar_api.deps import expose
from ar_api.state import as_object
from ar_contracts import SCHEMA_MODELS

router = APIRouter()


@router.get("/api/v1/meta")
@expose(public=True, permission=None)
async def meta(request: Request) -> dict[str, object]:
    from ar_api.auth.mode import AuthMode, resolve_auth_mode  # noqa: PLC0415

    settings = request.app.state.settings
    mode = resolve_auth_mode(settings)
    if mode is AuthMode.OIDC:
        auth: dict[str, str] = {
            "login_url": "/api/v1/auth/oidc/start",
            "method": "oidc",
            "mfa": "idp",
        }
    else:
        auth = {
            "login_url": "/api/v1/auth/login",
            "method": "password",
            "mfa": "totp" if settings.password_mfa else "none",
        }
    return {
        "version": "0.1.0",
        "deployment_mode": settings.deployment_mode.value,
        "features": {},
        "auth": auth,
    }


@router.get("/api/v1/schemas/{kind}")
@expose(public=False, permission=None)
async def schema(kind: str) -> JSONResponse:
    model = SCHEMA_MODELS.get(kind)
    if model is None:
        from ar_common.errors import NotFoundError  # noqa: PLC0415

        raise NotFoundError(f"unknown schema {kind}")
    return JSONResponse(model.model_json_schema())


@router.get("/api/v1/openapi.json")
@expose(public=True, permission=None)
async def openapi_document(request: Request) -> dict[str, object]:
    if request.app.state.settings.env.value == "prod":
        from ar_api.deps import current_principal  # noqa: PLC0415

        current_principal(request)
    return as_object(request.app.openapi())
