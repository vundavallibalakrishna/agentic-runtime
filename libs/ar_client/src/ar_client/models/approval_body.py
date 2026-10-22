from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="ApprovalBody")


@_attrs_define
class ApprovalBody:
    """
    Attributes:
        approval_id (UUID):
        decision (str):
        args_hash (str | Unset):  Default: ''.
        external_user_id (str | Unset):  Default: ''.
        integration_id (None | Unset | UUID):
    """

    approval_id: UUID
    decision: str
    args_hash: str | Unset = ""
    external_user_id: str | Unset = ""
    integration_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        approval_id = str(self.approval_id)

        decision = self.decision

        args_hash = self.args_hash

        external_user_id = self.external_user_id

        integration_id: None | str | Unset
        if isinstance(self.integration_id, Unset):
            integration_id = UNSET
        elif isinstance(self.integration_id, UUID):
            integration_id = str(self.integration_id)
        else:
            integration_id = self.integration_id

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "approvalId": approval_id,
                "decision": decision,
            }
        )
        if args_hash is not UNSET:
            field_dict["argsHash"] = args_hash
        if external_user_id is not UNSET:
            field_dict["externalUserId"] = external_user_id
        if integration_id is not UNSET:
            field_dict["integrationId"] = integration_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        approval_id = UUID(d.pop("approvalId"))

        decision = d.pop("decision")

        args_hash = d.pop("argsHash", UNSET)

        external_user_id = d.pop("externalUserId", UNSET)

        def _parse_integration_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                integration_id_type_0 = UUID(data)

                return integration_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        integration_id = _parse_integration_id(d.pop("integrationId", UNSET))

        approval_body = cls(
            approval_id=approval_id,
            decision=decision,
            args_hash=args_hash,
            external_user_id=external_user_id,
            integration_id=integration_id,
        )

        return approval_body
