from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.test_body_arguments import TestBodyArguments


T = TypeVar("T", bound="TestBody")


@_attrs_define
class TestBody:
    """
    Attributes:
        arguments (TestBodyArguments | Unset):
        dry_run (bool | Unset):  Default: False.
    """

    arguments: TestBodyArguments | Unset = UNSET
    dry_run: bool | Unset = False

    def to_dict(self) -> dict[str, Any]:
        from ..models.test_body_arguments import TestBodyArguments  # noqa: PLC0415

        arguments: dict[str, Any] | Unset = UNSET
        if not isinstance(self.arguments, Unset):
            arguments = self.arguments.to_dict()

        dry_run = self.dry_run

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if arguments is not UNSET:
            field_dict["arguments"] = arguments
        if dry_run is not UNSET:
            field_dict["dryRun"] = dry_run

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.test_body_arguments import TestBodyArguments  # noqa: PLC0415

        d = dict(src_dict)
        _arguments = d.pop("arguments", UNSET)
        arguments: TestBodyArguments | Unset
        if isinstance(_arguments, Unset):
            arguments = UNSET
        else:
            arguments = TestBodyArguments.from_dict(_arguments)

        dry_run = d.pop("dryRun", UNSET)

        test_body = cls(
            arguments=arguments,
            dry_run=dry_run,
        )

        return test_body
