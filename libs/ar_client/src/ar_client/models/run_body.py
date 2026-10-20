from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID






T = TypeVar("T", bound="RunBody")



@_attrs_define
class RunBody:
    """ 
        Attributes:
            agent_id (UUID):
            text (str):
            callback_url (None | str | Unset):
            on_behalf_of_user_id (None | Unset | UUID):
            allow_on_behalf_of (bool | Unset):  Default: False.
            wait (bool | Unset):  Default: False.
     """

    agent_id: UUID
    text: str
    callback_url: None | str | Unset = UNSET
    on_behalf_of_user_id: None | Unset | UUID = UNSET
    allow_on_behalf_of: bool | Unset = False
    wait: bool | Unset = False





    def to_dict(self) -> dict[str, Any]:
        agent_id = str(self.agent_id)

        text = self.text

        callback_url: None | str | Unset
        if isinstance(self.callback_url, Unset):
            callback_url = UNSET
        else:
            callback_url = self.callback_url

        on_behalf_of_user_id: None | str | Unset
        if isinstance(self.on_behalf_of_user_id, Unset):
            on_behalf_of_user_id = UNSET
        elif isinstance(self.on_behalf_of_user_id, UUID):
            on_behalf_of_user_id = str(self.on_behalf_of_user_id)
        else:
            on_behalf_of_user_id = self.on_behalf_of_user_id

        allow_on_behalf_of = self.allow_on_behalf_of

        wait = self.wait


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "agentId": agent_id,
            "text": text,
        })
        if callback_url is not UNSET:
            field_dict["callbackUrl"] = callback_url
        if on_behalf_of_user_id is not UNSET:
            field_dict["onBehalfOfUserId"] = on_behalf_of_user_id
        if allow_on_behalf_of is not UNSET:
            field_dict["allowOnBehalfOf"] = allow_on_behalf_of
        if wait is not UNSET:
            field_dict["wait"] = wait

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        agent_id = UUID(d.pop("agentId"))




        text = d.pop("text")

        def _parse_callback_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        callback_url = _parse_callback_url(d.pop("callbackUrl", UNSET))


        def _parse_on_behalf_of_user_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                on_behalf_of_user_id_type_0 = UUID(data)



                return on_behalf_of_user_id_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        on_behalf_of_user_id = _parse_on_behalf_of_user_id(d.pop("onBehalfOfUserId", UNSET))


        allow_on_behalf_of = d.pop("allowOnBehalfOf", UNSET)

        wait = d.pop("wait", UNSET)

        run_body = cls(
            agent_id=agent_id,
            text=text,
            callback_url=callback_url,
            on_behalf_of_user_id=on_behalf_of_user_id,
            allow_on_behalf_of=allow_on_behalf_of,
            wait=wait,
        )

        return run_body

