from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast

if TYPE_CHECKING:
  from ..models.draft_body_definition import DraftBodyDefinition





T = TypeVar("T", bound="DraftBody")



@_attrs_define
class DraftBody:
    """ 
        Attributes:
            definition (DraftBodyDefinition):
     """

    definition: DraftBodyDefinition





    def to_dict(self) -> dict[str, Any]:
        from ..models.draft_body_definition import DraftBodyDefinition # noqa: PLC0415
        definition = self.definition.to_dict()


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "definition": definition,
        })

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.draft_body_definition import DraftBodyDefinition # noqa: PLC0415
        d = dict(src_dict)
        definition = DraftBodyDefinition.from_dict(d.pop("definition"))




        draft_body = cls(
            definition=definition,
        )

        return draft_body

