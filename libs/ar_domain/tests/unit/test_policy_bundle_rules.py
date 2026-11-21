"""The bundle the API serves to OPA always holds the real decision rules."""

import io
import tarfile
from pathlib import Path

import pytest

from ar_domain.policy import bundle


class _Store:
    def __init__(self) -> None:
        self.policies: dict[object, dict[str, object]] = {}
        self.tenant_settings: dict[object, dict[str, object]] = {}


def _members(raw: bytes) -> dict[str, bytes]:
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        return {
            member.name: archive.extractfile(member).read()  # type: ignore[union-attr]
            for member in archive.getmembers()
        }


def test_bundle_holds_the_decision_rules() -> None:
    raw, _etag = bundle.build_bundle(_Store())
    files = _members(raw)
    assert b"decision := combine(" in files["ar/policy.rego"]
    assert b"package ar.jsonpath" in files["ar/jsonpath.rego"]


def test_packaged_rules_are_read_before_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "policy.rego").write_bytes(b"package ar.policy\n# packaged\n")
    monkeypatch.setattr(bundle, "_PACKAGED", tmp_path)
    assert bundle._read("policy.rego").endswith(b"# packaged\n")
    assert b"package ar.jsonpath" in bundle._read("jsonpath.rego")


def test_missing_rules_fail_instead_of_serving_an_empty_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bundle, "_PACKAGED", tmp_path / "none")
    monkeypatch.setattr(bundle, "_CHECKOUT", tmp_path / "none")
    with pytest.raises(FileNotFoundError, match=r"policy\.rego is missing"):
        bundle.build_bundle(_Store())
