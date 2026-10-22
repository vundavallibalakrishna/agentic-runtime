from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast


T = TypeVar("T", bound="ToolPatch")


@_attrs_define
class ToolPatch:
    """
    Attributes:
        risk_class (None | str | Unset):
        description_override (None | str | Unset):
        data_classification (None | str | Unset):
        timeout_s (int | None | Unset):
        idempotent (bool | None | Unset):
    """

    risk_class: None | str | Unset = UNSET
    description_override: None | str | Unset = UNSET
    data_classification: None | str | Unset = UNSET
    timeout_s: int | None | Unset = UNSET
    idempotent: bool | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        risk_class: None | str | Unset
        if isinstance(self.risk_class, Unset):
            risk_class = UNSET
        else:
            risk_class = self.risk_class

        description_override: None | str | Unset
        if isinstance(self.description_override, Unset):
            description_override = UNSET
        else:
            description_override = self.description_override

        data_classification: None | str | Unset
        if isinstance(self.data_classification, Unset):
            data_classification = UNSET
        else:
            data_classification = self.data_classification

        timeout_s: int | None | Unset
        if isinstance(self.timeout_s, Unset):
            timeout_s = UNSET
        else:
            timeout_s = self.timeout_s

        idempotent: bool | None | Unset
        if isinstance(self.idempotent, Unset):
            idempotent = UNSET
        else:
            idempotent = self.idempotent

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if risk_class is not UNSET:
            field_dict["riskClass"] = risk_class
        if description_override is not UNSET:
            field_dict["descriptionOverride"] = description_override
        if data_classification is not UNSET:
            field_dict["dataClassification"] = data_classification
        if timeout_s is not UNSET:
            field_dict["timeoutS"] = timeout_s
        if idempotent is not UNSET:
            field_dict["idempotent"] = idempotent

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_risk_class(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        risk_class = _parse_risk_class(d.pop("riskClass", UNSET))

        def _parse_description_override(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description_override = _parse_description_override(d.pop("descriptionOverride", UNSET))

        def _parse_data_classification(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        data_classification = _parse_data_classification(d.pop("dataClassification", UNSET))

        def _parse_timeout_s(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        timeout_s = _parse_timeout_s(d.pop("timeoutS", UNSET))

        def _parse_idempotent(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        idempotent = _parse_idempotent(d.pop("idempotent", UNSET))

        tool_patch = cls(
            risk_class=risk_class,
            description_override=description_override,
            data_classification=data_classification,
            timeout_s=timeout_s,
            idempotent=idempotent,
        )

        return tool_patch
