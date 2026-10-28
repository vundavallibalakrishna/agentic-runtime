"""Platform component health. Spec: docs/03-specs/18-observability-eval.md §3."""

from fastapi import APIRouter, Request

from ar_api.deps import expose
from ar_common.errors import ForbiddenError
from ar_common.settings import DeploymentMode
from ar_domain.runs.health import component_health, default_targets

router = APIRouter()


def _allowed(request: Request) -> None:
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise ForbiddenError("platform admin required")
    if getattr(principal, "kind", "") == "platform_admin":
        return
    mode = request.app.state.settings.deployment_mode
    roles = set(getattr(principal, "roles", ()) or ())
    if mode is DeploymentMode.SINGLE_TENANT and "tenant_admin" in roles:
        return
    raise ForbiddenError("platform admin required")


@router.get("/api/v1/platform/health")
@expose(public=False, permission=None)
async def platform_health(request: Request) -> dict[str, object]:
    _allowed(request)
    components = await component_health(default_targets(request.app.state.settings))
    return {"components": components}
