from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID






T = TypeVar("T", bound="ApiKeyCreate")



@_attrs_define
class ApiKeyCreate:
    """ 
        Attributes:
            name (str):
            service_account_id (None | Unset | UUID):
            scopes (list[str] | Unset):
            expires_in_days (int | Unset):  Default: 90.
     """

    name: str
    service_account_id: None | Unset | UUID = UNSET
    scopes: list[str] | Unset = UNSET
    expires_in_days: int | Unset = 90





    def to_dict(self) -> dict[str, Any]:
        name = self.name

        service_account_id: None | str | Unset
        if isinstance(self.service_account_id, Unset):
            service_account_id = UNSET
        elif isinstance(self.service_account_id, UUID):
            service_account_id = str(self.service_account_id)
        else:
            service_account_id = self.service_account_id

        scopes: list[str] | Unset = UNSET
        if not isinstance(self.scopes, Unset):
            scopes = self.scopes



        expires_in_days = self.expires_in_days


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "name": name,
        })
        if service_account_id is not UNSET:
            field_dict["serviceAccountId"] = service_account_id
        if scopes is not UNSET:
            field_dict["scopes"] = scopes
        if expires_in_days is not UNSET:
            field_dict["expiresInDays"] = expires_in_days

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        name = d.pop("name")

        def _parse_service_account_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                service_account_id_type_0 = UUID(data)



                return service_account_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        service_account_id = _parse_service_account_id(d.pop("serviceAccountId", UNSET))


        scopes = cast(list[str], d.pop("scopes", UNSET))


        expires_in_days = d.pop("expiresInDays", UNSET)

        api_key_create = cls(
            name=name,
            service_account_id=service_account_id,
            scopes=scopes,
            expires_in_days=expires_in_days,
        )

        return api_key_create

