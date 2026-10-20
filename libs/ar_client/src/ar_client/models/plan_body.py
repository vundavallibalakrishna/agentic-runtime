from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
  from ..models.plan_body_limits import PlanBodyLimits





T = TypeVar("T", bound="PlanBody")



@_attrs_define
class PlanBody:
    """ 
        Attributes:
            key (str):
            name (str):
            limits (PlanBodyLimits | Unset):
     """

    key: str
    name: str
    limits: PlanBodyLimits | Unset = UNSET





    def to_dict(self) -> dict[str, Any]:
        from ..models.plan_body_limits import PlanBodyLimits # noqa: PLC0415
        key = self.key

        name = self.name

        limits: dict[str, Any] | Unset = UNSET
        if not isinstance(self.limits, Unset):
            limits = self.limits.to_dict()


        field_dict: dict[str, Any] = {}

        field_dict.update({
            "key": key,
            "name": name,
        })
        if limits is not UNSET:
            field_dict["limits"] = limits

        return field_dict



    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.plan_body_limits import PlanBodyLimits # noqa: PLC0415
        d = dict(src_dict)
        key = d.pop("key")

        name = d.pop("name")

        _limits = d.pop("limits", UNSET)
        limits: PlanBodyLimits | Unset
        if isinstance(_limits,  Unset):
            limits = UNSET
        else:
            limits = PlanBodyLimits.from_dict(_limits)




        plan_body = cls(
            key=key,
            name=name,
            limits=limits,
        )

        return plan_body

