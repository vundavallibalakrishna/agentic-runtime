from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypeVar, cast

from attrs import define as _attrs_define

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.upgrade_body_manifest import UpgradeBodyManifest


T = TypeVar("T", bound="UpgradeBody")


@_attrs_define
class UpgradeBody:
    """
    Attributes:
        manifest (UpgradeBodyManifest):
        signature (None | str | Unset):
        key_id (None | str | Unset):
        accept_conflicts (bool | Unset):  Default: False.
    """

    manifest: UpgradeBodyManifest
    signature: str | Unset | None = UNSET
    key_id: str | Unset | None = UNSET
    accept_conflicts: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        manifest = self.manifest.to_dict()

        signature: str | Unset | None
        if isinstance(self.signature, Unset):
            signature = UNSET
        else:
            signature = self.signature

        key_id: str | Unset | None
        if isinstance(self.key_id, Unset):
            key_id = UNSET
        else:
            key_id = self.key_id

        accept_conflicts = self.accept_conflicts

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "manifest": manifest,
            }
        )
        if signature is not UNSET:
            field_dict["signature"] = signature
        if key_id is not UNSET:
            field_dict["keyId"] = key_id
        if accept_conflicts is not UNSET:
            field_dict["acceptConflicts"] = accept_conflicts

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.upgrade_body_manifest import UpgradeBodyManifest  # noqa: PLC0415

        d = dict(src_dict)
        manifest = UpgradeBodyManifest.from_dict(d.pop("manifest"))

        def _parse_signature(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast("None | str | Unset", data)

        signature = _parse_signature(d.pop("signature", UNSET))

        def _parse_key_id(data: object) -> str | Unset | None:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast("None | str | Unset", data)

        key_id = _parse_key_id(d.pop("keyId", UNSET))

        accept_conflicts = d.pop("acceptConflicts", UNSET)

        upgrade_body = cls(
            manifest=manifest,
            signature=signature,
            key_id=key_id,
            accept_conflicts=accept_conflicts,
        )

        return upgrade_body
