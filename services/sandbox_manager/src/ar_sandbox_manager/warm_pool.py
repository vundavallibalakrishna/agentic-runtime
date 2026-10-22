"""Warm pool claim. Spec: docs/03-specs/12-sandbox-manager.md §4."""

from ar_common.sandboxkit import parse_warm_pool


def claim(spec: str, template: str, available: dict[str, int]) -> str | None:
    """Take one warm sandbox for ``template`` when the pool has one."""
    sizes = parse_warm_pool(spec)
    if sizes.get(template, 0) <= 0:
        return None
    count = available.get(template, 0)
    if count <= 0:
        return None
    available[template] = count - 1
    return template
