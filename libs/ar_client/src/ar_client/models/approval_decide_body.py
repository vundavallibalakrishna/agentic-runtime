from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.approval_decide_body_arguments_type_0 import ApprovalDecideBodyArgumentsType0


T = TypeVar("T", bound="ApprovalDecideBody")


@_attrs_define
class ApprovalDecideBody:
    """
    Attributes:
        decision (str):
        args_hash (str):
        comment (str | Unset):  Default: ''.
        arguments (ApprovalDecideBodyArgumentsType0 | None | Unset):
    """

    decision: str
    args_hash: str
    comment: str | Unset = ""
    arguments: ApprovalDecideBodyArgumentsType0 | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.approval_decide_body_arguments_type_0 import ApprovalDecideBodyArgumentsType0  # noqa: PLC0415

        decision = self.decision

        args_hash = self.args_hash

        comment = self.comment

        arguments: dict[str, Any] | None | Unset
        if isinstance(self.arguments, Unset):
            arguments = UNSET
        elif isinstance(self.arguments, ApprovalDecideBodyArgumentsType0):
            arguments = self.arguments.to_dict()
        else:
            arguments = self.arguments

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "decision": decision,
                "argsHash": args_hash,
            }
        )
        if comment is not UNSET:
            field_dict["comment"] = comment
        if arguments is not UNSET:
            field_dict["arguments"] = arguments

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.approval_decide_body_arguments_type_0 import ApprovalDecideBodyArgumentsType0  # noqa: PLC0415

        d = dict(src_dict)
        decision = d.pop("decision")

        args_hash = d.pop("argsHash")

        comment = d.pop("comment", UNSET)

        def _parse_arguments(data: object) -> ApprovalDecideBodyArgumentsType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                arguments_type_0 = ApprovalDecideBodyArgumentsType0.from_dict(data)

                return arguments_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(ApprovalDecideBodyArgumentsType0 | None | Unset, data)

        arguments = _parse_arguments(d.pop("arguments", UNSET))

        approval_decide_body = cls(
            decision=decision,
            args_hash=args_hash,
            comment=comment,
            arguments=arguments,
        )

        return approval_decide_body
