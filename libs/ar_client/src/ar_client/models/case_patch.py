from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.case_patch_assertions_type_0_item import CasePatchAssertionsType0Item
    from ..models.case_patch_input_type_0 import CasePatchInputType0
    from ..models.case_patch_tool_mocks_type_0_item import CasePatchToolMocksType0Item


T = TypeVar("T", bound="CasePatch")


@_attrs_define
class CasePatch:
    """
    Attributes:
        name (None | str | Unset):
        input_ (CasePatchInputType0 | None | Unset):
        assertions (list[CasePatchAssertionsType0Item] | None | Unset):
        tool_mocks (list[CasePatchToolMocksType0Item] | None | Unset):
        tags (list[str] | None | Unset):
    """

    name: None | str | Unset = UNSET
    input_: CasePatchInputType0 | None | Unset = UNSET
    assertions: list[CasePatchAssertionsType0Item] | None | Unset = UNSET
    tool_mocks: list[CasePatchToolMocksType0Item] | None | Unset = UNSET
    tags: list[str] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.case_patch_assertions_type_0_item import CasePatchAssertionsType0Item  # noqa: PLC0415
        from ..models.case_patch_input_type_0 import CasePatchInputType0  # noqa: PLC0415
        from ..models.case_patch_tool_mocks_type_0_item import CasePatchToolMocksType0Item  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        input_: dict[str, Any] | None | Unset
        if isinstance(self.input_, Unset):
            input_ = UNSET
        elif isinstance(self.input_, CasePatchInputType0):
            input_ = self.input_.to_dict()
        else:
            input_ = self.input_

        assertions: list[dict[str, Any]] | None | Unset
        if isinstance(self.assertions, Unset):
            assertions = UNSET
        elif isinstance(self.assertions, list):
            assertions = []
            for assertions_type_0_item_data in self.assertions:
                assertions_type_0_item = assertions_type_0_item_data.to_dict()
                assertions.append(assertions_type_0_item)

        else:
            assertions = self.assertions

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

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if input_ is not UNSET:
            field_dict["input"] = input_
        if assertions is not UNSET:
            field_dict["assertions"] = assertions
        if tool_mocks is not UNSET:
            field_dict["toolMocks"] = tool_mocks
        if tags is not UNSET:
            field_dict["tags"] = tags

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.case_patch_assertions_type_0_item import CasePatchAssertionsType0Item  # noqa: PLC0415
        from ..models.case_patch_input_type_0 import CasePatchInputType0  # noqa: PLC0415
        from ..models.case_patch_tool_mocks_type_0_item import CasePatchToolMocksType0Item  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_input_(data: object) -> CasePatchInputType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                input_type_0 = CasePatchInputType0.from_dict(data)

                return input_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(CasePatchInputType0 | None | Unset, data)

        input_ = _parse_input_(d.pop("input", UNSET))

        def _parse_assertions(data: object) -> list[CasePatchAssertionsType0Item] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                assertions_type_0 = []
                _assertions_type_0 = data
                for assertions_type_0_item_data in _assertions_type_0:
                    assertions_type_0_item = CasePatchAssertionsType0Item.from_dict(
                        assertions_type_0_item_data
                    )

                    assertions_type_0.append(assertions_type_0_item)

                return assertions_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[CasePatchAssertionsType0Item] | None | Unset, data)

        assertions = _parse_assertions(d.pop("assertions", UNSET))

        def _parse_tool_mocks(data: object) -> list[CasePatchToolMocksType0Item] | None | Unset:
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
                    tool_mocks_type_0_item = CasePatchToolMocksType0Item.from_dict(
                        tool_mocks_type_0_item_data
                    )

                    tool_mocks_type_0.append(tool_mocks_type_0_item)

                return tool_mocks_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[CasePatchToolMocksType0Item] | None | Unset, data)

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

        case_patch = cls(
            name=name,
            input_=input_,
            assertions=assertions,
            tool_mocks=tool_mocks,
            tags=tags,
        )

        return case_patch
