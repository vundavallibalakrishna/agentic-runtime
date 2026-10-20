from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from typing import cast

if TYPE_CHECKING:
  from ..models.idp_create_config import IdpCreateConfig





T = TypeVar("T", bound="IdpCreate")



@_attrs_define
class IdpCreate:
    """ 
        Attributes:
            kind (str):
            display_name (str):
            config (IdpCreateConfig):
     """

    kind: str
    display_name: str
    config: IdpCreateConfig





    def to_dict(self) -> dict[str, Any]:
        from ..models.idp_create_config import IdpCreateConfig # noqa: PLC0415
        kind = self.kind

        display_name = self.display_name

        config = self.config.to_dict()


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "kind": kind,
            "displayName": display_name,
            "config": config,
        })

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.idp_create_config import IdpCreateConfig # noqa: PLC0415
        d = dict(src_dict)
        kind = d.pop("kind")

        display_name = d.pop("displayName")

        config = IdpCreateConfig.from_dict(d.pop("config"))




        idp_create = cls(
            kind=kind,
            display_name=display_name,
            config=config,
        )

        return idp_create

