"""Review links follow the install's sign-in mode, and the decision checks Origin.

Label: unit
"""

from __future__ import annotations

from ar_api.auth.mode import AuthMode, resolve_auth_mode
from ar_api.main import Settings
from ar_api.middleware.stack import _review_decide
from ar_common.settings import EnvName


def test_production_defaults_to_oidc_so_a_review_token_is_not_enough() -> None:
    settings = Settings(_env_file=None, env=EnvName.PROD, auth_mode="")
    assert resolve_auth_mode(settings) is AuthMode.OIDC
    dev = Settings(_env_file=None, env=EnvName.DEV, auth_mode="")
    assert resolve_auth_mode(dev) is AuthMode.PASSWORD


def test_only_the_review_decision_stays_on_the_csrf_check() -> None:
    assert _review_decide("/api/v1/review/abc:decide")
    assert not _review_decide("/api/v1/review/abc")
    assert not _review_decide("/api/v1/reviews")
    assert not _review_decide("/api/v1/auth/login")
