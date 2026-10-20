from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset







T = TypeVar("T", bound="SaveDraftApiV1AgentsAgentIdVersionsDraftPutResponseSaveDraftApiV1AgentsAgentIdVersionsDraftPut")



@_attrs_define
class SaveDraftApiV1AgentsAgentIdVersionsDraftPutResponseSaveDraftApiV1AgentsAgentIdVersionsDraftPut:
    

    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)





    def to_dict(self) -> dict[str, Any]:
        
        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        save_draft_api_v1_agents_agent_id_versions_draft_put_response_save_draft_api_v1_agents_agent_id_versions_draft_put = cls(
        )


        save_draft_api_v1_agents_agent_id_versions_draft_put_response_save_draft_api_v1_agents_agent_id_versions_draft_put.additional_properties = d
        return save_draft_api_v1_agents_agent_id_versions_draft_put_response_save_draft_api_v1_agents_agent_id_versions_draft_put

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
