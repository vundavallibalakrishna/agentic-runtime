from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="AssignmentCreate")


@_attrs_define
class AssignmentCreate:
    """
    Attributes:
        role_id (UUID):
        principal_type (str):
        principal_id (UUID):
        scope_type (str | Unset):  Default: 'tenant'.
        scope_id (None | Unset | UUID):
    """

    role_id: UUID
    principal_type: str
    principal_id: UUID
    scope_type: str | Unset = "tenant"
    scope_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        role_id = str(self.role_id)

        principal_type = self.principal_type

        principal_id = str(self.principal_id)

        scope_type = self.scope_type

        scope_id: None | str | Unset
        if isinstance(self.scope_id, Unset):
            scope_id = UNSET
        elif isinstance(self.scope_id, UUID):
            scope_id = str(self.scope_id)
        else:
            scope_id = self.scope_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "roleId": role_id,
                "principalType": principal_type,
                "principalId": principal_id,
            }
        )
        if scope_type is not UNSET:
            field_dict["scopeType"] = scope_type
        if scope_id is not UNSET:
            field_dict["scopeId"] = scope_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        role_id = UUID(d.pop("roleId"))

        principal_type = d.pop("principalType")

        principal_id = UUID(d.pop("principalId"))

        scope_type = d.pop("scopeType", UNSET)

        def _parse_scope_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                scope_id_type_0 = UUID(data)

                return scope_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        scope_id = _parse_scope_id(d.pop("scopeId", UNSET))

        assignment_create = cls(
            role_id=role_id,
            principal_type=principal_type,
            principal_id=principal_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

        return assignment_create
