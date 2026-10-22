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
    from ..models.item_body_subjectref import ItemBodySubjectref


T = TypeVar("T", bound="ItemBody")


@_attrs_define
class ItemBody:
    """
    Attributes:
        queue_id (UUID):
        subject_id (UUID):
        content_hash (str):
        statement_text (str):
        subject_type (str | Unset):  Default: ''.
        subject_ref (ItemBodySubjectref | Unset):
    """

    queue_id: UUID
    subject_id: UUID
    content_hash: str
    statement_text: str
    subject_type: str | Unset = ""
    subject_ref: ItemBodySubjectref | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.item_body_subjectref import ItemBodySubjectref  # noqa: PLC0415

        queue_id = str(self.queue_id)

        subject_id = str(self.subject_id)

        content_hash = self.content_hash

        statement_text = self.statement_text

        subject_type = self.subject_type

        subject_ref: dict[str, Any] | Unset = UNSET
        if not isinstance(self.subject_ref, Unset):
            subject_ref = self.subject_ref.to_dict()

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "queueId": queue_id,
                "subjectId": subject_id,
                "contentHash": content_hash,
                "statementText": statement_text,
            }
        )
        if subject_type is not UNSET:
            field_dict["subjectType"] = subject_type
        if subject_ref is not UNSET:
            field_dict["subjectRef"] = subject_ref

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.item_body_subjectref import ItemBodySubjectref  # noqa: PLC0415

        d = dict(src_dict)
        queue_id = UUID(d.pop("queueId"))

        subject_id = UUID(d.pop("subjectId"))

        content_hash = d.pop("contentHash")

        statement_text = d.pop("statementText")

        subject_type = d.pop("subjectType", UNSET)

        _subject_ref = d.pop("subjectRef", UNSET)
        subject_ref: ItemBodySubjectref | Unset
        if isinstance(_subject_ref, Unset):
            subject_ref = UNSET
        else:
            subject_ref = ItemBodySubjectref.from_dict(_subject_ref)

        item_body = cls(
            queue_id=queue_id,
            subject_id=subject_id,
            content_hash=content_hash,
            statement_text=statement_text,
            subject_type=subject_type,
            subject_ref=subject_ref,
        )

        return item_body
