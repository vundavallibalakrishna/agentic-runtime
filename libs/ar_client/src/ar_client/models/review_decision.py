from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.review_decision_arguments_type_0 import ReviewDecisionArgumentsType0


T = TypeVar("T", bound="ReviewDecision")


@_attrs_define
class ReviewDecision:
    """
    Attributes:
        decision (str):
        comment (str | Unset):  Default: ''.
        args_hash (str | Unset):  Default: ''.
        arguments (None | ReviewDecisionArgumentsType0 | Unset):
    """

    decision: str
    comment: str | Unset = ""
    args_hash: str | Unset = ""
    arguments: None | ReviewDecisionArgumentsType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.review_decision_arguments_type_0 import ReviewDecisionArgumentsType0  # noqa: PLC0415

        decision = self.decision

        comment = self.comment

        args_hash = self.args_hash

        arguments: dict[str, Any] | None | Unset
        if isinstance(self.arguments, Unset):
            arguments = UNSET
        elif isinstance(self.arguments, ReviewDecisionArgumentsType0):
            arguments = self.arguments.to_dict()
        else:
            arguments = self.arguments

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "decision": decision,
            }
        )
        if comment is not UNSET:
            field_dict["comment"] = comment
        if args_hash is not UNSET:
            field_dict["argsHash"] = args_hash
        if arguments is not UNSET:
            field_dict["arguments"] = arguments

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.review_decision_arguments_type_0 import ReviewDecisionArgumentsType0  # noqa: PLC0415

        d = dict(src_dict)
        decision = d.pop("decision")

        comment = d.pop("comment", UNSET)

        args_hash = d.pop("argsHash", UNSET)

        def _parse_arguments(data: object) -> None | ReviewDecisionArgumentsType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                arguments_type_0 = ReviewDecisionArgumentsType0.from_dict(data)

                return arguments_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | ReviewDecisionArgumentsType0 | Unset, data)

        arguments = _parse_arguments(d.pop("arguments", UNSET))

        review_decision = cls(
            decision=decision,
            comment=comment,
            args_hash=args_hash,
            arguments=arguments,
        )

        return review_decision
