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
    from ..models.test_body_arguments import TestBodyArguments


T = TypeVar("T", bound="TestBody")


@_attrs_define
class TestBody:
    """
    Attributes:
        arguments (TestBodyArguments | Unset):
        dry_run (bool | Unset):  Default: False.
        conversation_id (None | Unset | UUID):
    """

    arguments: TestBodyArguments | Unset = UNSET
    dry_run: bool | Unset = False
    conversation_id: None | Unset | UUID = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.test_body_arguments import TestBodyArguments  # noqa: PLC0415

        arguments: dict[str, Any] | Unset = UNSET
        if not isinstance(self.arguments, Unset):
            arguments = self.arguments.to_dict()

        dry_run = self.dry_run

        conversation_id: None | str | Unset
        if isinstance(self.conversation_id, Unset):
            conversation_id = UNSET
        elif isinstance(self.conversation_id, UUID):
            conversation_id = str(self.conversation_id)
        else:
            conversation_id = self.conversation_id

        field_dict: dict[str, Any] = {}

        field_dict.update({})
        if arguments is not UNSET:
            field_dict["arguments"] = arguments
        if dry_run is not UNSET:
            field_dict["dryRun"] = dry_run
        if conversation_id is not UNSET:
            field_dict["conversationId"] = conversation_id

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

        def _parse_conversation_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                conversation_id_type_0 = UUID(data)

                return conversation_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        conversation_id = _parse_conversation_id(d.pop("conversationId", UNSET))

        test_body = cls(
            arguments=arguments,
            dry_run=dry_run,
            conversation_id=conversation_id,
        )

        return test_body
