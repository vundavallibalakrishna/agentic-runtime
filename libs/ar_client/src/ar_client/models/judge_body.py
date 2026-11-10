from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.rule_set_body import RuleSetBody


T = TypeVar("T", bound="JudgeBody")


@_attrs_define
class JudgeBody:
    """
    Attributes:
        rule_set_id (str | Unset):  Default: ''.
        statements (list[str] | Unset):
        rule_set (None | RuleSetBody | Unset):
        label (str | Unset):  Default: ''.
        model_alias (str | Unset):  Default: ''.
    """

    rule_set_id: str | Unset = ""
    statements: list[str] | Unset = UNSET
    rule_set: None | RuleSetBody | Unset = UNSET
    label: str | Unset = ""
    model_alias: str | Unset = ""

    def to_dict(self) -> dict[str, Any]:
        from ..models.rule_set_body import RuleSetBody  # noqa: PLC0415

        rule_set_id = self.rule_set_id

        statements: list[str] | Unset = UNSET
        if not isinstance(self.statements, Unset):
            statements = self.statements

        rule_set: dict[str, Any] | None | Unset
        if isinstance(self.rule_set, Unset):
            rule_set = UNSET
        elif isinstance(self.rule_set, RuleSetBody):
            rule_set = self.rule_set.to_dict()
        else:
            rule_set = self.rule_set

        label = self.label

        model_alias = self.model_alias

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if rule_set_id is not UNSET:
            field_dict["ruleSetId"] = rule_set_id
        if statements is not UNSET:
            field_dict["statements"] = statements
        if rule_set is not UNSET:
            field_dict["ruleSet"] = rule_set
        if label is not UNSET:
            field_dict["label"] = label
        if model_alias is not UNSET:
            field_dict["modelAlias"] = model_alias

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.rule_set_body import RuleSetBody  # noqa: PLC0415

        d = dict(src_dict)
        rule_set_id = d.pop("ruleSetId", UNSET)

        statements = cast(list[str], d.pop("statements", UNSET))

        def _parse_rule_set(data: object) -> None | RuleSetBody | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                rule_set_type_0 = RuleSetBody.from_dict(data)

                return rule_set_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | RuleSetBody | Unset, data)

        rule_set = _parse_rule_set(d.pop("ruleSet", UNSET))

        label = d.pop("label", UNSET)

        model_alias = d.pop("modelAlias", UNSET)

        judge_body = cls(
            rule_set_id=rule_set_id,
            statements=statements,
            rule_set=rule_set,
            label=label,
            model_alias=model_alias,
        )

        return judge_body
