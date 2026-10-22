from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, BinaryIO, TextIO, TYPE_CHECKING, Generator

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

from ..types import UNSET, Unset
from typing import cast

if TYPE_CHECKING:
    from ..models.chat_message import ChatMessage


T = TypeVar("T", bound="ChatRequest")


@_attrs_define
class ChatRequest:
    """
    Attributes:
        model (str):
        messages (list[ChatMessage] | Unset):
        stream (bool | Unset):  Default: False.
        user (None | str | Unset):
        tools (list[Any] | None | Unset):
        functions (list[Any] | None | Unset):
    """

    model: str
    messages: list[ChatMessage] | Unset = UNSET
    stream: bool | Unset = False
    user: None | str | Unset = UNSET
    tools: list[Any] | None | Unset = UNSET
    functions: list[Any] | None | Unset = UNSET

    def to_dict(self) -> dict[str, Any]:
        from ..models.chat_message import ChatMessage  # noqa: PLC0415

        model = self.model

        messages: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.messages, Unset):
            messages = []
            for messages_item_data in self.messages:
                messages_item = messages_item_data.to_dict()
                messages.append(messages_item)

        stream = self.stream

        user: None | str | Unset
        if isinstance(self.user, Unset):
            user = UNSET
        else:
            user = self.user

        tools: list[Any] | None | Unset
        if isinstance(self.tools, Unset):
            tools = UNSET
        elif isinstance(self.tools, list):
            tools = self.tools

        else:
            tools = self.tools

        functions: list[Any] | None | Unset
        if isinstance(self.functions, Unset):
            functions = UNSET
        elif isinstance(self.functions, list):
            functions = self.functions

        else:
            functions = self.functions

        field_dict: dict[str, Any] = {}

        field_dict.update(
            {
                "model": model,
            }
        )
        if messages is not UNSET:
            field_dict["messages"] = messages
        if stream is not UNSET:
            field_dict["stream"] = stream
        if user is not UNSET:
            field_dict["user"] = user
        if tools is not UNSET:
            field_dict["tools"] = tools
        if functions is not UNSET:
            field_dict["functions"] = functions

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        from ..models.chat_message import ChatMessage  # noqa: PLC0415

        d = dict(src_dict)
        model = d.pop("model")

        _messages = d.pop("messages", UNSET)
        messages: list[ChatMessage] | Unset = UNSET
        if _messages is not UNSET:
            messages = []
            for messages_item_data in _messages:
                messages_item = ChatMessage.from_dict(messages_item_data)

                messages.append(messages_item)

        stream = d.pop("stream", UNSET)

        def _parse_user(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        user = _parse_user(d.pop("user", UNSET))

        def _parse_tools(data: object) -> list[Any] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                tools_type_0 = cast(list[Any], data)

                return tools_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[Any] | None | Unset, data)

        tools = _parse_tools(d.pop("tools", UNSET))

        def _parse_functions(data: object) -> list[Any] | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, list):
                    raise TypeError()
                functions_type_0 = cast(list[Any], data)

                return functions_type_0
            except TypeError, ValueError, AttributeError, KeyError:
                pass
            return cast(list[Any] | None | Unset, data)

        functions = _parse_functions(d.pop("functions", UNSET))

        chat_request = cls(
            model=model,
            messages=messages,
            stream=stream,
            user=user,
            tools=tools,
            functions=functions,
        )

        return chat_request
