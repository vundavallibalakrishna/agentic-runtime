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
    from ..models.send_body_response_format_type_0 import SendBodyResponseFormatType0
    from ..models.task_item import TaskItem


T = TypeVar("T", bound="SendBody")


@_attrs_define
class SendBody:
    """
    Attributes:
        text (str):
        stream (bool | Unset):  Default: False.
        attachment_ids (list[UUID] | Unset):
        file_ids (list[UUID] | Unset):
        collection_ids (list[UUID] | Unset):
        task_template (None | str | Unset):
        strategy (str | Unset):  Default: ''.
        items (list[str | TaskItem] | Unset):
        response_format (None | SendBodyResponseFormatType0 | Unset):
        suggest_followups (bool | Unset):  Default: False.
        wait (bool | Unset):  Default: True.
        callback_url (None | str | Unset):
    """

    text: str
    stream: bool | Unset = False
    attachment_ids: list[UUID] | Unset = UNSET
    file_ids: list[UUID] | Unset = UNSET
    collection_ids: list[UUID] | Unset = UNSET
    task_template: None | str | Unset = UNSET
    strategy: str | Unset = ""
    items: list[str | TaskItem] | Unset = UNSET
    response_format: None | SendBodyResponseFormatType0 | Unset = UNSET
    suggest_followups: bool | Unset = False
    wait: bool | Unset = True
    callback_url: None | str | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.send_body_response_format_type_0 import SendBodyResponseFormatType0  # noqa: PLC0415
        from ..models.task_item import TaskItem  # noqa: PLC0415

        text = self.text

        stream = self.stream

        attachment_ids: list[str] | Unset = UNSET
        if not isinstance(self.attachment_ids, Unset):
            attachment_ids = []
            for attachment_ids_item_data in self.attachment_ids:
                attachment_ids_item = str(attachment_ids_item_data)
                attachment_ids.append(attachment_ids_item)

        file_ids: list[str] | Unset = UNSET
        if not isinstance(self.file_ids, Unset):
            file_ids = []
            for file_ids_item_data in self.file_ids:
                file_ids_item = str(file_ids_item_data)
                file_ids.append(file_ids_item)

        collection_ids: list[str] | Unset = UNSET
        if not isinstance(self.collection_ids, Unset):
            collection_ids = []
            for collection_ids_item_data in self.collection_ids:
                collection_ids_item = str(collection_ids_item_data)
                collection_ids.append(collection_ids_item)

        task_template: None | str | Unset
        if isinstance(self.task_template, Unset):
            task_template = UNSET
        else:
            task_template = self.task_template

        strategy = self.strategy

        items: list[dict[str, Any] | str] | Unset = UNSET
        if not isinstance(self.items, Unset):
            items = []
            for items_item_data in self.items:
                items_item: dict[str, Any] | str
                if isinstance(items_item_data, TaskItem):
                    items_item = items_item_data.to_dict()
                else:
                    items_item = items_item_data
                items.append(items_item)

        response_format: dict[str, Any] | None | Unset
        if isinstance(self.response_format, Unset):
            response_format = UNSET
        elif isinstance(self.response_format, SendBodyResponseFormatType0):
            response_format = self.response_format.to_dict()
        else:
            response_format = self.response_format

        suggest_followups = self.suggest_followups

        wait = self.wait

        callback_url: None | str | Unset
        if isinstance(self.callback_url, Unset):
            callback_url = UNSET
        else:
            callback_url = self.callback_url

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "text": text,
            }
        )
        if stream is not UNSET:
            field_dict["stream"] = stream
        if attachment_ids is not UNSET:
            field_dict["attachmentIds"] = attachment_ids
        if file_ids is not UNSET:
            field_dict["fileIds"] = file_ids
        if collection_ids is not UNSET:
            field_dict["collectionIds"] = collection_ids
        if task_template is not UNSET:
            field_dict["taskTemplate"] = task_template
        if strategy is not UNSET:
            field_dict["strategy"] = strategy
        if items is not UNSET:
            field_dict["items"] = items
        if response_format is not UNSET:
            field_dict["responseFormat"] = response_format
        if suggest_followups is not UNSET:
            field_dict["suggestFollowups"] = suggest_followups
        if wait is not UNSET:
            field_dict["wait"] = wait
        if callback_url is not UNSET:
            field_dict["callbackUrl"] = callback_url

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.send_body_response_format_type_0 import SendBodyResponseFormatType0  # noqa: PLC0415
        from ..models.task_item import TaskItem  # noqa: PLC0415

        d = dict(src_dict)
        text = d.pop("text")

        stream = d.pop("stream", UNSET)

        _attachment_ids = d.pop("attachmentIds", UNSET)
        attachment_ids: list[UUID] | Unset = UNSET
        if _attachment_ids is not UNSET:
            attachment_ids = []
            for attachment_ids_item_data in _attachment_ids:
                attachment_ids_item = UUID(attachment_ids_item_data)

                attachment_ids.append(attachment_ids_item)

        _file_ids = d.pop("fileIds", UNSET)
        file_ids: list[UUID] | Unset = UNSET
        if _file_ids is not UNSET:
            file_ids = []
            for file_ids_item_data in _file_ids:
                file_ids_item = UUID(file_ids_item_data)

                file_ids.append(file_ids_item)

        _collection_ids = d.pop("collectionIds", UNSET)
        collection_ids: list[UUID] | Unset = UNSET
        if _collection_ids is not UNSET:
            collection_ids = []
            for collection_ids_item_data in _collection_ids:
                collection_ids_item = UUID(collection_ids_item_data)

                collection_ids.append(collection_ids_item)

        def _parse_task_template(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        task_template = _parse_task_template(d.pop("taskTemplate", UNSET))

        strategy = d.pop("strategy", UNSET)

        _items = d.pop("items", UNSET)
        items: list[str | TaskItem] | Unset = UNSET
        if _items is not UNSET:
            items = []
            for items_item_data in _items:

                def _parse_items_item(data: object) -> str | TaskItem:
                    try:
                        if not isinstance(data, dict):
                            raise TypeError()
                        items_item_type_0 = TaskItem.from_dict(data)

                        return items_item_type_0
                    except TypeError, ValueError, AttributeError, KeyError:
                        pass
                    return cast(str | TaskItem, data)

                items_item = _parse_items_item(items_item_data)

                items.append(items_item)

        def _parse_response_format(data: object) -> None | SendBodyResponseFormatType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_format_type_0 = SendBodyResponseFormatType0.from_dict(data)

                return response_format_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | SendBodyResponseFormatType0 | Unset, data)

        response_format = _parse_response_format(d.pop("responseFormat", UNSET))

        suggest_followups = d.pop("suggestFollowups", UNSET)

        wait = d.pop("wait", UNSET)

        def _parse_callback_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        callback_url = _parse_callback_url(d.pop("callbackUrl", UNSET))

        send_body = cls(
            text=text,
            stream=stream,
            attachment_ids=attachment_ids,
            file_ids=file_ids,
            collection_ids=collection_ids,
            task_template=task_template,
            strategy=strategy,
            items=items,
            response_format=response_format,
            suggest_followups=suggest_followups,
            wait=wait,
            callback_url=callback_url,
        )

        return send_body
