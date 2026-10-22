"""Compare a bundle resource with the copy already in the tenant."""

from ar_domain.agents.logic import definition_hash


def _definition(resource: dict[str, object]) -> dict[str, object]:
    spec = resource.get("spec")
    if isinstance(spec, dict):
        return {str(key): value for key, value in spec.items() if key != "resolved"}
    return {}


def resource_hash(resource: dict[str, object]) -> str:
    """Stable hash of a resource spec. Ids and clocks are not part of it."""
    return definition_hash(_definition(resource))


def classify(existing_hash: str | None, incoming_hash: str, *, dirty: bool) -> str:
    """Return create, unchanged, new_version or conflict."""
    if existing_hash is None:
        return "create"
    if existing_hash == incoming_hash:
        return "unchanged"
    if dirty:
        return "conflict"
    return "new_version"
