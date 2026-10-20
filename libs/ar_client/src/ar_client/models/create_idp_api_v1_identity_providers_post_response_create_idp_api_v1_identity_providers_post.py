from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset







T = TypeVar("T", bound="CreateIdpApiV1IdentityProvidersPostResponseCreateIdpApiV1IdentityProvidersPost")



@_attrs_define
class CreateIdpApiV1IdentityProvidersPostResponseCreateIdpApiV1IdentityProvidersPost:
    

    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        
        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        create_idp_api_v1_identity_providers_post_response_create_idp_api_v1_identity_providers_post = cls(
        )


        create_idp_api_v1_identity_providers_post_response_create_idp_api_v1_identity_providers_post.additional_properties = d
        return create_idp_api_v1_identity_providers_post_response_create_idp_api_v1_identity_providers_post

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
