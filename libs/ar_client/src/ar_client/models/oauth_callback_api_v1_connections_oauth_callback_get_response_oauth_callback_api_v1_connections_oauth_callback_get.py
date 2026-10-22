from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset


T = TypeVar(
    "T",
    bound="OauthCallbackApiV1ConnectionsOauthCallbackGetResponseOauthCallbackApiV1ConnectionsOauthCallbackGet",
)


@_attrs_define
class OauthCallbackApiV1ConnectionsOauthCallbackGetResponseOauthCallbackApiV1ConnectionsOauthCallbackGet:
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        oauth_callback_api_v1_connections_oauth_callback_get_response_oauth_callback_api_v1_connections_oauth_callback_get = cls()

        oauth_callback_api_v1_connections_oauth_callback_get_response_oauth_callback_api_v1_connections_oauth_callback_get.additional_properties = d
        return oauth_callback_api_v1_connections_oauth_callback_get_response_oauth_callback_api_v1_connections_oauth_callback_get

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
