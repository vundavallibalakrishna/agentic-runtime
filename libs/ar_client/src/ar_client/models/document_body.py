from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="DocumentBody")


@_attrs_define
class DocumentBody:
    """
    Attributes:
        file_ids (list[UUID] | Unset):
        acl_principals (list[str] | None | Unset):
    """

    file_ids: list[UUID] | Unset = UNSET
    acl_principals: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        file_ids: list[str] | Unset = UNSET
        if not isinstance(self.file_ids, Unset):
            file_ids = []
            for file_ids_item_data in self.file_ids:
                file_ids_item = str(file_ids_item_data)
                file_ids.append(file_ids_item)

        acl_principals: list[str] | None | Unset
        if isinstance(self.acl_principals, Unset):
            acl_principals = UNSET
        elif isinstance(self.acl_principals, list):
            acl_principals = self.acl_principals

        else:
            acl_principals = self.acl_principals

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if file_ids is not UNSET:
            field_dict["fileIds"] = file_ids
        if acl_principals is not UNSET:
            field_dict["aclPrincipals"] = acl_principals

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        _file_ids = d.pop("fileIds", UNSET)
        file_ids: list[UUID] | Unset = UNSET
        if _file_ids is not UNSET:
            file_ids = []
            for file_ids_item_data in _file_ids:
                file_ids_item = UUID(file_ids_item_data)

                file_ids.append(file_ids_item)

        def _parse_acl_principals(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                acl_principals_type_0 = cast(list[str], data)

                return acl_principals_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        acl_principals = _parse_acl_principals(d.pop("aclPrincipals", UNSET))

        document_body = cls(
            file_ids=file_ids,
            acl_principals=acl_principals,
        )

        return document_body
