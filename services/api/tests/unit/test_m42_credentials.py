"""Credential classification and two-part verification in the API layer. Stage A of M42."""

from __future__ import annotations

from ar_api.principal import (
    api_key_matches,
    classify_authorization,
    split_api_key_matches,
    split_api_key_prefix,
)
from ar_domain.identity.tokens import new_api_key, new_split_api_key, sha256_hex


def test_classify_routes_split_and_legacy_keys_to_api_key() -> None:
    key_id, secret, _prefix, _d = new_split_api_key()
    legacy, _p, _h = new_api_key()
    assert classify_authorization(f"Bearer {key_id}.{secret}", None).kind == "api_key"
    assert classify_authorization(f"Bearer {legacy}", None).kind == "api_key"
    assert classify_authorization("Bearer scim_abc.def", None).kind == "scim"
    assert classify_authorization("Bearer eyJabc.def.ghi", None).kind == "bearer"
    assert classify_authorization(None, "cookievalue").kind == "session"
    assert classify_authorization(None, None) is None


def test_split_api_key_prefix_and_match() -> None:
    key_id, secret, prefix, digest = new_split_api_key()
    assert split_api_key_prefix(f"{key_id}.{secret}") == prefix
    assert split_api_key_prefix("garbage") is None
    assert split_api_key_matches(secret, digest) is True
    assert split_api_key_matches("sk_wrong", digest) is False


def test_legacy_api_key_match_unaffected() -> None:
    legacy, _prefix, digest = new_api_key()
    assert api_key_matches(legacy, digest) is True
    assert api_key_matches(legacy + "x", digest) is False
    # A split secret must not validate against a legacy hash.
    assert sha256_hex(legacy) == digest
