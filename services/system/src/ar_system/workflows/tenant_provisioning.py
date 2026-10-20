"""Tenant provisioning steps. Spec: docs/03-specs/02-identity-tenancy.md §4."""

from dataclasses import dataclass, field


@dataclass
class ProvisionRequest:
    slug: str
    name: str
    plan_key: str
    owner_email: str
    tenant_id: str | None = None


@dataclass
class ProvisionState:
    tenant_id: str
    created: bool
    invited: bool
    hooks: list[str] = field(default_factory=list)


def provision_plan(
    existing_id: str | None, request: ProvisionRequest, hooks: list[str]
) -> ProvisionState:
    """Idempotent plan: an existing tenant is a no-op apart from recorded hooks."""
    if existing_id:
        return ProvisionState(
            tenant_id=existing_id, created=False, invited=False, hooks=list(hooks)
        )
    return ProvisionState(
        tenant_id=request.tenant_id or request.slug,
        created=True,
        invited=True,
        hooks=list(hooks),
    )
