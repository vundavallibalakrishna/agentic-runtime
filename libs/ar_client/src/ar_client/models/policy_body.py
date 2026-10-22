from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.policy_body_document_type_0 import PolicyBodyDocumentType0


T = TypeVar("T", bound="PolicyBody")


@_attrs_define
class PolicyBody:
    """
    Attributes:
        name (str | Unset):  Default: ''.
        description (str | Unset):  Default: ''.
        kind (str | Unset):  Default: 'rules'.
        priority (int | Unset):  Default: 100.
        document (None | PolicyBodyDocumentType0 | Unset):
        rego (None | str | Unset):
    """

    name: str | Unset = ""
    description: str | Unset = ""
    kind: str | Unset = "rules"
    priority: int | Unset = 100
    document: None | PolicyBodyDocumentType0 | Unset = UNSET
    rego: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.policy_body_document_type_0 import PolicyBodyDocumentType0  # noqa: PLC0415

        name = self.name

        description = self.description

        kind = self.kind

        priority = self.priority

        document: dict[str, Any] | None | Unset
        if isinstance(self.document, Unset):
            document = UNSET
        elif isinstance(self.document, PolicyBodyDocumentType0):
            document = self.document.to_dict()
        else:
            document = self.document

        rego: None | str | Unset
        if isinstance(self.rego, Unset):
            rego = UNSET
        else:
            rego = self.rego

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if description is not UNSET:
            field_dict["description"] = description
        if kind is not UNSET:
            field_dict["kind"] = kind
        if priority is not UNSET:
            field_dict["priority"] = priority
        if document is not UNSET:
            field_dict["document"] = document
        if rego is not UNSET:
            field_dict["rego"] = rego

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.policy_body_document_type_0 import PolicyBodyDocumentType0  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name", UNSET)

        description = d.pop("description", UNSET)

        kind = d.pop("kind", UNSET)

        priority = d.pop("priority", UNSET)

        def _parse_document(data: object) -> None | PolicyBodyDocumentType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                document_type_0 = PolicyBodyDocumentType0.from_dict(data)

                return document_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | PolicyBodyDocumentType0 | Unset, data)

        document = _parse_document(d.pop("document", UNSET))

        def _parse_rego(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        rego = _parse_rego(d.pop("rego", UNSET))

        policy_body = cls(
            name=name,
            description=description,
            kind=kind,
            priority=priority,
            document=document,
            rego=rego,
        )

        return policy_body
