from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.case_body_assertions_item import CaseBodyAssertionsItem
    from ..models.case_body_input import CaseBodyInput
    from ..models.case_body_tool_mocks_type_0_item import CaseBodyToolMocksType0Item


T = TypeVar("T", bound="CaseBody")


@_attrs_define
class CaseBody:
    """
    Attributes:
        name (str):
        input_ (CaseBodyInput):
        assertions (list[CaseBodyAssertionsItem]):
        tool_mocks (list[CaseBodyToolMocksType0Item] | None | Unset):
        tags (list[str] | None | Unset):
    """

    name: str
    input_: CaseBodyInput
    assertions: list[CaseBodyAssertionsItem]
    tool_mocks: list[CaseBodyToolMocksType0Item] | None | Unset = UNSET
    tags: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.case_body_assertions_item import CaseBodyAssertionsItem  # noqa: PLC0415
        from ..models.case_body_input import CaseBodyInput  # noqa: PLC0415
        from ..models.case_body_tool_mocks_type_0_item import CaseBodyToolMocksType0Item  # noqa: PLC0415

        name = self.name

        input_ = self.input_.to_dict()

        assertions = []
        for assertions_item_data in self.assertions:
            assertions_item = assertions_item_data.to_dict()
            assertions.append(assertions_item)

        tool_mocks: list[dict[str, Any]] | None | Unset
        if isinstance(self.tool_mocks, Unset):
            tool_mocks = UNSET
        elif isinstance(self.tool_mocks, list):
            tool_mocks = []
            for tool_mocks_type_0_item_data in self.tool_mocks:
                tool_mocks_type_0_item = tool_mocks_type_0_item_data.to_dict()
                tool_mocks.append(tool_mocks_type_0_item)

        else:
            tool_mocks = self.tool_mocks

        tags: list[str] | None | Unset
        if isinstance(self.tags, Unset):
            tags = UNSET
        elif isinstance(self.tags, list):
            tags = self.tags

        else:
            tags = self.tags

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "name": name,
                "input": input_,
                "assertions": assertions,
            }
        )
        if tool_mocks is not UNSET:
            field_dict["toolMocks"] = tool_mocks
        if tags is not UNSET:
            field_dict["tags"] = tags

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.case_body_assertions_item import CaseBodyAssertionsItem  # noqa: PLC0415
        from ..models.case_body_input import CaseBodyInput  # noqa: PLC0415
        from ..models.case_body_tool_mocks_type_0_item import CaseBodyToolMocksType0Item  # noqa: PLC0415

        d = dict(src_dict)
        name = d.pop("name")

        input_ = CaseBodyInput.from_dict(d.pop("input"))

        assertions = []
        _assertions = d.pop("assertions")
        for assertions_item_data in _assertions:
            assertions_item = CaseBodyAssertionsItem.from_dict(assertions_item_data)

            assertions.append(assertions_item)

        def _parse_tool_mocks(data: object) -> list[CaseBodyToolMocksType0Item] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                tool_mocks_type_0 = []
                _tool_mocks_type_0 = data
                for tool_mocks_type_0_item_data in _tool_mocks_type_0:
                    tool_mocks_type_0_item = CaseBodyToolMocksType0Item.from_dict(
                        tool_mocks_type_0_item_data
                    )

                    tool_mocks_type_0.append(tool_mocks_type_0_item)

                return tool_mocks_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[CaseBodyToolMocksType0Item] | None | Unset, data)

        tool_mocks = _parse_tool_mocks(d.pop("toolMocks", UNSET))

        def _parse_tags(data: object) -> list[str] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                tags_type_0 = cast(list[str], data)

                return tags_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[str] | None | Unset, data)

        tags = _parse_tags(d.pop("tags", UNSET))

        case_body = cls(
            name=name,
            input_=input_,
            assertions=assertions,
            tool_mocks=tool_mocks,
            tags=tags,
        )

        return case_body
