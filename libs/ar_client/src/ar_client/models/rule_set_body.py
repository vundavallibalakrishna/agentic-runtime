from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast
from uuid import UUID

if TYPE_CHECKING:
    from ..models.rule_set_item import RuleSetItem


T = TypeVar("T", bound="RuleSetBody")


@_attrs_define
class RuleSetBody:
    """
    Attributes:
        id (str | Unset):  Default: ''.
        version (str | Unset):  Default: ''.
        items (list[RuleSetItem] | Unset):
        source_file_id (None | Unset | UUID):
        sha256 (str | Unset):  Default: ''.
    """

    id: str | Unset = ""
    version: str | Unset = ""
    items: list[RuleSetItem] | Unset = UNSET
    source_file_id: None | Unset | UUID = UNSET
    sha256: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        from ..models.rule_set_item import RuleSetItem  # noqa: PLC0415

        id = self.id

        version = self.version

        items: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.items, Unset):
            items = []
            for items_item_data in self.items:
                items_item = items_item_data.to_dict()
                items.append(items_item)

        source_file_id: None | str | Unset
        if isinstance(self.source_file_id, Unset):
            source_file_id = UNSET
        elif isinstance(self.source_file_id, UUID):
            source_file_id = str(self.source_file_id)
        else:
            source_file_id = self.source_file_id

        sha256 = self.sha256

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if version is not UNSET:
            field_dict["version"] = version
        if items is not UNSET:
            field_dict["items"] = items
        if source_file_id is not UNSET:
            field_dict["sourceFileId"] = source_file_id
        if sha256 is not UNSET:
            field_dict["sha256"] = sha256

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.rule_set_item import RuleSetItem  # noqa: PLC0415

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        version = d.pop("version", UNSET)

        _items = d.pop("items", UNSET)
        items: list[RuleSetItem] | Unset = UNSET
        if _items is not UNSET:
            items = []
            for items_item_data in _items:
                items_item = RuleSetItem.from_dict(items_item_data)

                items.append(items_item)

        def _parse_source_file_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                source_file_id_type_0 = UUID(data)

                return source_file_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        source_file_id = _parse_source_file_id(d.pop("sourceFileId", UNSET))

        sha256 = d.pop("sha256", UNSET)

        rule_set_body = cls(
            id=id,
            version=version,
            items=items,
            source_file_id=source_file_id,
            sha256=sha256,
        )

        return rule_set_body
