from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define

from ..types import UNSET, Unset

T = TypeVar("T", bound="ValidateBody")


@_attrs_define
class ValidateBody:
    """
    Attributes:
        version_ref (str | Unset):  Default: 'draft'.
    """

    version_ref: str | Unset = "draft"

    def to_dict(self) -> dict[str, Any]:
        version_ref = self.version_ref

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if version_ref is not UNSET:
            field_dict["versionRef"] = version_ref

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        version_ref = d.pop("versionRef", UNSET)

        validate_body = cls(
            version_ref=version_ref,
        )

        return validate_body
