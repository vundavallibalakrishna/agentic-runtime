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
    from ..models.message_item import MessageItem
    from ..models.run_body_response_format_type_0 import RunBodyResponseFormatType0


T = TypeVar("T", bound="RunBody")


@_attrs_define
class RunBody:
    """
    Attributes:
        agent_id (UUID):
        text (str):
        callback_url (None | str | Unset):
        on_behalf_of_user_id (None | Unset | UUID):
        allow_on_behalf_of (bool | Unset):  Default: False.
        wait (bool | Unset):  Default: False.
        attachment_ids (list[UUID] | Unset):
        file_ids (list[UUID] | Unset):
        collection_ids (list[UUID] | Unset):
        task_template (None | str | Unset):
        items (list[MessageItem | str] | Unset):
        response_format (None | RunBodyResponseFormatType0 | Unset):
    """

    agent_id: UUID
    text: str
    callback_url: None | str | Unset = UNSET
    on_behalf_of_user_id: None | Unset | UUID = UNSET
    allow_on_behalf_of: bool | Unset = False
    wait: bool | Unset = False
    attachment_ids: list[UUID] | Unset = UNSET
    file_ids: list[UUID] | Unset = UNSET
    collection_ids: list[UUID] | Unset = UNSET
    task_template: None | str | Unset = UNSET
    items: list[MessageItem | str] | Unset = UNSET
    response_format: None | RunBodyResponseFormatType0 | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.message_item import MessageItem  # noqa: PLC0415
        from ..models.run_body_response_format_type_0 import RunBodyResponseFormatType0  # noqa: PLC0415

        agent_id = str(self.agent_id)

        text = self.text

        callback_url: None | str | Unset
        if isinstance(self.callback_url, Unset):
            callback_url = UNSET
        else:
            callback_url = self.callback_url

        on_behalf_of_user_id: None | str | Unset
        if isinstance(self.on_behalf_of_user_id, Unset):
            on_behalf_of_user_id = UNSET
        elif isinstance(self.on_behalf_of_user_id, UUID):
            on_behalf_of_user_id = str(self.on_behalf_of_user_id)
        else:
            on_behalf_of_user_id = self.on_behalf_of_user_id

        allow_on_behalf_of = self.allow_on_behalf_of

        wait = self.wait

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

        items: list[dict[str, Any] | str] | Unset = UNSET
        if not isinstance(self.items, Unset):
            items = []
            for items_item_data in self.items:
                items_item: dict[str, Any] | str
                if isinstance(items_item_data, MessageItem):
                    items_item = items_item_data.to_dict()
                else:
                    items_item = items_item_data
                items.append(items_item)

        response_format: dict[str, Any] | None | Unset
        if isinstance(self.response_format, Unset):
            response_format = UNSET
        elif isinstance(self.response_format, RunBodyResponseFormatType0):
            response_format = self.response_format.to_dict()
        else:
            response_format = self.response_format

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "agentId": agent_id,
                "text": text,
            }
        )
        if callback_url is not UNSET:
            field_dict["callbackUrl"] = callback_url
        if on_behalf_of_user_id is not UNSET:
            field_dict["onBehalfOfUserId"] = on_behalf_of_user_id
        if allow_on_behalf_of is not UNSET:
            field_dict["allowOnBehalfOf"] = allow_on_behalf_of
        if wait is not UNSET:
            field_dict["wait"] = wait
        if attachment_ids is not UNSET:
            field_dict["attachmentIds"] = attachment_ids
        if file_ids is not UNSET:
            field_dict["fileIds"] = file_ids
        if collection_ids is not UNSET:
            field_dict["collectionIds"] = collection_ids
        if task_template is not UNSET:
            field_dict["taskTemplate"] = task_template
        if items is not UNSET:
            field_dict["items"] = items
        if response_format is not UNSET:
            field_dict["responseFormat"] = response_format

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.message_item import MessageItem  # noqa: PLC0415
        from ..models.run_body_response_format_type_0 import RunBodyResponseFormatType0  # noqa: PLC0415

        d = dict(src_dict)
        agent_id = UUID(d.pop("agentId"))

        text = d.pop("text")

        def _parse_callback_url(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        callback_url = _parse_callback_url(d.pop("callbackUrl", UNSET))

        def _parse_on_behalf_of_user_id(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                on_behalf_of_user_id_type_0 = UUID(data)

                return on_behalf_of_user_id_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | Unset | UUID, data)

        on_behalf_of_user_id = _parse_on_behalf_of_user_id(d.pop("onBehalfOfUserId", UNSET))

        allow_on_behalf_of = d.pop("allowOnBehalfOf", UNSET)

        wait = d.pop("wait", UNSET)

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

        _items = d.pop("items", UNSET)
        items: list[MessageItem | str] | Unset = UNSET
        if _items is not UNSET:
            items = []
            for items_item_data in _items:

                def _parse_items_item(data: object) -> MessageItem | str:
                    try:
                        if not isinstance(data, dict):
                            raise TypeError()
                        items_item_type_0 = MessageItem.from_dict(data)

                        return items_item_type_0
                    except TypeError, ValueError, AttributeError, KeyError:
                        pass
                    return cast(MessageItem | str, data)

                items_item = _parse_items_item(items_item_data)

                items.append(items_item)

        def _parse_response_format(data: object) -> None | RunBodyResponseFormatType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                response_format_type_0 = RunBodyResponseFormatType0.from_dict(data)

                return response_format_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(None | RunBodyResponseFormatType0 | Unset, data)

        response_format = _parse_response_format(d.pop("responseFormat", UNSET))

        run_body = cls(
            agent_id=agent_id,
            text=text,
            callback_url=callback_url,
            on_behalf_of_user_id=on_behalf_of_user_id,
            allow_on_behalf_of=allow_on_behalf_of,
            wait=wait,
            attachment_ids=attachment_ids,
            file_ids=file_ids,
            collection_ids=collection_ids,
            task_template=task_template,
            items=items,
            response_format=response_format,
        )

        return run_body
