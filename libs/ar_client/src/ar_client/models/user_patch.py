from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.user_patch_attributes_type_0 import UserPatchAttributesType0





T = TypeVar("T", bound="UserPatch")



@_attrs_define
class UserPatch:
    """ 
        Attributes:
            status (None | str | Unset):
            attributes (None | Unset | UserPatchAttributesType0):
     """

    status: None | str | Unset = UNSET
    attributes: None | Unset | UserPatchAttributesType0 = UNSET





    def to_dict(self) -> dict[str, Any]:
        from ..models.user_patch_attributes_type_0 import UserPatchAttributesType0 # noqa: PLC0415
        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        attributes: dict[str, Any] | None | Unset
        if isinstance(self.attributes, Unset):
            attributes = UNSET
        elif isinstance(self.attributes, UserPatchAttributesType0):
            attributes = self.attributes.to_dict()
        else:
            attributes = self.attributes


        field_dict: dict[str, Any] = {}

        field_dict.update({
        })
        if status is not UNSET:
            field_dict["status"] = status
        if attributes is not UNSET:
            field_dict["attributes"] = attributes

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.user_patch_attributes_type_0 import UserPatchAttributesType0 # noqa: PLC0415
        d = dict(src_dict)
        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))


        def _parse_attributes(data: object) -> None | Unset | UserPatchAttributesType0:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                attributes_type_0 = UserPatchAttributesType0.from_dict(data)



                return attributes_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UserPatchAttributesType0, data)

        attributes = _parse_attributes(d.pop("attributes", UNSET))


        user_patch = cls(
            status=status,
            attributes=attributes,
        )

        return user_patch

