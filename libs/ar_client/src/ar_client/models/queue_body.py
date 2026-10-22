from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.queue_body_levels_item import QueueBodyLevelsItem


T = TypeVar("T", bound="QueueBody")


@_attrs_define
class QueueBody:
    """
    Attributes:
        slug (str | Unset):  Default: ''.
        name (str | Unset):  Default: ''.
        subject_type (str | Unset):  Default: ''.
        levels (list[QueueBodyLevelsItem] | Unset):
        statement_template (str | Unset):  Default: ''.
    """

    slug: str | Unset = ""
    name: str | Unset = ""
    subject_type: str | Unset = ""
    levels: list[QueueBodyLevelsItem] | Unset = UNSET
    statement_template: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        from ..models.queue_body_levels_item import QueueBodyLevelsItem  # noqa: PLC0415

        slug = self.slug

        name = self.name

        subject_type = self.subject_type

        levels: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.levels, Unset):
            levels = []
            for levels_item_data in self.levels:
                levels_item = levels_item_data.to_dict()
                levels.append(levels_item)

        statement_template = self.statement_template

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if slug is not UNSET:
            field_dict["slug"] = slug
        if name is not UNSET:
            field_dict["name"] = name
        if subject_type is not UNSET:
            field_dict["subjectType"] = subject_type
        if levels is not UNSET:
            field_dict["levels"] = levels
        if statement_template is not UNSET:
            field_dict["statementTemplate"] = statement_template

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.queue_body_levels_item import QueueBodyLevelsItem  # noqa: PLC0415

        d = dict(src_dict)
        slug = d.pop("slug", UNSET)

        name = d.pop("name", UNSET)

        subject_type = d.pop("subjectType", UNSET)

        _levels = d.pop("levels", UNSET)
        levels: list[QueueBodyLevelsItem] | Unset = UNSET
        if _levels is not UNSET:
            levels = []
            for levels_item_data in _levels:
                levels_item = QueueBodyLevelsItem.from_dict(levels_item_data)

                levels.append(levels_item)

        statement_template = d.pop("statementTemplate", UNSET)

        queue_body = cls(
            slug=slug,
            name=name,
            subject_type=subject_type,
            levels=levels,
            statement_template=statement_template,
        )

        return queue_body
