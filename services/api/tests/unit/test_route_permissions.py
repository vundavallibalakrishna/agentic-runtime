"""A route without a permission must be on the allowlist, with a reason."""

from ar_api.auth.route_access import ungoverned
from ar_api.main import create_application


def test_every_route_has_a_permission_or_an_allowlist_reason() -> None:
    missing = ungoverned(create_application())
    assert missing == []
