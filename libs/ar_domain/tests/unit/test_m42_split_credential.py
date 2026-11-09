"""Two-part (key id + secret) API credential helpers. Stage A of M42.

Spec: docs/06-security/authn-authz.md §2, docs/05-contracts/api-conventions.md §2.
"""

from __future__ import annotations

from ar_domain.identity.tokens import (
    constant_time_equal,
    new_api_key,
    new_split_api_key,
    rotate_legacy_secret,
    rotate_split_secret,
    sha256_hex,
    split_credential,
)


def test_new_split_api_key_shape_and_hash() -> None:
    key_id, secret, prefix, digest = new_split_api_key()
    assert key_id == f"ak_{prefix}"
    assert len(prefix) == 12
    assert secret.startswith("sk_")
    # Only the secret is hashed; the key id/prefix are not part of the hash.
    assert sha256_hex(secret) == digest
    assert sha256_hex(f"{key_id}.{secret}") != digest


def test_split_credential_parses_well_formed_token() -> None:
    key_id, secret, prefix, _digest = new_split_api_key()
    assert split_credential(f"{key_id}.{secret}") == (prefix, secret)


def test_split_credential_rejects_malformed() -> None:
    _id, secret, prefix, _d = new_split_api_key()
    assert split_credential(f"ak_{prefix}") is None  # no secret part
    assert split_credential(f"ark_{prefix}.{secret}") is None  # wrong id scheme
    assert split_credential(f"ak_{prefix}.nope") is None  # secret not sk_
    assert split_credential("ak_short.sk_x") is None  # prefix wrong length
    assert split_credential("garbage") is None
    # partition on the first dot: a secret may itself contain dots.
    assert split_credential(f"ak_{prefix}.{secret}.extra") == (prefix, f"{secret}.extra")


def test_split_verification_matches_only_the_right_secret() -> None:
    _id, secret, _prefix, digest = new_split_api_key()
    assert constant_time_equal(sha256_hex(secret), digest)
    assert not constant_time_equal(sha256_hex("sk_wrong"), digest)


def test_rotate_split_secret_changes_the_secret() -> None:
    _id, secret, _prefix, digest = new_split_api_key()
    new_secret, new_digest = rotate_split_secret()
    assert new_secret.startswith("sk_") and new_secret != secret
    assert new_digest == sha256_hex(new_secret) != digest


def test_rotate_legacy_secret_keeps_prefix() -> None:
    full, prefix, _digest = new_api_key()
    rotated, new_digest = rotate_legacy_secret(prefix)
    assert rotated.startswith(f"ark_{prefix}") and rotated != full
    assert new_digest == sha256_hex(rotated)


def test_legacy_key_still_verifies() -> None:
    full, _prefix, digest = new_api_key()
    assert full.startswith("ark_")
    assert constant_time_equal(sha256_hex(full), digest)
