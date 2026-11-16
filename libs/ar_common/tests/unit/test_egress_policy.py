"""Closed egress and explicit private hosts."""

from __future__ import annotations

import pytest

from ar_common.egress_policy import decide, decide_url


def _public(host: str) -> list[str]:
    return ["1.2.3.4"]


def _private(host: str) -> list[str]:
    return ["10.1.2.3"]


def _meta(host: str) -> list[str]:
    return ["169.254.169.254"]


@pytest.mark.unit
def test_closed_mode_refuses_a_host_that_is_not_listed() -> None:
    reason = decide("api.example", [], resolve=_public, closed=True, loopback=False)
    assert reason is not None
    assert "allow list" in reason


@pytest.mark.unit
def test_closed_mode_allows_a_listed_public_host() -> None:
    assert (
        decide("api.example", ["api.example"], resolve=_public, closed=True, loopback=False) is None
    )


@pytest.mark.unit
def test_open_mode_allows_a_public_host_without_a_list() -> None:
    assert (
        decide(
            "api.example", [], resolve=_public, closed=False, loopback=False, check_private=False
        )
        is None
    )


@pytest.mark.unit
def test_a_named_host_may_be_private_only_when_the_install_allows_it() -> None:
    blocked = decide(
        "minio.internal",
        ["minio.internal"],
        resolve=_private,
        closed=True,
        loopback=False,
        named_private=False,
    )
    assert blocked is not None
    assert "AR_EGRESS_ALLOW_NAMED_PRIVATE" in blocked
    assert (
        decide(
            "minio.internal",
            ["minio.internal"],
            resolve=_private,
            closed=True,
            loopback=False,
            named_private=True,
        )
        is None
    )


@pytest.mark.unit
def test_a_private_host_that_is_not_named_is_denied() -> None:
    reason = decide("minio.internal", [], resolve=_private, closed=False, loopback=False)
    assert reason is not None
    assert "deny list" in reason


@pytest.mark.unit
def test_a_wildcard_does_not_unlock_a_private_address() -> None:
    reason = decide(
        "minio.corp.example",
        ["*.corp.example"],
        resolve=_private,
        closed=True,
        loopback=False,
    )
    assert reason is not None


@pytest.mark.unit
def test_metadata_is_denied_even_when_named() -> None:
    reason = decide(
        "169.254.169.254",
        ["169.254.169.254"],
        resolve=_meta,
        closed=False,
        loopback=False,
    )
    assert reason is not None
    assert "metadata" in reason


@pytest.mark.unit
def test_mapped_decimal_octal_and_unspecified_addresses_stay_denied() -> None:
    for host in (
        "::ffff:169.254.169.254",
        "0.0.0.0",  # noqa: S104
        "::",
        "100.100.100.200",
        "168.63.129.16",
        "192.0.0.192",
    ):
        reason = decide(host, [host], closed=False, loopback=True, named_private=True)
        assert reason is not None, host
    for host in ("2130706433", "0177.0.0.1", "localhost", "fake-llm"):
        reason = decide(host, [host], closed=False, loopback=False)
        assert reason is not None, host
        assert "not allowed" in reason or "deny list" in reason


def test_a_star_is_not_a_match_when_closed() -> None:
    reason = decide_url(
        "https://api.example/v1",
        ["*"],
        resolve=_public,
        closed=True,
        loopback=False,
        check_private=False,
    )
    assert reason is not None
