"""Self-serve signup. Spec: docs/03-specs/02-identity-tenancy.md §4."""

from fastapi import APIRouter, Request

from ar_api.deps import expose
from ar_common.errors import NotFoundError
from ar_contracts.json_api import ApiModel

router = APIRouter()


class SignupBody(ApiModel):
    slug: str
    name: str
    email: str


@router.post("/api/v1/signup")
@expose(public=True, permission=None)
async def signup(body: SignupBody, request: Request) -> dict[str, str]:
    if not bool(getattr(request.app.state.settings, "saas_self_signup", False)):
        raise NotFoundError("signup is disabled")
    if request.app.state.settings.deployment_mode.value != "saas":
        raise NotFoundError("signup is disabled")
    tenant_id = await request.app.state.signup(body.slug, body.name, body.email)
    return {"tenant_id": tenant_id, "status": "provisioning"}
