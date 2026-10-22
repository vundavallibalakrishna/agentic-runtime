from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.queue_patch_levels_type_0_item import QueuePatchLevelsType0Item


T = TypeVar("T", bound="QueuePatch")


@_attrs_define
class QueuePatch:
    """
    Attributes:
        name (None | str | Unset):
        levels (list[QueuePatchLevelsType0Item] | None | Unset):
        statement_template (None | str | Unset):
    """

    name: None | str | Unset = UNSET
    levels: list[QueuePatchLevelsType0Item] | None | Unset = UNSET
    statement_template: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.queue_patch_levels_type_0_item import QueuePatchLevelsType0Item  # noqa: PLC0415

        name: None | str | Unset
        if isinstance(self.name, Unset):
            name = UNSET
        else:
            name = self.name

        levels: list[dict[str, Any]] | None | Unset
        if isinstance(self.levels, Unset):
            levels = UNSET
        elif isinstance(self.levels, list):
            levels = []
            for levels_type_0_item_data in self.levels:
                levels_type_0_item = levels_type_0_item_data.to_dict()
                levels.append(levels_type_0_item)

        else:
            levels = self.levels

        statement_template: None | str | Unset
        if isinstance(self.statement_template, Unset):
            statement_template = UNSET
        else:
            statement_template = self.statement_template

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if name is not UNSET:
            field_dict["name"] = name
        if levels is not UNSET:
            field_dict["levels"] = levels
        if statement_template is not UNSET:
            field_dict["statementTemplate"] = statement_template

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.queue_patch_levels_type_0_item import QueuePatchLevelsType0Item  # noqa: PLC0415

        d = dict(src_dict)

        def _parse_name(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        name = _parse_name(d.pop("name", UNSET))

        def _parse_levels(data: object) -> list[QueuePatchLevelsType0Item] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                levels_type_0 = []
                _levels_type_0 = data
                for levels_type_0_item_data in _levels_type_0:
                    levels_type_0_item = QueuePatchLevelsType0Item.from_dict(
                        levels_type_0_item_data
                    )

                    levels_type_0.append(levels_type_0_item)

                return levels_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[QueuePatchLevelsType0Item] | None | Unset, data)

        levels = _parse_levels(d.pop("levels", UNSET))

        def _parse_statement_template(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        statement_template = _parse_statement_template(d.pop("statementTemplate", UNSET))

        queue_patch = cls(
            name=name,
            levels=levels,
            statement_template=statement_template,
        )

        return queue_patch
