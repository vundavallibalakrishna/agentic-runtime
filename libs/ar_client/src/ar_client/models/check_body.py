from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="CheckBody")


@_attrs_define
class CheckBody:
    """
    Attributes:
        action (str | Unset):  Default: 'approval'.
        preparer_principal_id (None | Unset | UUID):
        signer_principal_id (None | Unset | UUID):
        agent_id (None | Unset | UUID):
    """

    action: str | Unset = "approval"
    preparer_principal_id: None | Unset | UUID = UNSET
    signer_principal_id: None | Unset | UUID = UNSET
    agent_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        action = self.action

        preparer_principal_id: None | str | Unset
        if isinstance(self.preparer_principal_id, Unset):
            preparer_principal_id = UNSET
        elif isinstance(self.preparer_principal_id, UUID):
            preparer_principal_id = str(self.preparer_principal_id)
        else:
            preparer_principal_id = self.preparer_principal_id

        signer_principal_id: None | str | Unset
        if isinstance(self.signer_principal_id, Unset):
            signer_principal_id = UNSET
        elif isinstance(self.signer_principal_id, UUID):
            signer_principal_id = str(self.signer_principal_id)
        else:
            signer_principal_id = self.signer_principal_id

        agent_id: None | str | Unset
        if isinstance(self.agent_id, Unset):
            agent_id = UNSET
        elif isinstance(self.agent_id, UUID):
            agent_id = str(self.agent_id)
        else:
            agent_id = self.agent_id

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if action is not UNSET:
            field_dict["action"] = action
        if preparer_principal_id is not UNSET:
            field_dict["preparerPrincipalId"] = preparer_principal_id
        if signer_principal_id is not UNSET:
            field_dict["signerPrincipalId"] = signer_principal_id
        if agent_id is not UNSET:
            field_dict["agentId"] = agent_id

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        action = d.pop("action", UNSET)

        def _parse_preparer_principal_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                preparer_principal_id_type_0 = UUID(data)

                return preparer_principal_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        preparer_principal_id = _parse_preparer_principal_id(d.pop("preparerPrincipalId", UNSET))

        def _parse_signer_principal_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                signer_principal_id_type_0 = UUID(data)

                return signer_principal_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        signer_principal_id = _parse_signer_principal_id(d.pop("signerPrincipalId", UNSET))

        def _parse_agent_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                agent_id_type_0 = UUID(data)

                return agent_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        agent_id = _parse_agent_id(d.pop("agentId", UNSET))

        check_body = cls(
            action=action,
            preparer_principal_id=preparer_principal_id,
            signer_principal_id=signer_principal_id,
            agent_id=agent_id,
        )

        return check_body
