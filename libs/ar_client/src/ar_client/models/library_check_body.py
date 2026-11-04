from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID


T = TypeVar("T", bound="LibraryCheckBody")


@_attrs_define
class LibraryCheckBody:
    """
    Attributes:
        standard_document_id (None | Unset | UUID):
        requirements (list[str] | Unset):
        label (str | Unset):  Default: ''.
        model_alias (str | Unset):  Default: ''.
    """

    standard_document_id: None | Unset | UUID = UNSET
    requirements: list[str] | Unset = UNSET
    label: str | Unset = ""
    model_alias: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        standard_document_id: None | str | Unset
        if isinstance(self.standard_document_id, Unset):
            standard_document_id = UNSET
        elif isinstance(self.standard_document_id, UUID):
            standard_document_id = str(self.standard_document_id)
        else:
            standard_document_id = self.standard_document_id

        requirements: list[str] | Unset = UNSET
        if not isinstance(self.requirements, Unset):
            requirements = self.requirements

        label = self.label

        model_alias = self.model_alias

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if standard_document_id is not UNSET:
            field_dict["standardDocumentId"] = standard_document_id
        if requirements is not UNSET:
            field_dict["requirements"] = requirements
        if label is not UNSET:
            field_dict["label"] = label
        if model_alias is not UNSET:
            field_dict["modelAlias"] = model_alias

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)

        def _parse_standard_document_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                standard_document_id_type_0 = UUID(data)

                return standard_document_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        standard_document_id = _parse_standard_document_id(d.pop("standardDocumentId", UNSET))

        requirements = cast(list[str], d.pop("requirements", UNSET))

        label = d.pop("label", UNSET)

        model_alias = d.pop("modelAlias", UNSET)

        library_check_body = cls(
            standard_document_id=standard_document_id,
            requirements=requirements,
            label=label,
            model_alias=model_alias,
        )

        return library_check_body
