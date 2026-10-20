from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast






T = TypeVar("T", bound="ServiceAccountPatch")



@_attrs_define
class ServiceAccountPatch:
    """ 
        Attributes:
            description (None | str | Unset):
            status (None | str | Unset):
            allow_on_behalf_of (bool | None | Unset):
     """

    description: None | str | Unset = UNSET
    status: None | str | Unset = UNSET
    allow_on_behalf_of: bool | None | Unset = UNSET





    def to_dict(self) -> dict[str, Any]:
        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        allow_on_behalf_of: bool | None | Unset
        if isinstance(self.allow_on_behalf_of, Unset):
            allow_on_behalf_of = UNSET
        else:
            allow_on_behalf_of = self.allow_on_behalf_of


        field_dict: dict[str, Any] = {}

        field_dict.update({
        })
        if description is not UNSET:
            field_dict["description"] = description
        if status is not UNSET:
            field_dict["status"] = status
        if allow_on_behalf_of is not UNSET:
            field_dict["allowOnBehalfOf"] = allow_on_behalf_of

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))


        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))


        def _parse_allow_on_behalf_of(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        allow_on_behalf_of = _parse_allow_on_behalf_of(d.pop("allowOnBehalfOf", UNSET))


        service_account_patch = cls(
            description=description,
            status=status,
            allow_on_behalf_of=allow_on_behalf_of,
        )

        return service_account_patch

